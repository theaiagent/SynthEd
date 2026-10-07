"""Tests for synthed.validation.types dataclasses."""

from __future__ import annotations

import numpy as np
import pytest

from synthed.validation.types import ReferenceStatistics, ValidationResult


@pytest.mark.parametrize("field", ["employment_rate", "dropout_rate", "pass_rate", "distinction_rate"])
@pytest.mark.parametrize("bad_value", [-0.01, 1.01, float("nan"), float("inf"), -float("inf"),
                                      "0.5", [], {}, 1j, True, 10**400])
def test_reference_proportions_reject_invalid_scalar(field, bad_value):
    """Configured proportions must be finite real probabilities with field context."""
    with pytest.raises(ValueError, match=field):
        ReferenceStatistics(**{field: bad_value})


@pytest.mark.parametrize("field", ["employment_rate", "dropout_rate"])
def test_required_reference_proportions_cannot_be_none(field):
    """Only pass and distinction references support the unconfigured None state."""
    with pytest.raises(ValueError, match=field):
        ReferenceStatistics(**{field: None})


def test_reference_proportion_endpoints_and_optional_none_remain_valid():
    """Zero/one are valid nulls; optional references retain explicit omission."""
    reference = ReferenceStatistics(employment_rate=0.0, dropout_rate=1.0,
                                    pass_rate=None, distinction_rate=None, dropout_range=None)
    assert reference.employment_rate == 0.0
    assert reference.dropout_rate == 1.0
    assert reference.pass_rate is reference.distinction_rate is None


def test_invalid_reference_json_and_pipeline_config_fail_with_field_context(tmp_path):
    """External JSON/config reconstruction uses the same proportion contract."""
    from synthed.pipeline_config import PipelineConfig

    path = tmp_path / "reference.json"
    path.write_text('{"employment_rate": "0.5"}', encoding="utf-8")
    with pytest.raises(ValueError, match="employment_rate"):
        ReferenceStatistics.from_json(str(path))
    with pytest.raises(ValueError, match="dropout_rate"):
        PipelineConfig.from_dict({"reference_stats": {"dropout_rate": -0.1}})


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


class TestValidationAssessmentStatus:
    """Undefined measurements must carry a reason and never become a score."""

    def test_not_assessed_has_null_values_and_false_pass_flag(self):
        row = ValidationResult("constant", "Pearson r", None, 0.3,
                               passed=False, details="constant_input; n=20",
                               status="not_assessed")
        assert row.status == "not_assessed"
        assert row.passed is False

    @pytest.mark.parametrize("field", ["synthetic_value", "reference_value", "statistic", "p_value"])
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
    def test_rejects_non_finite_measurements(self, field, value):
        with pytest.raises(ValueError, match="finite"):
            ValidationResult(**_minimal_kwargs(**{field: value}))

    @pytest.mark.parametrize("status,passed", [("passed", False), ("failed", True),
                                               ("not_assessed", True), ("unknown", False)])
    def test_rejects_inconsistent_status(self, status, passed):
        with pytest.raises(ValueError):
            ValidationResult(**_minimal_kwargs(status=status, passed=passed))

    def test_not_assessed_requires_reason_and_no_measurement(self):
        with pytest.raises(ValueError):
            ValidationResult("missing", "r", None, None, passed=False, status="not_assessed")
        with pytest.raises(ValueError):
            ValidationResult("missing", "r", 0.0, None, passed=False,
                             details="insufficient_pairs", status="not_assessed")

    def test_coerces_numpy_comparison_output(self):
        """Mirrors the production validator pattern: ``ks_p > alpha`` emits np.bool_."""
        ks_p, alpha = np.float64(0.12), 0.05
        r = ValidationResult(**_minimal_kwargs(passed=ks_p > alpha))
        assert r.passed is True
        assert type(r.passed) is bool
