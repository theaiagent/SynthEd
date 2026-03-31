"""
Trait-based calibrator using Bayesian optimization (Optuna).

Optimizes SynthEd simulation parameters to minimize the distance between
synthetic output distributions and real OULAD reference data. Uses the
parameter space and override mechanism from the Sobol sensitivity module.

Phase 2 of the trait-based calibration pipeline:
  Phase 1 (Sobol) → identifies which parameters matter most
  Phase 2 (this) → optimizes those parameters against OULAD targets
  Phase 3 (validation) → confirms calibration on held-out data
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import optuna

from ..agents.persona import PersonaConfig
from .oulad_targets import OuladTargets
from .sobol_sensitivity import SobolParameter, SOBOL_PARAMETER_SPACE
from ._sim_runner import run_simulation_with_overrides

logger = logging.getLogger(__name__)

# Suppress Optuna's verbose trial logging (we log our own progress)
optuna.logging.set_verbosity(optuna.logging.WARNING)


# ─────────────────────────────────────────────
# Loss functions
# ─────────────────────────────────────────────

def squared_error(predicted: float, target: float) -> float:
    """Squared difference between predicted and target."""
    return (predicted - target) ** 2


def normalized_squared_error(predicted: float, target: float) -> float:
    """Squared error normalized by target magnitude to balance scales."""
    if target == 0.0:
        return predicted ** 2
    return ((predicted - target) / target) ** 2


# ─────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class CalibrationResult:
    """Result of a trait-based calibration run."""
    best_params: dict[str, float]       # optimized parameter values
    best_loss: float                    # final composite loss
    dropout_loss: float                 # dropout rate component
    gpa_loss: float                     # GPA mean component
    engagement_loss: float              # engagement component
    n_trials: int                       # total Optuna trials
    target_dropout: float               # OULAD target
    achieved_dropout: float             # best trial's dropout
    target_gpa: float                   # OULAD target
    achieved_gpa: float                 # best trial's GPA
    parameter_names: tuple[str, ...]    # names in order


# ─────────────────────────────────────────────
# Calibrator
# ─────────────────────────────────────────────

_DROPOUT_WEIGHT: float = 0.50    # dropout rate match priority
_GPA_WEIGHT: float = 0.30       # GPA distribution match
_ENGAGEMENT_WEIGHT: float = 0.20  # engagement level match


class TraitCalibrator:
    """
    Bayesian optimization of SynthEd parameters against OULAD targets.

    Uses Optuna's Tree-structured Parzen Estimator (TPE) to search the
    parameter space defined by SobolParameter entries. Each trial runs
    a full SynthEd simulation and computes a weighted loss against
    real OULAD statistics.

    Usage:
        targets = extract_targets("oulad/")
        calibrator = TraitCalibrator(targets, n_students=200)
        result = calibrator.run(n_trials=100)
        print(result.best_params)
    """

    def __init__(
        self,
        targets: OuladTargets,
        n_students: int = 200,
        seed: int = 42,
        parameters: tuple[SobolParameter, ...] | None = None,
        dropout_weight: float = _DROPOUT_WEIGHT,
        gpa_weight: float = _GPA_WEIGHT,
        engagement_weight: float = _ENGAGEMENT_WEIGHT,
    ):
        self.targets = targets
        self.n_students = n_students
        self.seed = seed
        self.parameters = parameters or SOBOL_PARAMETER_SPACE
        self.dropout_weight = dropout_weight
        self.gpa_weight = gpa_weight
        self.engagement_weight = engagement_weight
        self._default_config = PersonaConfig()

    def run(
        self,
        n_trials: int = 100,
        timeout: float | None = None,
        study: optuna.Study | None = None,
    ) -> CalibrationResult:
        """
        Run Bayesian optimization.

        Args:
            n_trials: Maximum number of optimization trials.
            timeout: Optional timeout in seconds.
            study: Pre-existing Optuna study (for resumption).

        Returns:
            CalibrationResult with optimized parameters and metrics.
        """
        if study is None:
            study = optuna.create_study(
                direction="minimize",
                sampler=optuna.samplers.TPESampler(seed=self.seed),
            )

        logger.info(
            "Starting trait calibration: %d params, %d trials, %d students/trial",
            len(self.parameters), n_trials, self.n_students,
        )

        study.optimize(
            self._objective,
            n_trials=n_trials,
            timeout=timeout,
        )

        best = study.best_trial
        logger.info(
            "Calibration complete: loss=%.4f after %d trials",
            best.value, len(study.trials),
        )

        # Extract per-metric losses from best trial
        dropout_loss = best.user_attrs.get("dropout_loss", 0.0)
        gpa_loss = best.user_attrs.get("gpa_loss", 0.0)
        engagement_loss = best.user_attrs.get("engagement_loss", 0.0)

        return CalibrationResult(
            best_params=dict(best.params),
            best_loss=best.value,
            dropout_loss=dropout_loss,
            gpa_loss=gpa_loss,
            engagement_loss=engagement_loss,
            n_trials=len(study.trials),
            target_dropout=self.targets.overall_dropout_rate,
            achieved_dropout=best.user_attrs.get("achieved_dropout", 0.0),
            target_gpa=self.targets.gpa_mean,
            achieved_gpa=best.user_attrs.get("achieved_gpa", 0.0),
            parameter_names=tuple(p.name for p in self.parameters),
        )

    def _objective(self, trial: optuna.Trial) -> float:
        """Optuna objective: weighted composite loss vs OULAD targets."""
        overrides: dict[str, float] = {}
        for p in self.parameters:
            if p.log_scale:
                value = trial.suggest_float(p.name, p.lower, p.upper, log=True)
            elif p.step is not None:
                value = trial.suggest_float(p.name, p.lower, p.upper, step=p.step)
            else:
                value = trial.suggest_float(p.name, p.lower, p.upper)
            overrides[p.name] = value

        metrics = run_simulation_with_overrides(
            overrides, self.n_students, self.seed, self._default_config,
        )

        dropout_loss = normalized_squared_error(
            metrics["dropout_rate"], self.targets.overall_dropout_rate,
        )
        gpa_loss = normalized_squared_error(
            metrics["mean_gpa"], self.targets.gpa_mean,
        )

        # Engagement: compare CV (coefficient of variation) — scale-independent.
        # SynthEd engagement is 0-1 probability, OULAD is clicks/day.
        # Absolute values are incomparable; CV captures distribution shape.
        mean_eng = metrics["mean_engagement"]
        std_eng = metrics["std_engagement"]
        synthed_cv = std_eng / mean_eng if mean_eng > 0 else 0.0
        engagement_loss = normalized_squared_error(
            synthed_cv, self.targets.engagement_cv,
        )

        composite = (
            self.dropout_weight * dropout_loss
            + self.gpa_weight * gpa_loss
            + self.engagement_weight * engagement_loss
        )

        trial.set_user_attr("dropout_loss", round(dropout_loss, 6))
        trial.set_user_attr("gpa_loss", round(gpa_loss, 6))
        trial.set_user_attr("engagement_loss", round(engagement_loss, 6))
        trial.set_user_attr("achieved_dropout", round(metrics["dropout_rate"], 4))
        trial.set_user_attr("achieved_gpa", round(metrics["mean_gpa"], 3))

        if trial.number % 10 == 0:
            logger.info(
                "  Trial %d: loss=%.4f (dropout=%.3f, gpa=%.3f)",
                trial.number, composite,
                metrics["dropout_rate"], metrics["mean_gpa"],
            )

        return composite


def select_top_parameters(
    rankings: list,
    top_n: int = 15,
) -> tuple[SobolParameter, ...]:
    """
    Select top-N parameters from Sobol rankings for calibration.

    Filters SOBOL_PARAMETER_SPACE to only include the most influential
    parameters as determined by Phase 1 Sobol analysis.

    Args:
        rankings: List of SobolRanking from SobolAnalyzer.rank().
        top_n: Number of top parameters to select.

    Returns:
        Tuple of SobolParameter for the top-N most important parameters.
    """
    top_names = {r.parameter for r in rankings[:top_n]}
    return tuple(p for p in SOBOL_PARAMETER_SPACE if p.name in top_names)
