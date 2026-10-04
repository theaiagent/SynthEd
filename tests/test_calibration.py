"""Tests for CalibrationMap interpolation and estimation."""

import pytest

from synthed.calibration import (
    CalibrationMap,
    CalibrationPoint,
    CALIBRATION_DATA,
    _MIN_BASE_RATE,
    _MAX_BASE_RATE,
)


class TestCalibrationMap:
    def setup_method(self):
        """Use a fixed monotone fixture so unit tests do not freeze measured rates."""
        self.cal = CalibrationMap(data=(
            CalibrationPoint(1, 0.20, 0.248, 500, 5),
            CalibrationPoint(1, 0.40, 0.363, 500, 5),
            CalibrationPoint(1, 0.60, 0.420, 500, 5),
            CalibrationPoint(1, 0.90, 0.482, 500, 5),
        ))

    def test_nonmonotone_curve_uses_adjacent_base_rate_segments(self):
        """Do not invent segments by sorting noisy observations before inversion."""
        cal = CalibrationMap(data=(
            CalibrationPoint(4, 0.20, 0.80, 500, 5),
            CalibrationPoint(4, 0.40, 0.92, 500, 5),
            CalibrationPoint(4, 0.60, 0.88, 500, 5),
            CalibrationPoint(4, 0.80, 0.96, 500, 5),
        ))
        result = cal.estimate(0.90, 4)
        assert result.candidate_base_rates == pytest.approx((0.3666666666666667, 0.50, 0.65))
        assert result.estimated_dropout_base_rate == pytest.approx(0.3666666666666667)
        assert result.mapping_status == "multiple_matches"
        assert result.confidence == "low"

    def test_flat_segment_reports_ambiguous_measured_matches(self):
        """An observed plateau uses the lowest matching base without division by zero."""
        cal = CalibrationMap(data=(
            CalibrationPoint(2, 0.10, 0.30, 500, 5),
            CalibrationPoint(2, 0.20, 0.30, 500, 5),
        ))
        result = cal.estimate(0.30, 2)
        assert result.estimated_dropout_base_rate == 0.10
        assert result.mapping_status == "multiple_matches"
        assert result.candidate_base_rates == (0.10, 0.20)

    @pytest.mark.parametrize("target", [float("nan"), float("inf"), -0.1, 1.1])
    def test_invalid_target_raises(self, target):
        """Invalid targets cannot produce nonfinite simulation parameters."""
        with pytest.raises(ValueError, match="target_dropout"):
            self.cal.estimate(target)

    def test_estimate_known_point(self):
        """Estimation at a known observed dropout should return its base_rate."""
        # 1-sem, rate=0.60, observed=0.420
        result = self.cal.estimate(0.420, n_semesters=1)
        assert abs(result.estimated_dropout_base_rate - 0.60) < 0.05

    def test_estimate_interpolation(self):
        """Interpolated value should be between neighboring known points."""
        result = self.cal.estimate(0.38, n_semesters=1)
        # 0.363 -> 0.40, 0.400 -> 0.50, so 0.38 should give ~0.40-0.55
        assert 0.35 <= result.estimated_dropout_base_rate <= 0.55
        assert result.confidence == "high"

    def test_estimate_monotonic(self):
        """Higher target dropout should produce higher estimated base_rate."""
        low = self.cal.estimate(0.30, n_semesters=1)
        high = self.cal.estimate(0.45, n_semesters=1)
        assert high.estimated_dropout_base_rate > low.estimated_dropout_base_rate

    def test_estimate_clamp_low(self):
        """Target below calibrated range is clamped, confidence='low'."""
        result = self.cal.estimate(0.10, n_semesters=1)
        assert result.estimated_dropout_base_rate >= _MIN_BASE_RATE
        assert result.confidence == "low"

    def test_estimate_clamp_high(self):
        """Target above calibrated range is clamped, confidence='low'."""
        result = self.cal.estimate(0.99, n_semesters=1)
        assert result.estimated_dropout_base_rate <= _MAX_BASE_RATE
        assert result.confidence == "low"

    def test_estimate_multi_semester(self):
        """Identical targets use the curve for the requested horizon."""
        cal = CalibrationMap(data=(
            CalibrationPoint(1, 0.20, 0.20, 500, 5),
            CalibrationPoint(1, 0.60, 0.40, 500, 5),
            CalibrationPoint(2, 0.10, 0.20, 500, 5),
            CalibrationPoint(2, 0.30, 0.40, 500, 5),
        ))
        assert cal.estimate(0.30, 1).estimated_dropout_base_rate == pytest.approx(0.40)
        assert cal.estimate(0.30, 2).estimated_dropout_base_rate == pytest.approx(0.20)

    @pytest.mark.parametrize("n_semesters", [2, 4, 8])
    def test_missing_horizon_never_uses_single_semester_data(self, n_semesters):
        """Incomplete horizon data fail explicitly instead of borrowing a curve."""
        cal = CalibrationMap(data=(
            CalibrationPoint(1, 0.20, 0.20, 500, 5),
            CalibrationPoint(1, 0.60, 0.40, 500, 5),
            CalibrationPoint(2, 0.46, 0.68, 500, 5),
        ))
        with pytest.raises(ValueError, match=f"{n_semesters} semester"):
            cal.estimate_from_range((0.30, 0.45), n_semesters)

    def test_low_base_rates_are_not_raised_above_measured_value(self):
        """Long-horizon targeting can use the persona model's lower domain."""
        cal = CalibrationMap(data=(
            CalibrationPoint(4, 0.01, 0.30, 500, 5),
            CalibrationPoint(4, 0.05, 0.50, 500, 5),
        ))
        result = cal.estimate_from_range((0.30, 0.50), 4)
        assert result.estimated_dropout_base_rate == pytest.approx(0.03)
        assert result.observed_dropout_range == (0.30, 0.50)
        assert result.clamped is False

    def test_clamping_is_preserved_in_range_estimate(self):
        """Callers can identify estimates outside the measured response range."""
        cal = CalibrationMap(data=(
            CalibrationPoint(4, 0.01, 0.30, 500, 5),
            CalibrationPoint(4, 0.05, 0.50, 500, 5),
        ))
        result = cal.estimate_from_range((0.10, 0.20), 4)
        assert result.clamped is True
        assert result.confidence == "low"
        assert result.observed_dropout_range == (0.30, 0.50)
        assert result.estimated_dropout_base_rate == pytest.approx(0.01)

    def test_estimate_from_range_basic(self):
        """Range-based estimation uses midpoint and computes tolerance."""
        result = self.cal.estimate_from_range((0.40, 0.50), n_semesters=1)
        assert abs(result.validation_dropout_rate - 0.45) < 1e-10
        assert abs(result.validation_tolerance - 0.05) < 1e-10

    def test_estimate_from_range_invalid(self):
        """Invalid range raises ValueError."""
        with pytest.raises(ValueError):
            self.cal.estimate_from_range((0.50, 0.30))  # lower >= upper

    def test_estimate_from_range_out_of_bounds(self):
        """Range outside (0, 1) raises ValueError."""
        with pytest.raises(ValueError):
            self.cal.estimate_from_range((0.0, 0.50))  # lower must be > 0
        with pytest.raises(ValueError):
            self.cal.estimate_from_range((-0.1, 0.50))
        with pytest.raises(ValueError):
            self.cal.estimate_from_range((0.40, 1.0))  # upper must be < 1

    def test_calibration_data_sorted_by_semester(self):
        """Every built-in horizon has the same measured base-rate grid."""
        grids = [{p.dropout_base_rate for p in CALIBRATION_DATA if p.n_semesters == sem}
                 for sem in (1, 2, 3, 4)]
        assert len(grids[0]) >= 5
        assert all(grid == grids[0] for grid in grids)

    def test_builtin_curves_match_saved_measurements(self):
        """Published means derive from complete seed runs and actual dropout counts."""
        import json
        from pathlib import Path

        data = json.loads((Path(__file__).resolve().parents[1] /
                           "docs/measurements/dropout-horizons.json").read_text())
        for point in CALIBRATION_DATA:
            runs = [r for r in data["runs"] if r["base_rate"] == point.dropout_base_rate]
            assert sorted(r["seed"] for r in runs) == sorted(data["seeds"])
            assert len(runs) == point.seed_count
            assert data["n_students"] == point.n_students
            dropped = sum(sum(s["dropped"] for s in r["semesters"][:point.n_semesters])
                          for r in runs)
            assert point.observed_dropout_rate == pytest.approx(
                dropped / (point.n_students * point.seed_count)
            )

    def test_custom_calibration_data(self):
        """CalibrationMap accepts custom calibration points."""
        custom = (
            CalibrationPoint(1, 0.30, 0.20, 100, 1),
            CalibrationPoint(1, 0.70, 0.50, 100, 1),
        )
        cal = CalibrationMap(data=custom)
        result = cal.estimate(0.35, n_semesters=1)
        assert 0.30 <= result.estimated_dropout_base_rate <= 0.70
        assert result.confidence == "high"
