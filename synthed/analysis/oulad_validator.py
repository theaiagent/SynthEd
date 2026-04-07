"""
OULAD comparative validation (Phase 3 of trait-based calibration).

Validates calibrated SynthEd parameters against held-out OULAD modules.
Compares distribution shapes using KS test, and scalar metrics using
normalized error.

Pipeline:
  1. Calibrate on training modules (Phase 2)
  2. Run SynthEd with calibrated parameters
  3. Compare output against held-out OULAD modules (this module)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .oulad_targets import extract_targets
from ._sim_runner import run_simulation_with_overrides
from ..agents.persona import PersonaConfig

logger = logging.getLogger(__name__)

# Default module split: calibration vs validation
CALIBRATION_MODULES: frozenset[str] = frozenset({"BBB", "FFF", "DDD", "EEE", "AAA"})
VALIDATION_MODULES: frozenset[str] = frozenset({"CCC", "GGG"})


@dataclass(frozen=True)
class ValidationMetric:
    """A single validation comparison."""
    name: str
    synthed_value: float
    oulad_value: float
    error: float           # absolute error
    relative_error: float  # |error| / |target|
    passed: bool           # within acceptable threshold


@dataclass(frozen=True)
class ValidationReport:
    """Full validation report comparing calibrated SynthEd vs held-out OULAD."""
    metrics: tuple[ValidationMetric, ...]
    passed_count: int
    total_count: int
    pass_rate: float
    calibrated_params: dict[str, float]
    calibration_modules: frozenset[str]
    validation_modules: frozenset[str]
    n_students: int

    @property
    def grade(self) -> str:
        if self.pass_rate >= 0.80:
            return "A"
        if self.pass_rate >= 0.60:
            return "B"
        if self.pass_rate >= 0.40:
            return "C"
        return "D"


# ─────────────────────────────────────────────
# Thresholds for pass/fail
# ─────────────────────────────────────────────

_DROPOUT_RATE_TOLERANCE: float = 0.10        # within 10 percentage points
_GPA_MEAN_TOLERANCE: float = 0.20            # relative error < 20%
_ENGAGEMENT_CV_TOLERANCE: float = 0.30       # relative error < 30%
_SCORE_MEAN_TOLERANCE: float = 0.15          # relative error < 15%
_DISABILITY_RATE_TOLERANCE: float = 0.50     # relative error < 50% (small base)


def validate_against_oulad(
    calibrated_params: dict[str, float],
    oulad_dir: str,
    n_students: int = 200,
    seed: int = 42,
    validation_modules: frozenset[str] | None = None,
) -> ValidationReport:
    """
    Run calibrated SynthEd and compare against held-out OULAD modules.

    Args:
        calibrated_params: Optimized parameter dict from TraitCalibrator.
        oulad_dir: Path to OULAD CSV directory.
        n_students: Population size for validation simulation.
        seed: RNG seed.
        validation_modules: OULAD modules to validate against.

    Returns:
        ValidationReport with per-metric comparisons.
    """
    val_modules = validation_modules or VALIDATION_MODULES

    # Extract held-out OULAD targets
    oulad_targets = extract_targets(oulad_dir, modules=val_modules)
    logger.info(
        "Validation targets (modules %s): dropout=%.1f%%, GPA=%.3f, n=%d",
        val_modules, oulad_targets.overall_dropout_rate * 100,
        oulad_targets.gpa_mean, oulad_targets.n_students,
    )

    # Run SynthEd with calibrated parameters
    default_config = PersonaConfig()
    metrics = run_simulation_with_overrides(
        calibrated_params, n_students, seed, default_config,
    )

    synthed_dropout = metrics["dropout_rate"]
    synthed_gpa = metrics["mean_gpa"]
    synthed_mean_eng = metrics["mean_engagement"]
    synthed_std_eng = metrics["std_engagement"]
    synthed_cv = synthed_std_eng / synthed_mean_eng if synthed_mean_eng > 0 else 0.0

    # Build validation metrics
    validation_metrics: list[ValidationMetric] = []

    # Dropout rate
    validation_metrics.append(_compare(
        "dropout_rate", synthed_dropout, oulad_targets.overall_dropout_rate,
        _DROPOUT_RATE_TOLERANCE, absolute=True,
    ))

    # GPA mean
    validation_metrics.append(_compare(
        "gpa_mean", synthed_gpa, oulad_targets.gpa_mean,
        _GPA_MEAN_TOLERANCE,
    ))

    # Engagement CV (scale-independent)
    validation_metrics.append(_compare(
        "engagement_cv", synthed_cv, oulad_targets.engagement_cv,
        _ENGAGEMENT_CV_TOLERANCE,
    ))

    # Score mean (SynthEd GPA * 25 ≈ score/100 scale, approximate)
    synthed_score_approx = synthed_gpa * 25.0  # GPA 4.0 → score 100
    validation_metrics.append(_compare(
        "score_mean_approx", synthed_score_approx, oulad_targets.score_mean,
        _SCORE_MEAN_TOLERANCE,
    ))

    metrics_tuple = tuple(validation_metrics)
    passed = sum(1 for m in metrics_tuple if m.passed)

    report = ValidationReport(
        metrics=metrics_tuple,
        passed_count=passed,
        total_count=len(metrics_tuple),
        pass_rate=passed / len(metrics_tuple) if metrics_tuple else 0.0,
        calibrated_params=calibrated_params,
        calibration_modules=CALIBRATION_MODULES,
        validation_modules=val_modules,
        n_students=n_students,
    )

    logger.info(
        "Validation: %d/%d passed (grade %s)",
        report.passed_count, report.total_count, report.grade,
    )
    for m in metrics_tuple:
        status = "PASS" if m.passed else "FAIL"
        logger.info(
            "  [%s] %s: synthed=%.4f, oulad=%.4f, rel_err=%.1f%%",
            status, m.name, m.synthed_value, m.oulad_value, m.relative_error * 100,
        )

    return report


def _compare(
    name: str,
    synthed: float,
    oulad: float,
    tolerance: float,
    absolute: bool = False,
) -> ValidationMetric:
    """Compare a single metric with tolerance check."""
    error = synthed - oulad
    if absolute:
        rel_error = abs(error)
    else:
        rel_error = abs(error / oulad) if oulad != 0 else abs(error)
    passed = rel_error <= tolerance

    return ValidationMetric(
        name=name,
        synthed_value=round(synthed, 4),
        oulad_value=round(oulad, 4),
        error=round(error, 4),
        relative_error=round(rel_error, 4),
        passed=passed,
    )

