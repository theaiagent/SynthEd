"""
CalibrationMap: Maps target dropout ranges to simulation parameters.

Uses piecewise linear interpolation from empirically measured data points
to estimate the dropout_base_rate needed to achieve a target dropout rate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationPoint:
    """A single empirically measured calibration data point."""
    n_semesters: int
    dropout_base_rate: float
    observed_dropout_rate: float
    n_students: int
    seed_count: int  # number of seeds averaged


@dataclass(frozen=True)
class CalibrationEstimate:
    """Result of a calibration mapping."""
    estimated_dropout_base_rate: float
    validation_dropout_rate: float  # midpoint of target range
    validation_tolerance: float     # half-width of target range
    confidence: str                 # "high" (interpolated) or "low" (edge/clamped)
    n_semesters: int
    source_data_points: int


# Empirically measured calibration data (N=300, 3 seeds averaged per point).
# Measured with _dropout_risk_scale active (post Step 0 fix).
CALIBRATION_DATA: tuple[CalibrationPoint, ...] = (
    # 1-semester sweep across dropout_base_rate values
    CalibrationPoint(1, 0.20, 0.227, 300, 3),
    CalibrationPoint(1, 0.30, 0.279, 300, 3),
    CalibrationPoint(1, 0.40, 0.342, 300, 3),
    CalibrationPoint(1, 0.50, 0.386, 300, 3),
    CalibrationPoint(1, 0.60, 0.422, 300, 3),
    CalibrationPoint(1, 0.70, 0.446, 300, 3),
    CalibrationPoint(1, 0.80, 0.486, 300, 3),
    CalibrationPoint(1, 0.90, 0.489, 300, 3),
    CalibrationPoint(1, 0.95, 0.516, 300, 3),
    # Multi-semester at default rate (0.80)
    CalibrationPoint(2, 0.80, 0.759, 300, 3),
    CalibrationPoint(4, 0.80, 0.962, 300, 3),
)

# Bounds for dropout_base_rate
_MIN_BASE_RATE = 0.10
_MAX_BASE_RATE = 0.95


class CalibrationMap:
    """Maps target dropout rates to simulation parameters.

    Uses piecewise linear interpolation between known calibration points.
    Clamps to known range — does not extrapolate.
    """

    def __init__(
        self, data: tuple[CalibrationPoint, ...] = CALIBRATION_DATA,
    ):
        self._data = data

    def estimate(
        self,
        target_dropout: float,
        n_semesters: int = 1,
    ) -> CalibrationEstimate:
        """Estimate dropout_base_rate for a target dropout rate.

        Args:
            target_dropout: Desired dropout rate (0.0–1.0), typically
                the midpoint of the researcher's target range.
            n_semesters: Number of semesters to simulate.

        Returns:
            CalibrationEstimate with estimated parameters and confidence.
        """
        points = [p for p in self._data if p.n_semesters == n_semesters]

        semester_fallback = False
        if len(points) < 2:
            # Not enough data for this semester count — fall back to
            # 1-semester points and warn.
            points = [p for p in self._data if p.n_semesters == 1]
            if len(points) < 2:
                raise ValueError("Insufficient calibration data")
            semester_fallback = True
            logger.warning(
                "No calibration data for %d semesters, using 1-semester data",
                n_semesters,
            )

        # Sort by observed dropout rate for interpolation
        points = sorted(points, key=lambda p: p.observed_dropout_rate)

        observed = np.array([p.observed_dropout_rate for p in points])
        base_rates = np.array([p.dropout_base_rate for p in points])

        # Determine confidence — forced low on semester fallback
        min_observed = observed[0]
        max_observed = observed[-1]
        clamped = target_dropout < min_observed or target_dropout > max_observed
        confidence = "low" if (clamped or semester_fallback) else "high"

        if clamped:
            logger.warning(
                "Target dropout %.2f is outside calibrated range [%.2f, %.2f] "
                "for %d semester(s). Estimate may be unreliable.",
                target_dropout, min_observed, max_observed, n_semesters,
            )

        # Piecewise linear interpolation (with edge clamping)
        estimated_rate = float(np.interp(target_dropout, observed, base_rates))
        estimated_rate = max(_MIN_BASE_RATE, min(_MAX_BASE_RATE, estimated_rate))

        return CalibrationEstimate(
            estimated_dropout_base_rate=estimated_rate,
            validation_dropout_rate=target_dropout,
            validation_tolerance=0.0,  # use estimate_from_range() for range-based calls
            confidence=confidence,
            n_semesters=n_semesters,
            source_data_points=len(points),
        )

    def estimate_from_range(
        self,
        target_range: tuple[float, float],
        n_semesters: int = 1,
    ) -> CalibrationEstimate:
        """Estimate parameters from a target dropout range.

        Uses the midpoint for base_rate estimation and half-width for
        validation tolerance.

        Args:
            target_range: (lower, upper) dropout rate bounds.
            n_semesters: Number of semesters to simulate.

        Returns:
            CalibrationEstimate with tolerance derived from range width.
        """
        lower, upper = target_range
        if not (0.0 < lower < upper < 1.0):
            raise ValueError(
                f"Target range ({lower}, {upper}) must satisfy 0 < lower < upper < 1"
            )

        midpoint = (lower + upper) / 2
        tolerance = (upper - lower) / 2

        result = self.estimate(midpoint, n_semesters)

        return CalibrationEstimate(
            estimated_dropout_base_rate=result.estimated_dropout_base_rate,
            validation_dropout_rate=midpoint,
            validation_tolerance=tolerance,
            confidence=result.confidence,
            n_semesters=n_semesters,
            source_data_points=result.source_data_points,
        )
