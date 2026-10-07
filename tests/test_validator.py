"""Tests for SyntheticDataValidator."""

import copy
import json

import pytest

from synthed.validation import SyntheticDataValidator, ReferenceStatistics


def test_outcome_rates_use_all_four_authoritative_labels():
    """Pass excludes Distinction; Fail and Withdrawn remain in the denominator."""
    outcomes = [{"student_id": str(i), "outcome": label}
                for i, label in enumerate(("Pass", "Distinction", "Fail", "Withdrawn"))]
    original = copy.deepcopy(outcomes)
    validator = SyntheticDataValidator(ReferenceStatistics(pass_rate=0.25, distinction_rate=0.25))
    rows = {r.test_name: r for r in validator._validate_correlations([], outcomes)}
    for name in ("outcome_pass_rate", "outcome_distinction_rate"):
        assert rows[name].synthetic_value == 0.25
        assert rows[name].status == "passed"
    assert outcomes == original


@pytest.mark.parametrize("bad_label", [None, "", " ", "PASS", "unknown", 42, True, [], {}])
def test_outcome_rates_require_every_label(bad_label):
    """One unknown label invalidates both configured rates instead of shrinking N."""
    outcomes = [{"student_id": str(i), "outcome": label}
                for i, label in enumerate(("Pass", "Distinction", "Fail", bad_label))]
    validator = SyntheticDataValidator(ReferenceStatistics(pass_rate=0.25, distinction_rate=0.25))
    rows = {r.test_name: r for r in validator._validate_correlations([], outcomes)}
    for name in ("outcome_pass_rate", "outcome_distinction_rate"):
        row = rows[name]
        assert row.status == "not_assessed"
        assert row.passed is False
        assert row.synthetic_value is row.statistic is row.p_value is None
        assert row.details == "reason=incomplete_outcome_labels; total=4; valid=3; invalid=1"
        json.dumps(vars(row), allow_nan=False)


@pytest.mark.parametrize("outcomes,total,valid,invalid", [
    ([], 0, 0, 0),
    ([{"student_id": "a", "outcome": "Pass"}, {"student_id": "b"}], 2, 1, 1),
])
def test_empty_or_missing_outcome_labels_are_not_zero_rates(outcomes, total, valid, invalid):
    """Empty data and omitted labels must expose missing evidence, not a measured zero."""
    validator = SyntheticDataValidator(ReferenceStatistics(pass_rate=0.4, distinction_rate=0.1))
    rows = {r.test_name: r for r in validator._validate_correlations([], outcomes)}
    for name in ("outcome_pass_rate", "outcome_distinction_rate"):
        assert rows[name].status == "not_assessed"
        assert rows[name].details == (
            f"reason=incomplete_outcome_labels; total={total}; valid={valid}; invalid={invalid}")


@pytest.mark.parametrize("pass_ref,distinction_ref,expected", [
    (None, None, set()),
    (0.0, None, {"outcome_pass_rate"}),
    (None, 0.0, {"outcome_distinction_rate"}),
])
def test_outcome_rates_only_emit_configured_checks(pass_ref, distinction_ref, expected):
    """A missing reference omits that optional check even with incomplete labels."""
    validator = SyntheticDataValidator(ReferenceStatistics(
        pass_rate=pass_ref, distinction_rate=distinction_ref))
    rows = {r.test_name: r for r in validator._validate_correlations([], [])}
    assert {name for name in rows if name.startswith("outcome_")} == expected
    for name in expected:
        assert rows[name].status == "not_assessed"


def test_observed_zero_outcome_rate_retains_strict_tolerance_boundary():
    """A valid zero is assessed; a difference of exactly 15pp still fails."""
    validator = SyntheticDataValidator(ReferenceStatistics(pass_rate=0.15, distinction_rate=0.0))
    rows = {r.test_name: r for r in validator._validate_correlations(
        [], [{"student_id": "a", "outcome": "Fail"}])}
    assert rows["outcome_pass_rate"].synthetic_value == 0.0
    assert rows["outcome_pass_rate"].status == "failed"
    assert rows["outcome_distinction_rate"].status == "passed"


@pytest.mark.parametrize("students", [[], [{}], [{"backstory": None}], [{"backstory": ""}],
                                      [{"backstory": " \t\n"}], [{"backstory": 42}],
                                      [{"backstory": []}], [{"backstory": {}}]])
def test_absent_backstories_emit_two_unassessed_checks(students):
    """Absence discloses coverage and makes no claim about whether an LLM ran."""
    students = [{"student_id": str(i), "age": 30, "gender": "female", "prior_gpa": 2.5,
                 "socioeconomic_level": "middle", **s} for i, s in enumerate(students)]
    report = SyntheticDataValidator().validate_all(students, [])
    rows = {r["test"]: r for r in report["results"]}
    for name in ("backstory_non_empty_rate", "backstory_attribute_relevance"):
        row = rows[name]
        assert row["status"] == "not_assessed"
        assert row["passed"] is False
        assert row["synthetic"] is row["statistic"] is row["p_value"] is None
        assert row["details"] == f"reason=no_nonempty_backstories; total={len(students)}; nonempty=0"
    assert report["summary"]["assessment_complete"] is False
    json.dumps(report, allow_nan=False)


def test_partial_backstory_coverage_uses_the_whole_cohort():
    """Missing/non-text rows count in coverage; relevance uses only actual text."""
    students = [{"backstory": "I work for my career.", "employment_intensity": 1.0},
                {}, {"backstory": "  "}, {"backstory": 42}]
    rows = {r.test_name: r for r in SyntheticDataValidator()._validate_backstories(students)}
    assert rows["backstory_non_empty_rate"].synthetic_value == 0.25
    assert rows["backstory_non_empty_rate"].status == "failed"
    assert "1/4" in rows["backstory_non_empty_rate"].details
    assert rows["backstory_attribute_relevance"].synthetic_value == 1.0
    assert rows["backstory_attribute_relevance"].status == "passed"
    assert "1/1" in rows["backstory_attribute_relevance"].details


class TestSyntheticDataValidator:
    def setup_method(self):
        self.validator = SyntheticDataValidator()

    def test_early_attrition_uses_full_simulation_horizon(self):
        """Week 20 is early in a 56-week run despite a short final-term history."""
        outcomes = [{"student_id": "drop", "has_dropped_out": True, "dropout_week": 20}]
        results = self.validator._validate_temporal(
            {"drop": [0.4, 0.3]}, outcomes, total_weeks=56,
        )
        timing = next(r for r in results if r.test_name == "dropout_early_attrition")
        assert timing.synthetic_value == 1.0
        assert timing.passed


    def test_validate_all_returns_report_structure(self):
        validator = SyntheticDataValidator()
        students = [
            {"student_id": f"s{i}", "age": 25 + i, "gender": "female",
             "employment_intensity": 0.67 if i % 2 == 0 else 0.0, "prior_gpa": 2.5,
             "socioeconomic_level": "middle"}
            for i in range(30)
        ]
        outcomes = [
            {"student_id": f"s{i}", "has_dropped_out": i < 10,
             "dropout_week": 5 if i < 10 else None,
             "final_dropout_phase": 5 if i < 10 else 0,
             "final_engagement": 0.3 if i < 10 else 0.7}
            for i in range(30)
        ]
        report = validator.validate_all(students, outcomes)
        assert "summary" in report
        assert "results" in report
        assert "total_tests" in report["summary"]
        assert "passed" in report["summary"]
        assert "overall_quality" in report["summary"]

    def test_proportion_z_test_symmetric(self):
        z1, p1 = SyntheticDataValidator._proportion_z_test(0.55, 0.50, 100)
        z2, p2 = SyntheticDataValidator._proportion_z_test(0.45, 0.50, 100)
        assert abs(abs(z1) - abs(z2)) < 1e-6
        assert abs(p1 - p2) < 1e-6

    def test_quality_grade_thresholds(self):
        assert "A" in SyntheticDataValidator._quality_grade(0.95)
        assert "B" in SyntheticDataValidator._quality_grade(0.80)
        assert "C" in SyntheticDataValidator._quality_grade(0.65)
        assert "D" in SyntheticDataValidator._quality_grade(0.45)
        assert "F" in SyntheticDataValidator._quality_grade(0.20)

    def test_effective_alpha_small_n_unchanged(self):
        assert self.validator._effective_alpha(200) == 0.05
        assert self.validator._effective_alpha(500) == 0.05

    def test_effective_alpha_large_n_decreases(self):
        alpha_10k = self.validator._effective_alpha(10000)
        assert alpha_10k < 0.05
        assert abs(alpha_10k - 0.01) < 0.005  # approximately 0.01

    def test_effective_alpha_minimum_bound(self):
        assert self.validator._effective_alpha(10_000_000) >= 0.001


class TestDropoutRangeValidation:
    """Tests for range-based dropout validation."""

    def _make_data(self, n=30, n_dropout=10):
        students = [
            {"student_id": f"s{i}", "age": 25 + i, "gender": "female",
             "employment_intensity": 0.67 if i % 2 == 0 else 0.0, "prior_gpa": 2.5,
             "socioeconomic_level": "middle"}
            for i in range(n)
        ]
        outcomes = [
            {"student_id": f"s{i}", "has_dropped_out": i < n_dropout,
             "dropout_week": 5 if i < n_dropout else None,
             "final_engagement": 0.3 if i < n_dropout else 0.7}
            for i in range(n)
        ]
        return students, outcomes

    def test_dropout_range_pass(self):
        """Observed dropout within range passes."""
        ref = ReferenceStatistics(dropout_range=(0.20, 0.50))
        v = SyntheticDataValidator(reference=ref)
        students, outcomes = self._make_data(n=30, n_dropout=10)  # ~33%
        report = v.validate_all(students, outcomes)
        dropout_result = next(
            r for r in report["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result["passed"] is True
        assert dropout_result["metric"] == "Range check"

    def test_dropout_range_fail(self):
        """Observed dropout outside range fails."""
        ref = ReferenceStatistics(dropout_range=(0.60, 0.80))
        v = SyntheticDataValidator(reference=ref)
        students, outcomes = self._make_data(n=30, n_dropout=10)  # ~33%
        report = v.validate_all(students, outcomes)
        dropout_result = next(
            r for r in report["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result["passed"] is False

    def test_dropout_range_backward_compat(self):
        """Default uses range check; explicit None uses z-test."""
        # Default now has dropout_range=(0.20, 0.45) → range check
        ref_default = ReferenceStatistics()
        v_default = SyntheticDataValidator(reference=ref_default)
        students, outcomes = self._make_data(n=30, n_dropout=10)
        report = v_default.validate_all(students, outcomes)
        dropout_result = next(
            r for r in report["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result["metric"] == "Range check"

        # Explicit dropout_range=None → z-test
        ref_ztest = ReferenceStatistics(dropout_range=None)
        v_ztest = SyntheticDataValidator(reference=ref_ztest)
        report2 = v_ztest.validate_all(students, outcomes)
        dropout_result2 = next(
            r for r in report2["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result2["metric"] == "Proportion Z-test"
