"""Tests for synthed.validation.types dataclasses."""

from __future__ import annotations

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
