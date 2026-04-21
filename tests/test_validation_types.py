"""Tests for synthed.validation.types dataclasses."""

from __future__ import annotations

import numpy as np
import pytest

from synthed.validation.types import ValidationResult


def _minimal_kwargs(**overrides):
    base = {
        "test_name": "some_test",
        "metric": "some_metric",
        "synthetic_value": 0.42,
        "reference_value": 0.40,
    }
    base.update(overrides)
    return base


class TestValidationResultPassedContract:
    """`passed` must be strictly bool so downstream truthy-counts can't lie."""

    def test_accepts_true(self):
        r = ValidationResult(**_minimal_kwargs(passed=True))
        assert r.passed is True

    def test_accepts_false(self):
        r = ValidationResult(**_minimal_kwargs(passed=False))
        assert r.passed is False

    def test_default_is_true(self):
        r = ValidationResult(**_minimal_kwargs())
        assert r.passed is True

    def test_rejects_int_one(self):
        with pytest.raises(TypeError, match="passed must be bool"):
            ValidationResult(**_minimal_kwargs(passed=1))

    def test_rejects_int_zero(self):
        with pytest.raises(TypeError, match="passed must be bool"):
            ValidationResult(**_minimal_kwargs(passed=0))

    def test_rejects_string(self):
        with pytest.raises(TypeError, match="passed must be bool"):
            ValidationResult(**_minimal_kwargs(passed="yes"))

    def test_rejects_none(self):
        with pytest.raises(TypeError, match="passed must be bool"):
            ValidationResult(**_minimal_kwargs(passed=None))

    def test_coerces_numpy_true_to_python_bool(self):
        """numpy 2.x np.bool_ is not a bool subclass — must be coerced, not rejected."""
        r = ValidationResult(**_minimal_kwargs(passed=np.bool_(True)))
        assert r.passed is True
        assert type(r.passed) is bool  # strictly Python bool, not np.bool_

    def test_coerces_numpy_false_to_python_bool(self):
        r = ValidationResult(**_minimal_kwargs(passed=np.bool_(False)))
        assert r.passed is False
        assert type(r.passed) is bool

    def test_coerces_numpy_comparison_output(self):
        """Mirrors the production validator pattern: ``ks_p > alpha`` emits np.bool_."""
        ks_p, alpha = np.float64(0.12), 0.05
        r = ValidationResult(**_minimal_kwargs(passed=ks_p > alpha))
        assert r.passed is True
        assert type(r.passed) is bool
