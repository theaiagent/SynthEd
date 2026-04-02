"""Multi-objective calibration using Optuna NSGAIISampler (NSGA-II)."""
from __future__ import annotations

import logging
from dataclasses import fields
from typing import TYPE_CHECKING

import numpy as np
import optuna
from optuna.samplers import NSGAIISampler

from ._sim_runner import run_simulation_with_overrides
from .pareto_utils import ParetoSolution, ParetoResult, find_knee_point
from .sobol_sensitivity import (
    SobolAnalyzer,
    SobolParameter,
    SobolRanking,
    SOBOL_PARAMETER_SPACE,
)

if TYPE_CHECKING:
    from ..benchmarks.profiles import BenchmarkProfile

logger = logging.getLogger(__name__)


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
    only engine/theory constants. Two objectives (dropout_error, gpa_error)
    with three hard constraints (engagement floor, dropout range).

    NOTE: n_workers maps to Optuna's n_jobs (ThreadPoolExecutor).
    For CPU-bound simulations, thread-based parallelism gives limited
    benefit due to GIL.
    """

    def __init__(
        self,
        n_students: int = 100,
        seed: int = 42,
        n_workers: int = 1,
    ) -> None:
        self._n_students = n_students
        self._seed = seed
        self._n_workers = n_workers

    def run(
        self,
        profile_name: str,
        pop_size: int = 80,
        n_trials: int = 8000,
        sobol_rankings: list[SobolRanking] | None = None,
        sobol_top_n: int = 20,
    ) -> ParetoResult:
        """Run NSGA-II calibration for a benchmark profile."""
        from ..benchmarks.profiles import PROFILES

        if profile_name not in PROFILES:
            raise NSGAIICalibrationError(
                f"Unknown profile '{profile_name}'. "
                f"Available: {list(PROFILES)}"
            )

        profile = PROFILES[profile_name]

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
        target_dropout = profile.reference_stats.dropout_rate
        target_gpa = profile.reference_stats.gpa_mean
        fixed_overrides = self._build_fixed_overrides(profile)
        lo, hi = profile.expected_dropout_range

        # Objective
        def objective(trial: optuna.Trial) -> tuple[float, float]:
            overrides = dict(fixed_overrides)
            for p in params:
                overrides[p.name] = trial.suggest_float(
                    p.name, p.lower, p.upper, log=p.log_scale,
                )
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

            dropout_error = abs(result["dropout_rate"] - target_dropout)
            gpa_error = abs(result["mean_gpa"] - target_gpa)
            return dropout_error, gpa_error

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
            "Starting NSGA-II: %d trials, pop_size=%d, %d params",
            n_trials, pop_size, len(params),
        )
        study.optimize(
            objective, n_trials=n_trials, n_jobs=self._n_workers,
        )

        # Extract Pareto front
        best_trials = study.best_trials
        if not best_trials:
            raise NSGAIICalibrationError(
                f"NSGA-II found no feasible solutions for '{profile_name}' "
                f"after {n_trials} evaluations. Consider relaxing constraints "
                f"or widening parameter bounds."
            )

        target_engagement = 0.5
        pareto_solutions = tuple(
            ParetoSolution(
                params={p.name: t.params[p.name] for p in params},
                dropout_error=t.values[0],
                gpa_error=t.values[1],
                engagement_error=abs(
                    t.user_attrs["achieved_engagement"] - target_engagement
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
        )

    def validate_solution(
        self,
        solution: ParetoSolution,
        profile_name: str,
        n_students: int = 500,
        seeds: tuple[int, ...] = (42, 123, 456),
    ) -> tuple[float, float, float, float]:
        """Re-evaluate with full population + multiple seeds.

        Returns (dropout_mean, dropout_std, gpa_mean, gpa_std).
        """
        from ..benchmarks.profiles import PROFILES

        profile = PROFILES[profile_name]
        fixed = self._build_fixed_overrides(profile)

        dropouts: list[float] = []
        gpas: list[float] = []
        for s in seeds:
            overrides = {**fixed, **solution.params}
            result = run_simulation_with_overrides(
                overrides=overrides,
                n_students=n_students,
                seed=s,
                default_config=profile.persona_config,
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
