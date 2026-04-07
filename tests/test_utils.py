"""Tests for shared utility modules: validation and log_config."""

from __future__ import annotations

import pytest

from synthed.utils.validation import (
    validate_range,
    validate_positive_int,
    validate_probability_distribution,
)
from synthed.utils.log_config import configure_logging


class TestValidateRange:
    """Tests for validate_range utility."""

    def test_valid_value_passes(self):
        """A value within [lo, hi] should not raise."""
        validate_range(0.5, 0.0, 1.0, "test_param")

    def test_boundary_values_pass(self):
        """Boundary values (lo and hi themselves) should pass."""
        validate_range(0.0, 0.0, 1.0, "test_param")
        validate_range(1.0, 0.0, 1.0, "test_param")

    def test_below_range_fails(self):
        """A value below lo should raise ValueError."""
        with pytest.raises(ValueError, match="test_param"):
            validate_range(-0.1, 0.0, 1.0, "test_param")

    def test_above_range_fails(self):
        """A value above hi should raise ValueError."""
        with pytest.raises(ValueError, match="test_param"):
            validate_range(1.1, 0.0, 1.0, "test_param")


class TestValidatePositiveInt:
    """Tests for validate_positive_int utility."""

    def test_positive_int_passes(self):
        """A positive integer should not raise."""
        validate_positive_int(1, "n")
        validate_positive_int(100, "n")

    def test_zero_fails(self):
        """Zero should raise ValueError."""
        with pytest.raises(ValueError, match="n"):
            validate_positive_int(0, "n")

    def test_negative_fails(self):
        """Negative integer should raise ValueError."""
        with pytest.raises(ValueError, match="n"):
            validate_positive_int(-5, "n")

    def test_float_fails(self):
        """A float should raise ValueError (not isinstance int)."""
        with pytest.raises(ValueError, match="n"):
            validate_positive_int(3.5, "n")  # type: ignore[arg-type]


class TestValidateProbabilityDistribution:
    """Tests for validate_probability_distribution utility."""

    def test_valid_distribution_passes(self):
        """A distribution summing to 1.0 should not raise."""
        validate_probability_distribution({"a": 0.5, "b": 0.3, "c": 0.2}, "dist")

    def test_near_one_passes(self):
        """A distribution summing to ~1.0 within tolerance should pass."""
        validate_probability_distribution({"a": 0.505, "b": 0.5}, "dist")

    def test_too_low_fails(self):
        """A distribution summing to 0.5 should raise ValueError."""
        with pytest.raises(ValueError, match="dist"):
            validate_probability_distribution({"a": 0.3, "b": 0.2}, "dist")

    def test_too_high_fails(self):
        """A distribution summing to 1.5 should raise ValueError."""
        with pytest.raises(ValueError, match="dist"):
            validate_probability_distribution({"a": 0.8, "b": 0.7}, "dist")


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configure_logging_default(self):
        """configure_logging() should not raise with defaults."""
        configure_logging()

    def test_configure_logging_verbose(self):
        """configure_logging(verbose=True) should not raise."""
        configure_logging(verbose=True)

