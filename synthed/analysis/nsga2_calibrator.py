"""Multi-objective calibration using Optuna NSGAIISampler (NSGA-II)."""
from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import fields
from functools import partial

import numpy as np
import optuna
from optuna.samplers import NSGAIISampler

from ._sim_runner import run_simulation_with_overrides
from .pareto_utils import ParetoSolution, ParetoResult, find_knee_point, compute_hypervolume
from .sobol_sensitivity import (
    SobolAnalyzer,
    SobolParameter,
    SobolRanking,
    SOBOL_PARAMETER_SPACE,
)

from ..benchmarks.profiles import BenchmarkProfile

logger = logging.getLogger(__name__)

_TARGET_ENGAGEMENT: float = 0.5
_WORKER_TIMEOUT_S: int = 300


class NSGAIICalibrationError(RuntimeError):
    """Raised when NSGA-II finds no feasible solutions or profile is unknown."""


def select_nsga2_parameters(
    rankings: list[SobolRanking],
    top_n: int = 20,
    exclude_prefixes: tuple[str, ...] = ("config.", "inst."),
) -> tuple[SobolParameter, ...]:
    """Select top-N Sobol params, excluding config/inst (fixed per profile)."""
    filtered = [
        r for r in rankings
        if not any(r.parameter.startswith(prefix) for prefix in exclude_prefixes)
    ]
    selected_names = {r.parameter for r in filtered[:top_n]}
    return tuple(
        p for p in SOBOL_PARAMETER_SPACE
        if p.name in selected_names
    )


class NSGAIICalibrator:
    """Multi-objective calibrator using Optuna NSGAIISampler.

    Fixes config.* and inst.* parameters to profile values and optimizes
    only engine/theory/grading constants. Two objectives (dropout_error,
    gpa_error) with three hard constraints (engagement floor, dropout range).

    When ``n_workers > 1``, simulations run in separate processes via
    ``ProcessPoolExecutor`` to bypass the GIL. Uses Optuna's ask/tell API
    with batch size = ``pop_size`` (one NSGA-II generation per batch) to
    preserve generational selection semantics.

    Windows note: Entry-point scripts calling this class with ``n_workers > 1``
    must be protected with ``if __name__ == "__main__":``.
    """

    def __init__(
        self,
        n_students: int = 500,
        seed: int = 42,
        n_workers: int = 1,
    ) -> None:
        self._n_students = n_students
        self._seed = seed
        self._n_workers = n_workers

    def run(
        self,
        profile: str | BenchmarkProfile,
        pop_size: int = 80,
        n_trials: int = 8000,
        sobol_rankings: list[SobolRanking] | None = None,
        sobol_top_n: int = 20,
    ) -> ParetoResult:
        """Run NSGA-II calibration for a benchmark profile."""
        from ..benchmarks.profiles import PROFILES

        if isinstance(profile, str):
            if profile not in PROFILES:
                raise NSGAIICalibrationError(
                    f"Unknown profile '{profile}'. "
                    f"Available: {list(PROFILES)}"
                )
            resolved = PROFILES[profile]
            profile_name = profile
        else:
            resolved = profile
            profile_name = resolved.name

        # Parameter selection
        if sobol_rankings is None:
            logger.info("Running Sobol analysis for parameter selection...")
            analyzer = SobolAnalyzer(
                n_students=self._n_students, seed=self._seed,
            )
            sobol_results = analyzer.run()
            dropout_result = next(
                r for r in sobol_results if r.metric == "dropout_rate"
            )
            sobol_rankings = analyzer.rank(dropout_result)

        params = select_nsga2_parameters(sobol_rankings, top_n=sobol_top_n)
        param_names = tuple(p.name for p in params)
        logger.info(
            "Selected %d parameters for NSGA-II: %s",
            len(params), ", ".join(param_names),
        )

        # Targets and fixed overrides
        target_dropout = resolved.reference_stats.dropout_rate
        target_gpa = resolved.reference_stats.gpa_mean
        fixed_overrides = self._build_fixed_overrides(resolved)
        lo, hi = resolved.expected_dropout_range

        # Constraints
        def constraints_func(
            trial: optuna.trial.FrozenTrial,
        ) -> list[float]:
            eng = trial.user_attrs["achieved_engagement"]
            drop = trial.user_attrs["achieved_dropout"]
            return [
                0.1 - eng,    # engagement >= 0.1 (includes dropped-out students)
                lo - drop,    # dropout >= lo
                drop - hi,    # dropout <= hi
            ]

        # Study
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        sampler = NSGAIISampler(
            seed=self._seed,
            population_size=pop_size,
            constraints_func=constraints_func,
        )
        study = optuna.create_study(
            directions=["minimize", "minimize"],
            sampler=sampler,
        )
        logger.info(
            "Starting NSGA-II: %d trials, pop_size=%d, %d params, %d workers",
            n_trials, pop_size, len(params), self._n_workers,
        )

        if self._n_workers > 1:
            hv_history = self._run_parallel(
                study, params, fixed_overrides, resolved,
                target_dropout, target_gpa, n_trials, pop_size,
            )
        else:
            hv_history = self._run_sequential(
                study, params, fixed_overrides, resolved,
                target_dropout, target_gpa, n_trials, pop_size,
            )

        # Extract Pareto front
        best_trials = study.best_trials
        if not best_trials:
            raise NSGAIICalibrationError(
                f"NSGA-II found no feasible solutions for '{profile_name}' "
                f"after {n_trials} evaluations. Consider relaxing constraints "
                f"or widening parameter bounds."
            )

        pareto_solutions = tuple(
            ParetoSolution(
                params={p.name: t.params[p.name] for p in params},
                dropout_error=t.values[0],
                gpa_error=t.values[1],
                engagement_error=abs(
                    t.user_attrs["achieved_engagement"] - _TARGET_ENGAGEMENT
                ),
                achieved_dropout=t.user_attrs["achieved_dropout"],
                achieved_gpa=t.user_attrs["achieved_gpa"],
                achieved_engagement=t.user_attrs["achieved_engagement"],
            )
            for t in best_trials
        )

        knee = find_knee_point(pareto_solutions)
        logger.info(
            "NSGA-II complete: %d Pareto solutions, knee-point "
            "dropout_err=%.4f gpa_err=%.4f",
            len(pareto_solutions),
            knee.dropout_error,
            knee.gpa_error,
        )

        return ParetoResult(
            profile_name=profile_name,
            pareto_front=pareto_solutions,
            knee_point=knee,
            n_evaluations=len(study.trials),
            parameter_names=param_names,
            hv_history=tuple(hv_history),
        )

    def _run_parallel(
        self,
        study: optuna.Study,
        params: tuple[SobolParameter, ...],
        fixed_overrides: dict[str, float],
        profile: BenchmarkProfile,
        target_dropout: float,
        target_gpa: float,
        n_trials: int,
        pop_size: int,
    ) -> list[float]:
        """Run trials with ProcessPoolExecutor for GIL bypass.

        Uses Optuna's ask/tell API: ask for a batch of trials, build
        override dicts in the main process, submit the top-level
        ``run_simulation_with_overrides`` to the pool (picklable),
        then tell results back to Optuna.

        Pool is created once and reused across all generations to avoid
        repeated process spawn overhead on Windows.

        Returns per-generation hypervolume history.
        """
        ref_point = np.array([0.25, 2.0])
        hv_history: list[float] = []
        worker = partial(
            run_simulation_with_overrides,
            n_students=self._n_students,
            seed=self._seed,
            default_config=profile.persona_config,
            calibration_mode=True,
        )
        completed = 0
        pool = ProcessPoolExecutor(max_workers=self._n_workers)
        try:
            while completed < n_trials:
                batch_size = min(pop_size, n_trials - completed)
                trials = [study.ask() for _ in range(batch_size)]

                # Build override dicts in main process (no closures to pickle)
                override_dicts = []
                for trial in trials:
                    overrides = dict(fixed_overrides)
                    for p in params:
                        overrides[p.name] = trial.suggest_float(
                            p.name, p.lower, p.upper, log=p.log_scale,
                        )
                    override_dicts.append(overrides)

                # Submit top-level function to pool (pickle-safe)
                future_to_trial = {
                    pool.submit(worker, overrides=od): trial
                    for od, trial in zip(override_dicts, trials)
                }

                # Collect with as_completed for max throughput
                results_map: dict[int, dict] = {}
                for future in as_completed(future_to_trial, timeout=_WORKER_TIMEOUT_S * batch_size):
                    trial = future_to_trial[future]
                    try:
                        results_map[trial.number] = future.result(timeout=_WORKER_TIMEOUT_S)
                    except Exception as e:
                        logger.warning("Trial %d failed: %s", trial.number, e)
                        study.tell(trial, state=optuna.trial.TrialState.FAIL)

                # Tell Optuna in trial order (preserves generational semantics)
                for trial in trials:
                    if trial.number not in results_map:
                        continue
                    result = results_map[trial.number]
                    trial.set_user_attr("achieved_dropout", result["dropout_rate"])
                    trial.set_user_attr("achieved_gpa", result["mean_gpa"])
                    trial.set_user_attr("achieved_engagement", result["mean_engagement"])
                    trial.set_user_attr("pass_rate", result.get("pass_rate", 0.0))
                    trial.set_user_attr("distinction_rate", result.get("distinction_rate", 0.0))

                    dropout_error = abs(result["dropout_rate"] - target_dropout)
                    gpa_error = abs(result["mean_gpa"] - target_gpa)
                    study.tell(trial, (dropout_error, gpa_error))

                # Safety: mark any untold trials as FAIL
                for trial in trials:
                    if trial.number not in results_map:
                        try:
                            study.tell(trial, state=optuna.trial.TrialState.FAIL)
                        except RuntimeError:
                            pass  # already told as FAIL in the as_completed loop

                # HV tracking per generation
                best = study.best_trials
                if best:
                    pts = np.array([(t.values[0], t.values[1]) for t in best])
                    hv = compute_hypervolume(pts, ref_point)
                    hv_history.append(hv)

                completed += batch_size
                if completed % (pop_size * 5) == 0:
                    logger.info("Progress: %d/%d trials", completed, n_trials)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return hv_history

    def _run_sequential(
        self,
        study: optuna.Study,
        params: tuple[SobolParameter, ...],
        fixed_overrides: dict[str, float],
        profile: BenchmarkProfile,
        target_dropout: float,
        target_gpa: float,
        n_trials: int,
        pop_size: int,
    ) -> list[float]:
        """Run trials sequentially with ask/tell API and HV tracking."""
        ref_point = np.array([0.25, 2.0])
        hv_history: list[float] = []
        completed = 0

        while completed < n_trials:
            batch_size = min(pop_size, n_trials - completed)

            for _ in range(batch_size):
                trial = study.ask()
                overrides = dict(fixed_overrides)
                for p in params:
                    overrides[p.name] = trial.suggest_float(
                        p.name, p.lower, p.upper, log=p.log_scale,
                    )
                try:
                    result = run_simulation_with_overrides(
                        overrides=overrides,
                        n_students=self._n_students,
                        seed=self._seed,
                        default_config=profile.persona_config,
                        calibration_mode=True,
                    )
                    trial.set_user_attr("achieved_dropout", result["dropout_rate"])
                    trial.set_user_attr("achieved_gpa", result["mean_gpa"])
                    trial.set_user_attr("achieved_engagement", result["mean_engagement"])
                    trial.set_user_attr("pass_rate", result.get("pass_rate", 0.0))
                    trial.set_user_attr("distinction_rate", result.get("distinction_rate", 0.0))

                    dropout_error = abs(result["dropout_rate"] - target_dropout)
                    gpa_error = abs(result["mean_gpa"] - target_gpa)
                    study.tell(trial, (dropout_error, gpa_error))
                except Exception as e:
                    logger.warning("Trial %d failed: %s", trial.number, e)
                    study.tell(trial, state=optuna.trial.TrialState.FAIL)

            completed += batch_size

            best = study.best_trials
            if best:
                pts = np.array([(t.values[0], t.values[1]) for t in best])
                hv = compute_hypervolume(pts, ref_point)
                hv_history.append(hv)

            if completed % (pop_size * 5) == 0:
                logger.info("Progress: %d/%d trials", completed, n_trials)

        return hv_history

    def validate_solution(
        self,
        solution: ParetoSolution,
        profile: str | BenchmarkProfile,
        n_students: int = 500,
        seeds: tuple[int, ...] = (42, 123, 456),
    ) -> tuple[float, float, float, float]:
        """Re-evaluate with full population + multiple seeds.

        Returns (dropout_mean, dropout_std, gpa_mean, gpa_std).
        Runs sequentially — pool overhead exceeds benefit for few seeds.
        """
        from ..benchmarks.profiles import PROFILES

        if isinstance(profile, str):
            resolved = PROFILES[profile]
        else:
            resolved = profile
        fixed = self._build_fixed_overrides(resolved)

        dropouts: list[float] = []
        gpas: list[float] = []
        for s in seeds:
            overrides = {**fixed, **solution.params}
            result = run_simulation_with_overrides(
                overrides=overrides,
                n_students=n_students,
                seed=s,
                default_config=resolved.persona_config,
                calibration_mode=True,
            )
            dropouts.append(result["dropout_rate"])
            gpas.append(result["mean_gpa"])

        return (
            float(np.mean(dropouts)),
            float(np.std(dropouts)),
            float(np.mean(gpas)),
            float(np.std(gpas)),
        )

    def _build_fixed_overrides(
        self, profile: BenchmarkProfile,
    ) -> dict[str, float]:
        """Lock config.* and inst.* params to profile values.

        Uses type(val) is float (not isinstance) to exclude bool fields,
        since bool is a subclass of int in Python.
        """
        overrides: dict[str, float] = {}
        for f in fields(profile.persona_config):
            val = getattr(profile.persona_config, f.name)
            if type(val) is float:
                overrides[f"config.{f.name}"] = val
        for f in fields(profile.institutional_config):
            val = getattr(profile.institutional_config, f.name)
            if type(val) is float:
                overrides[f"inst.{f.name}"] = val
        return overrides
