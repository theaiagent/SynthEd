"""Tests for SyntheticDataValidator."""

import copy
import json
from fractions import Fraction

import pytest
import numpy as np

from synthed.validation import SyntheticDataValidator, ReferenceStatistics


@pytest.mark.parametrize("seed", [42, 7, 123])
def test_gpa_decision_is_independent_of_call_history(seed):
    """Repeated/reordered inputs match a fresh validator despite other sample sizes."""
    reference = ReferenceStatistics()
    sample = np.clip(np.random.default_rng(seed).normal(3.03, 0.75, 100), 0, 4)
    students = [{"prior_gpa": float(g)} for g in sample]
    validator = SyntheticDataValidator(reference, seed=seed)
    for _ in range(20):
        row = next(r for r in validator._validate_academic(students, [])
                   if r.test_name == "gpa_distribution")
        assert (row.statistic, row.p_value, row.status) == (0.0, 1.0, "passed")
        reversed_row = next(r for r in validator._validate_academic(students[::-1], [])
                            if r.test_name == "gpa_distribution")
        assert (reversed_row.statistic, reversed_row.p_value, reversed_row.status) == (0.0, 1.0, "passed")
        assert reversed_row.synthetic_value == pytest.approx(row.synthetic_value)
        validator._validate_academic([{"prior_gpa": 2.0}] * 7, [])
    fresh_row = next(r for r in SyntheticDataValidator(reference, seed=seed)._validate_academic(students, [])
                     if r.test_name == "gpa_distribution")
    assert (fresh_row.statistic, fresh_row.p_value, fresh_row.status) == (0.0, 1.0, "passed")


def test_gpa_reference_provenance_is_reported():
    """The measured row identifies the clipped reference and its actual seed/count."""
    row = SyntheticDataValidator(seed=7)._validate_academic([{"prior_gpa": 2.0}] * 11, [])[0]
    assert "reference=clipped_normal; seed=7; reference_n=11" in row.details
    assert "GPA mean: synth=2.00" in row.details


@pytest.mark.parametrize("seed", [42, 7, 123])
def test_gpa_reference_clips_endpoints_and_preserves_global_rng(seed):
    """The common sample keeps clipping and never reseeds NumPy's global RNG."""
    before = np.random.get_state()
    validator = SyntheticDataValidator(ReferenceStatistics(gpa_mean=2.0, gpa_std=100.0), seed=seed)
    sample = validator._gpa_reference_sample(100)
    after = np.random.get_state()
    assert before[0] == after[0]
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]
    expected = np.clip(np.random.default_rng(seed).normal(2.0, 100.0, 100), 0, 4)
    np.testing.assert_array_equal(sample, expected)
    np.testing.assert_array_equal(validator._gpa_reference_sample(100), sample)
    assert sample.min() == 0.0
    assert sample.max() == 4.0


def test_unassessed_gpa_does_not_draw_a_reference(monkeypatch):
    """Empty and non-finite observations retain N/A without attempting a draw."""
    validator = SyntheticDataValidator()

    def unexpected_draw(n):
        """Fail if reference generation is attempted for an undefined comparison."""
        raise AssertionError("Unassessed GPA must not draw a reference")

    monkeypatch.setattr(validator, "_gpa_reference_sample", unexpected_draw)
    for students in ([], [{"prior_gpa": float("nan")}]):
        row = validator._validate_academic(students, [])[0]
        assert row.status == "not_assessed"
        assert row.statistic is row.p_value is None


@pytest.mark.parametrize("seed", [-1, 0.5, "42"])
def test_invalid_gpa_seed_is_rejected_at_construction(seed):
    """Retain NumPy's eager seed validation rather than delaying failure to GPA."""
    with pytest.raises((ValueError, TypeError)):
        SyntheticDataValidator(seed=seed)


@pytest.mark.parametrize("expected,observed,p_value", [
    (0.0, 0.0, 1.0), (0.0, 0.5, 0.0), (1.0, 1.0, 1.0), (1.0, 0.5, 0.0),
])
def test_boundary_proportion_uses_exact_null_distribution(expected, observed, p_value):
    """A degenerate binomial null cannot assign positive probability to a mismatch."""
    assert SyntheticDataValidator._proportion_z_test(observed, expected, 20) == (None, p_value)


def test_empty_proportion_is_unassessed_and_interior_formula_is_preserved():
    """No sample has no statistic; ordinary interior proportions retain the Z-test."""
    method = SyntheticDataValidator._proportion_z_test
    assert method(0.0, 0.5, 0) == (None, None)
    z, p_value = method(0.55, 0.5, 100)
    assert z == pytest.approx(1.0)
    assert p_value == pytest.approx(0.31731050786291415)


@pytest.mark.parametrize("field", ["p_observed", "p_expected"])
@pytest.mark.parametrize("bad_value", [-0.01, 1.01, float("nan"), float("inf"),
                                      -float("inf"), "0.5", [], {}, 1j, True, 10**400])
def test_proportion_helper_rejects_invalid_values_before_empty_sample(field, bad_value):
    """Invalid scalars must fail even when no sample could otherwise be assessed."""
    kwargs = {"p_observed": 0.5, "p_expected": 0.5, "n": 0, field: bad_value}
    with pytest.raises(ValueError, match=field):
        SyntheticDataValidator._proportion_z_test(**kwargs)


@pytest.mark.parametrize("n", [-1, 1.5, 20.0, True, np.bool_(False), None, "20"])
def test_proportion_helper_requires_nonnegative_integral_sample_size(n):
    """Bool, fractional and nonnumeric counts must not produce an assessment."""
    with pytest.raises(ValueError, match="n"):
        SyntheticDataValidator._proportion_z_test(0.5, 0.5, n)


def test_numpy_scalar_proportion_and_integral_count_remain_supported():
    """Scientific callers can supply real NumPy scalars and integer sample counts."""
    z, p_value = SyntheticDataValidator._proportion_z_test(
        np.float64(0.55), np.float32(0.5), np.int64(100))
    assert z == pytest.approx(1.0)
    assert p_value == pytest.approx(0.31731050786291415)


def test_fraction_proportions_use_numeric_interior_calculation():
    """Accepted real scalars must reach the normal calculation without object dtype."""
    z, p_value = SyntheticDataValidator._proportion_z_test(Fraction(11, 20), Fraction(1, 2), 100)
    assert z == pytest.approx(1.0)
    assert p_value == pytest.approx(0.31731050786291415)


@pytest.mark.parametrize("proportion", [Fraction(0), Fraction(1, 2), Fraction(1)])
def test_fraction_references_reach_callers_and_strict_json_without_mutation(proportion):
    """Calculation, formatting and report JSON support accepted Real references."""
    reference = ReferenceStatistics(employment_rate=proportion, dropout_rate=proportion,
                                    pass_rate=proportion, distinction_rate=proportion,
                                    dropout_range=None)
    students = [{"student_id": str(i), "age": 20 + i,
                 "gender": "male" if i < 11 else "female",
                 "employment_intensity": float(i < 10)} for i in range(20)]
    outcomes = [{"student_id": str(i), "has_dropped_out": i < 10,
                 "final_dropout_phase": 5 if i < 10 else 0,
                 "outcome": "Withdrawn" if i < 10 else "Pass"} for i in range(20)]
    validator = SyntheticDataValidator(reference)
    direct_rows = {r.test_name: r for r in validator._validate_demographics(students)
                   + validator._validate_academic([], outcomes)}
    for name in ("employment_rate", "dropout_rate"):
        row = direct_rows[name]
        assert row.synthetic_value == 0.5
        assert row.statistic == (0.0 if proportion == Fraction(1, 2) else None)
        assert row.p_value == float(proportion == Fraction(1, 2))
    report = validator.validate_all(students, outcomes)
    json.dumps(report, allow_nan=False)
    for name in ("employment_rate", "dropout_rate", "pass_rate", "distinction_rate"):
        assert getattr(reference, name) is proportion
    for row in report["results"]:
        if row["reference"] is not None:
            assert isinstance(row["reference"], float)


@pytest.mark.parametrize("expected", [0.0, 1.0])
def test_proportion_callers_reject_impossible_boundary(expected):
    """Both observed 50% proportions must fail against a 0% or 100% null."""
    validator = SyntheticDataValidator(ReferenceStatistics(
        employment_rate=expected, dropout_rate=expected, dropout_range=None))
    students = [{"age": 20 + i, "gender": "male" if i < 11 else "female",
                 "employment_intensity": 1.0 if i < 10 else 0.0} for i in range(20)]
    outcomes = [{"has_dropped_out": i < 10} for i in range(20)]
    rows = {r.test_name: r for r in validator._validate_demographics(students)
            + validator._validate_academic([], outcomes)}
    for name in ("employment_rate", "dropout_rate"):
        row = rows[name]
        assert row.synthetic_value == 0.5
        assert row.statistic is None
        assert row.p_value == 0.0
        assert row.status == "failed"
        assert row.metric == "Exact binomial boundary"


@pytest.mark.parametrize("expected", [0.0, 1.0])
def test_proportion_callers_accept_complete_boundary_agreement(expected):
    """Matching boundary data is assessed and passes without a fabricated Z-score."""
    validator = SyntheticDataValidator(ReferenceStatistics(
        employment_rate=expected, dropout_rate=expected, dropout_range=None))
    students = [{"age": 20 + i, "gender": "male" if i < 11 else "female",
                 "employment_intensity": expected} for i in range(20)]
    outcomes = [{"has_dropped_out": bool(expected)} for _ in range(20)]
    rows = {r.test_name: r for r in validator._validate_demographics(students)
            + validator._validate_academic([], outcomes)}
    for name in ("employment_rate", "dropout_rate"):
        assert rows[name].synthetic_value == expected
        assert rows[name].statistic is None
        assert rows[name].p_value == 1.0
        assert rows[name].status == "passed"
        assert rows[name].metric == "Exact binomial boundary"


@pytest.mark.parametrize("expected", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("dropout_range", [None, (0.2, 0.5)])
def test_empty_proportion_callers_report_no_assessment(expected, dropout_range):
    """Empty employment/dropout inputs disclose zero coverage on each metric path."""
    validator = SyntheticDataValidator(ReferenceStatistics(
        employment_rate=expected, dropout_rate=expected, dropout_range=dropout_range))
    rows = {r.test_name: r for r in validator._validate_demographics([])
            + validator._validate_academic([], [])}
    for name in ("employment_rate", "dropout_rate"):
        row = rows[name]
        assert row.status == "not_assessed"
        assert row.synthetic_value is row.statistic is row.p_value is None
        assert row.details == "reason=empty_sample; n=0"
    boundary_metric = "Exact binomial boundary" if expected in (0.0, 1.0) else "Proportion Z-test"
    assert rows["employment_rate"].metric == boundary_metric
    assert rows["dropout_rate"].metric == ("Range check" if dropout_range else boundary_metric)
    json.dumps([vars(r) for r in rows.values()], allow_nan=False)


@pytest.mark.parametrize("field", ["employment_rate", "dropout_rate"])
@pytest.mark.parametrize("bad_value", [-0.1, float("nan")])
def test_proportion_helper_rechecks_mutated_reference(field, bad_value):
    """A mutable reference must not bypass the helper's probability validation."""
    reference = ReferenceStatistics(dropout_range=None)
    setattr(reference, field, bad_value)
    validator = SyntheticDataValidator(reference)
    with pytest.raises(ValueError, match="p_expected"):
        if field == "employment_rate":
            validator._validate_demographics([{"age": 30, "gender": "male"}])
        else:
            validator._validate_academic([], [{"has_dropped_out": True}])


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
