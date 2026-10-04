"""
CalibrationMap: Maps target dropout ranges to simulation parameters.

Uses piecewise linear interpolation from simulation-measured data points
to estimate the dropout_base_rate needed to achieve a target dropout rate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationPoint:
    """A mean dropout rate measured from repeated simulator runs."""
    n_semesters: int
    dropout_base_rate: float
    observed_dropout_rate: float
    n_students: int
    seed_count: int  # number of seeds averaged


@dataclass(frozen=True)
class CalibrationEstimate:
    """Mapping result; confidence describes coverage, not statistical certainty."""
    estimated_dropout_base_rate: float
    validation_dropout_rate: float  # midpoint of target range
    validation_tolerance: float     # half-width of target range
    confidence: str                 # legacy coverage label; low on clamping/ambiguity
    n_semesters: int
    source_data_points: int
    observed_dropout_range: tuple[float, float] | None = None
    clamped: bool = False
    mapping_status: str = "interpolated"
    candidate_base_rates: tuple[float, ...] = ()
    reference_population_size: int | None = None


# Default-model measurements: N=500, seeds 42..46, 14 weeks per semester.
# Reproduce with scripts/measure_dropout_horizons.py; raw counts, seed variation,
# resolved configuration, dependencies and source hashes are recorded in
# docs/measurements/dropout-horizons.json. Re-measure after model/RNG changes.
CALIBRATION_DATA: tuple[CalibrationPoint, ...] = (
    # 1-semester cumulative dropout (mean across seeds)
    CalibrationPoint(1, 0.010, 0.0312, 500, 5),
    CalibrationPoint(1, 0.025, 0.0416, 500, 5),
    CalibrationPoint(1, 0.050, 0.0800, 500, 5),
    CalibrationPoint(1, 0.075, 0.1016, 500, 5),
    CalibrationPoint(1, 0.100, 0.1328, 500, 5),
    CalibrationPoint(1, 0.200, 0.2296, 500, 5),
    CalibrationPoint(1, 0.300, 0.2912, 500, 5),
    CalibrationPoint(1, 0.400, 0.3220, 500, 5),
    CalibrationPoint(1, 0.460, 0.3560, 500, 5),
    CalibrationPoint(1, 0.500, 0.3676, 500, 5),
    CalibrationPoint(1, 0.600, 0.3796, 500, 5),
    CalibrationPoint(1, 0.700, 0.4044, 500, 5),
    CalibrationPoint(1, 0.800, 0.4220, 500, 5),
    CalibrationPoint(1, 0.900, 0.4340, 500, 5),
    CalibrationPoint(1, 0.950, 0.4340, 500, 5),
    # 2-semester cumulative dropout (mean across seeds)
    CalibrationPoint(2, 0.010, 0.1104, 500, 5),
    CalibrationPoint(2, 0.025, 0.1364, 500, 5),
    CalibrationPoint(2, 0.050, 0.2588, 500, 5),
    CalibrationPoint(2, 0.075, 0.3132, 500, 5),
    CalibrationPoint(2, 0.100, 0.3752, 500, 5),
    CalibrationPoint(2, 0.200, 0.5088, 500, 5),
    CalibrationPoint(2, 0.300, 0.5812, 500, 5),
    CalibrationPoint(2, 0.400, 0.6152, 500, 5),
    CalibrationPoint(2, 0.460, 0.6348, 500, 5),
    CalibrationPoint(2, 0.500, 0.6428, 500, 5),
    CalibrationPoint(2, 0.600, 0.6620, 500, 5),
    CalibrationPoint(2, 0.700, 0.6812, 500, 5),
    CalibrationPoint(2, 0.800, 0.6952, 500, 5),
    CalibrationPoint(2, 0.900, 0.7008, 500, 5),
    CalibrationPoint(2, 0.950, 0.7112, 500, 5),
    # 3-semester cumulative dropout (mean across seeds)
    CalibrationPoint(3, 0.010, 0.2132, 500, 5),
    CalibrationPoint(3, 0.025, 0.2768, 500, 5),
    CalibrationPoint(3, 0.050, 0.4396, 500, 5),
    CalibrationPoint(3, 0.075, 0.5296, 500, 5),
    CalibrationPoint(3, 0.100, 0.5924, 500, 5),
    CalibrationPoint(3, 0.200, 0.7092, 500, 5),
    CalibrationPoint(3, 0.300, 0.7764, 500, 5),
    CalibrationPoint(3, 0.400, 0.7872, 500, 5),
    CalibrationPoint(3, 0.460, 0.8028, 500, 5),
    CalibrationPoint(3, 0.500, 0.8152, 500, 5),
    CalibrationPoint(3, 0.600, 0.8208, 500, 5),
    CalibrationPoint(3, 0.700, 0.8336, 500, 5),
    CalibrationPoint(3, 0.800, 0.8412, 500, 5),
    CalibrationPoint(3, 0.900, 0.8428, 500, 5),
    CalibrationPoint(3, 0.950, 0.8512, 500, 5),
    # 4-semester cumulative dropout (mean across seeds)
    CalibrationPoint(4, 0.010, 0.3152, 500, 5),
    CalibrationPoint(4, 0.025, 0.4196, 500, 5),
    CalibrationPoint(4, 0.050, 0.5912, 500, 5),
    CalibrationPoint(4, 0.075, 0.6892, 500, 5),
    CalibrationPoint(4, 0.100, 0.7540, 500, 5),
    CalibrationPoint(4, 0.200, 0.8388, 500, 5),
    CalibrationPoint(4, 0.300, 0.8692, 500, 5),
    CalibrationPoint(4, 0.400, 0.8804, 500, 5),
    CalibrationPoint(4, 0.460, 0.8860, 500, 5),
    CalibrationPoint(4, 0.500, 0.8948, 500, 5),
    CalibrationPoint(4, 0.600, 0.8872, 500, 5),
    CalibrationPoint(4, 0.700, 0.8992, 500, 5),
    CalibrationPoint(4, 0.800, 0.8972, 500, 5),
    CalibrationPoint(4, 0.900, 0.9068, 500, 5),
    CalibrationPoint(4, 0.950, 0.9088, 500, 5),
)


# Bounds for dropout_base_rate
_MIN_BASE_RATE = 0.01  # PersonaConfig's validated lower bound
_MAX_BASE_RATE = 1.0  # PersonaConfig's validated upper bound


class CalibrationMap:
    """Maps target dropout rates to simulation parameters.

    Uses piecewise linear interpolation between known calibration points.
    Interpolates only between adjacent base-rate measurements. Multiple matching
    segments or plateaus use the lowest candidate and report the ambiguity.
    Clamps to the closest observed mean outside the measured range.
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
        if not 0.0 <= target_dropout <= 1.0:
            raise ValueError("target_dropout must be a finite value in [0, 1]")
        points = sorted(
            (p for p in self._data if p.n_semesters == n_semesters),
            key=lambda p: p.dropout_base_rate,
        )

        if len(points) < 2:
            raise ValueError(
                f"Insufficient calibration data for {n_semesters} semester(s): "
                "at least two matching points are required. Supply a measured "
                "CalibrationMap for this horizon, or run without target_dropout_range."
            )

        # 'high' describes interpolation coverage, not statistical confidence.
        min_observed = min(p.observed_dropout_rate for p in points)
        max_observed = max(p.observed_dropout_rate for p in points)
        clamped = target_dropout < min_observed or target_dropout > max_observed
        candidates = {p.dropout_base_rate for p in points
                      if p.observed_dropout_rate == target_dropout}
        exact_match = bool(candidates)
        for left, right in zip(points, points[1:]):
            lo, hi = sorted((left.observed_dropout_rate, right.observed_dropout_rate))
            if lo < target_dropout < hi:
                fraction = ((target_dropout - left.observed_dropout_rate)
                            / (right.observed_dropout_rate - left.observed_dropout_rate))
                candidates.add(left.dropout_base_rate + fraction * (
                    right.dropout_base_rate - left.dropout_base_rate
                ))

        if clamped:
            estimated_rate = min(points, key=lambda p: (
                abs(p.observed_dropout_rate - target_dropout), p.dropout_base_rate,
            )).dropout_base_rate
            mapping_status = "clamped"
        else:
            estimated_rate = min(candidates)
            mapping_status = ("multiple_matches" if len(candidates) > 1
                              else "measured" if exact_match else "interpolated")
        confidence = "low" if clamped or len(candidates) > 1 else "high"

        if clamped:
            logger.warning(
                "Target dropout %.2f is outside calibrated range [%.2f, %.2f] "
                "for %d semester(s). Estimate may be unreliable.",
                target_dropout, min_observed, max_observed, n_semesters,
            )

        estimated_rate = max(_MIN_BASE_RATE, min(_MAX_BASE_RATE, estimated_rate))

        return CalibrationEstimate(
            estimated_dropout_base_rate=estimated_rate,
            validation_dropout_rate=target_dropout,
            validation_tolerance=0.0,  # use estimate_from_range() for range-based calls
            confidence=confidence,
            n_semesters=n_semesters,
            source_data_points=len(points),
            observed_dropout_range=(float(min_observed), float(max_observed)),
            clamped=clamped,
            mapping_status=mapping_status,
            candidate_base_rates=tuple(sorted(candidates)),
            reference_population_size=(points[0].n_students
                                       if len({p.n_students for p in points}) == 1 else None),
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

        return replace(
            result,
            validation_tolerance=tolerance,
        )
