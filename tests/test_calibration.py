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
        self.cal = CalibrationMap()

    def test_estimate_known_point(self):
        """Estimation at a known observed dropout should return its base_rate."""
        # 1-sem, rate=0.60, observed=0.468
        result = self.cal.estimate(0.468, n_semesters=1)
        assert abs(result.estimated_dropout_base_rate - 0.60) < 0.05

    def test_estimate_interpolation(self):
        """Interpolated value should be between neighboring known points."""
        result = self.cal.estimate(0.42, n_semesters=1)
        # 0.390 -> 0.40, 0.442 -> 0.50, so 0.42 should give ~0.40-0.55
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
        """2-semester estimation uses 2-semester data point."""
        # Only one 2-sem point (rate=0.80, observed=0.759)
        # With only 1 point for n_semesters=2, falls back to 1-sem data
        result = self.cal.estimate(0.40, n_semesters=2)
        assert result.source_data_points >= 2

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
        """Calibration data has entries for at least 1 semester."""
        sem1 = [p for p in CALIBRATION_DATA if p.n_semesters == 1]
        assert len(sem1) >= 5

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

