"""Tests for SyntheticDataValidator."""

import copy
import json
from enum import Enum
from fractions import Fraction

import pytest
import numpy as np

from synthed.validation import SyntheticDataValidator, ReferenceStatistics


@pytest.mark.parametrize("cohort,n,minimum,reference,average,passed", [
    ("grouped", 2, 2.0, 1.0, 2.0, True),
    ("grouped", 500, 500.0, 2.0, 500.0, True),
    ("unique", 499, 1.0, 1.0, 1.0, True),
    ("unique", 500, 1.0, 2.0, 1.0, False),
    ("mixed", 500, 1.0, 2.0, 250.0, True),
])
def test_privacy_copy_preserves_grouping_policy(cohort, n, minimum, reference, average, passed):
    """Limit the claim while retaining both sides of N=500 and the average-group fallback."""
    students = [{"age": 30, "gender": "female", "socioeconomic_level": "middle"} for _ in range(n)]
    if cohort == "unique":
        # Dictionary grouping contrast only; these are not valid-persona population claims.
        for i, student in enumerate(students):
            student["age"] = i
    elif cohort == "mixed":
        students[0]["age"] = 31
    original = copy.deepcopy(students)
    row, = SyntheticDataValidator()._validate_privacy(students)
    assert (row.test_name, row.metric) == ("k_anonymity", "Minimum k")
    assert (row.synthetic_value, row.reference_value, row.passed) == (minimum, reference, passed)
    assert row.status == ("passed" if passed else "failed")
    assert row.statistic is None and row.p_value is None
    assert row.details == (
        f"Min k={int(minimum)}, Avg k={average:.1f} (N={n}). "
        "Quasi-identifiers: age, gender, socioeconomic_level. "
        "Informational grouping check only; it does not verify input provenance, "
        "formal anonymity, or absence of re-identification risk. "
        "Custom inputs and LLM-generated text require a separate privacy assessment."
    )
    assert "privacy risk is inherently zero" not in row.details
    assert "has no real individuals" not in row.details
    assert students == original
    json.dumps(vars(row), allow_nan=False)


def test_privacy_copy_keeps_empty_population_unassessed():
    """The copy repair does not invent a privacy result for an empty cohort."""
    row, = SyntheticDataValidator()._validate_privacy([])
    assert (row.status, row.passed, row.synthetic_value, row.reference_value) == (
        "not_assessed", False, None, None)
    assert row.details == "insufficient_population; n=0"


def _dropout_trend(histories, outcomes):
    """Select the single trend row from a requested temporal assessment."""
    matches = [r for r in SyntheticDataValidator()._validate_temporal(histories, outcomes)
               if r.test_name == "dropout_negative_trend_rate"]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize("include_retained", [False, True])
def test_dropout_trend_uses_assessable_denominator(include_retained):
    """Three short histories cannot dilute the one assessable decline."""
    histories = {"d0": [.8, .6, .4, .2], "d1": [.8], "d2": [.7], "d3": [.6]}
    outcomes = [{"student_id": key, "has_dropped_out": True} for key in histories]
    if include_retained:
        histories["r"] = [.8] * 4
        outcomes.append({"student_id": "r", "has_dropped_out": False})
    row = _dropout_trend(histories, outcomes)
    assert (row.synthetic_value, row.reference_value, row.passed, row.status) == (1.0, .50, True, "passed")
    for text in ("total_dropout=4", "with_history=4", "assessable=1", "short_or_missing=3",
                 "invalid_history=0", "negative=1", "coverage=0.2500", "threshold=0.50 (model policy)"):
        assert text in row.details


@pytest.mark.parametrize("history,expected", [([], None), ([.8], None), ([.8, .6, .4], None),
                                               ([.8, .6, .4, .2], 1.0), ([.5] * 4, 0.0),
                                               ([.9, .8, .7, .6, .5], 1.0)])
def test_dropout_trend_minimum_history_and_ties(history, expected):
    """Four finite observations are required; ties and odd-length splits keep their meaning."""
    row = _dropout_trend({"d": history}, [{"student_id": "d", "has_dropped_out": True}])
    assert row.synthetic_value == expected
    assert row.reference_value == .5
    assert row.passed is (expected is not None and expected >= .5)
    if expected is None:
        assert row.status == "not_assessed"
        assert row.statistic is None and row.p_value is None
        assert "reason=no_assessable_history" in row.details
    else:
        assert row.status == ("passed" if expected >= .5 else "failed")


def test_dropout_trend_exact_half_passes():
    """The displayed reference equals the preserved inclusive decision threshold."""
    histories = {"decline": [.8, .6, .4, .2], "tie": [.5] * 4}
    outcomes = [{"student_id": key, "has_dropped_out": True} for key in histories]
    row = _dropout_trend(histories, outcomes)
    assert (row.synthetic_value, row.reference_value, row.passed) == (.5, .5, True)
    assert "negative=1" in row.details and "coverage=1.0000" in row.details


def test_dropout_trend_counts_missing_and_excludes_unmatched_and_retained():
    """Coverage includes missing outcomes; unrelated or retained histories cannot supply trend data."""
    histories = {"d": [.8, .6, .4, .2], "empty": [], "short": [.8],
                 "unmatched": [.9, .7, .3, .1], "r": [float("nan")] * 4}
    outcomes = [{"student_id": key, "has_dropped_out": True} for key in ("d", "empty", "short", "missing")]
    outcomes.append({"student_id": "r", "has_dropped_out": False})
    row = _dropout_trend(histories, outcomes)
    assert row.passed is True and row.synthetic_value == 1.0
    for text in ("total_dropout=4", "with_history=2", "assessable=1", "short_or_missing=3",
                 "invalid_history=0", "coverage=0.2500"):
        assert text in row.details


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("long_history", [False, True])
def test_dropout_trend_nonfinite_long_history_blocks_whole_assessment(bad, long_history):
    """A bad assessable-length history is reported, never silently dropped from the rate."""
    histories = {"good": [.8, .6, .4, .2], "bad": [.8, bad, .4, .2] if long_history else [bad]}
    outcomes = [{"student_id": key, "has_dropped_out": True} for key in histories]
    row = _dropout_trend(histories, outcomes)
    assert "total_dropout=2" in row.details and "coverage=0.5000" in row.details
    assert "assessable=1" in row.details and "negative=1" in row.details
    assert f"invalid_history={int(long_history)}" in row.details
    if long_history:
        assert (row.status, row.passed, row.synthetic_value, row.statistic, row.p_value) == (
            "not_assessed", False, None, None, None)
        assert "short_or_missing=0" in row.details and "reason=non_finite_history" in row.details
    else:
        assert row.status == "passed" and row.synthetic_value == 1.0
        assert "short_or_missing=1" in row.details


@pytest.mark.parametrize("outcomes", [[], [{"student_id": "r", "has_dropped_out": False}]])
def test_dropout_trend_empty_cohort_reports_zero_coverage(outcomes):
    """No dropout population yields an explicit unassessed row and zero coverage."""
    row = _dropout_trend({"r": [.8] * 4}, outcomes)
    assert row.status == "not_assessed" and row.synthetic_value is None
    for text in ("total_dropout=0", "with_history=0", "assessable=0", "short_or_missing=0",
                 "invalid_history=0", "negative=0", "coverage=0.0000", "threshold=0.50 (model policy)"):
        assert text in row.details


def test_dropout_trend_cohort_is_counted_by_outcome_rows():
    """The explicit outcome-row denominator is retained even for duplicate IDs."""
    outcomes = [{"student_id": "d", "has_dropped_out": True}] * 2
    outcomes.append({"student_id": "missing", "has_dropped_out": True})
    row = _dropout_trend({"d": [.8, .6, .4, .2]}, outcomes)
    assert row.synthetic_value == 1.0
    for text in ("total_dropout=3", "assessable=2", "negative=2", "coverage=0.6667"):
        assert text in row.details


@pytest.mark.parametrize("enum_reference", [False, True])
def test_gender_string_enum_labels_keep_their_literal_categories(enum_reference):
    """Accepted string subclasses retain payload labels in observations and reference keys."""
    class Gender(str, Enum):
        """Standard string enum whose display name differs from its string payload."""

        MALE = "male"
        FEMALE = "female"

    distribution = {Gender.MALE: 0.55, Gender.FEMALE: 0.45} if enum_reference else {"male": 0.55, "female": 0.45}
    reference = ReferenceStatistics(gender_distribution=distribution)
    labels = [Gender.MALE] * 11 + [Gender.FEMALE] * 9
    students = [{"age": 30, "gender": label} for label in labels]
    report = SyntheticDataValidator(reference).validate_all(students, [])
    literal_students = [{"age": 30, "gender": label.value} for label in labels]
    literal_report = SyntheticDataValidator().validate_all(literal_students, [])
    json.dumps(report, allow_nan=False)
    row = next(r for r in report["results"] if r["test"] == "gender_distribution")
    literal = next(r for r in literal_report["results"] if r["test"] == "gender_distribution")
    assert row == literal
    assert (row["statistic"], row["p_value"], row["status"]) == (0.0, 1.0, "passed")
    assert "Gender." not in row["details"]
    assert reference.gender_distribution is distribution


@pytest.mark.parametrize("reference,reason", [
    ({"male": 0.5, "female": 0.5}, "unexpected_category"),
    ({"male": 0.5, "female": 0.5, "other": 0.0}, "zero_probability_category"),
    ({"male": 0.4, "female": 0.4, "other": 0.2}, None),
])
def test_gender_report_preserves_all_observations_and_checks_support(reference, reason):
    """A third observed category is reported, never discarded or allowed to crash."""
    students = [{"student_id": str(i), "age": 30, "gender": gender}
                for i, gender in enumerate(["male"] * 4 + ["female"] * 4 + ["other"] * 2)]
    report = SyntheticDataValidator(ReferenceStatistics(gender_distribution=reference)).validate_all(students, [])
    json.dumps(report, allow_nan=False)
    rows = [r for r in report["results"] if r["test"] == "gender_distribution"]
    assert len(rows) == 1
    row = rows[0]
    assert "n=10" in row["details"]
    for label, count in (("male", 4), ("female", 4), ("other", 2)):
        assert f"'category': '{label}', 'observed': {count}" in row["details"]
    if reason:
        assert row["status"] == "failed" and row["passed"] is False
        assert row["metric"] == "Category support check"
        assert row["p_value"] == 0.0
        assert row["statistic"] is row["synthetic"] is None
        assert row["reference"] == 0.0
        assert f"reason={reason}" in row["details"]
    else:
        assert (row["status"], row["passed"], row["statistic"], row["p_value"]) == ("passed", True, 0.0, 1.0)


@pytest.mark.parametrize("bad_category", [None, "", 7, True, ["male"], {"gender": "male"}])
def test_gender_invalid_observation_is_counted_and_reported(bad_category):
    """Nonscalar labels remain visible support failures in the public report."""
    students = [{"age": 30, "gender": "male"}, {"age": 30, "gender": bad_category}]
    report = SyntheticDataValidator().validate_all(students, [])
    json.dumps(report, allow_nan=False)
    row = next(r for r in report["results"] if r["test"] == "gender_distribution")
    assert row["status"] == "failed" and row["p_value"] == 0.0
    assert "reason=invalid_category" in row["details"]
    assert "n=2" in row["details"] and "invalid_count=1" in row["details"]


def test_missing_gender_is_a_visible_support_failure():
    """An absent label differs from an ordinary category named unknown."""
    report = SyntheticDataValidator().validate_all([{"age": 30}], [])
    row = next(r for r in report["results"] if r["test"] == "gender_distribution")
    assert row["status"] == "failed"
    assert "reason=invalid_category" in row["details"]
    assert "missing" in row["details"] and "invalid_count=1" in row["details"]


def test_gender_empty_and_single_supported_category_are_defined():
    """No observations are N/A; complete agreement on singleton support is exact."""
    reference = ReferenceStatistics(gender_distribution={"male": 1.0, "other": 0.0})
    validator = SyntheticDataValidator(reference)
    empty = next(r for r in validator._validate_demographics([]) if r.test_name == "gender_distribution")
    assert empty.status == "not_assessed" and empty.passed is False
    assert empty.synthetic_value is empty.statistic is empty.p_value is None
    assert "n=0" in empty.details
    row = next(r for r in validator._validate_demographics([{"age": 30, "gender": "male"}] * 3)
               if r.test_name == "gender_distribution")
    assert (row.statistic, row.p_value, row.passed) == (0.0, 1.0, True)
    assert "'category': 'other', 'observed': 0, 'reference': 0.0" in row.details
    assert reference.gender_distribution == {"male": 1.0, "other": 0.0}


@pytest.mark.parametrize("n", [20, 1000])
def test_gender_supported_chi_square_matches_oracle_and_is_order_independent(n):
    """Supported samples retain the statistic and effective-alpha decision."""
    from scipy import stats

    reference = ReferenceStatistics(gender_distribution={"other": 0.0, "female": 0.45, "male": 0.55})
    students = [{"age": 30, "gender": gender} for gender in ["male"] * (n // 2) + ["female"] * (n // 2)]
    validator = SyntheticDataValidator(reference)
    row = next(r for r in validator._validate_demographics(students) if r.test_name == "gender_distribution")
    expected = stats.chisquare([n // 2, n // 2], [n * 0.55, n * 0.45])
    assert row.statistic == pytest.approx(expected.statistic)
    assert row.p_value == pytest.approx(expected.pvalue)
    assert row.passed == bool(expected.pvalue > validator._effective_alpha(n))
    reordered = SyntheticDataValidator(ReferenceStatistics(gender_distribution={"male": 0.55, "female": 0.45, "other": 0.0}))
    other = next(r for r in reordered._validate_demographics(students[::-1]) if r.test_name == "gender_distribution")
    assert other == row


@pytest.mark.parametrize("students", [[], [{"age": 30, "gender": "male"}]])
def test_gender_rechecks_mutated_reference_before_assessment(students):
    """Mutable reference dictionaries cannot bypass validation, even at N=0."""
    reference = ReferenceStatistics()
    validator = SyntheticDataValidator(reference)
    reference.gender_distribution["male"] = 0.99
    with pytest.raises(ValueError, match="gender_distribution"):
        validator._validate_demographics(students)


def test_gender_unobserved_positive_category_contributes_to_chi_square():
    """Absent but possible reference categories still contribute their expected counts."""
    from scipy import stats

    reference = ReferenceStatistics(gender_distribution={"male": 0.4, "female": 0.4, "other": 0.2})
    students = [{"age": 30, "gender": g} for g in ["male"] * 4 + ["female"] * 6]
    row = next(r for r in SyntheticDataValidator(reference)._validate_demographics(students)
               if r.test_name == "gender_distribution")
    expected = stats.chisquare([4, 6, 0], [4, 4, 2])
    assert row.statistic == expected.statistic and row.p_value == expected.pvalue
    assert "'category': 'other', 'observed': 0, 'reference': 0.2" in row.details


def test_gender_accepted_real_probabilities_and_roundoff_reach_finite_reports():
    """Fractions and a machine-scale sum discrepancy work without changing inputs."""
    for distribution, labels in (
        ({"male": Fraction(1, 3), "female": Fraction(2, 3)}, ["male", "female", "female"]),
        ({"male": 0.5 + np.spacing(1.0), "female": 0.5}, ["male", "female"]),
        ({np.str_("male"): np.float64(0.5), np.str_("female"): np.float64(0.5)}, ["male", "female"]),
    ):
        original = dict(distribution)
        reference = ReferenceStatistics(gender_distribution=distribution)
        students = [{"age": 30, "gender": np.str_(label)} for label in labels]
        report = SyntheticDataValidator(reference).validate_all(students, [])
        json.dumps(report, allow_nan=False)
        row = next(r for r in report["results"] if r["test"] == "gender_distribution")
        assert row["status"] == "passed" and row["p_value"] == 1.0
        assert reference.gender_distribution == original
        assert "np.str_" not in row["details"]


def test_gender_mixed_support_failures_preserve_all_diagnostics():
    """Primary reason is deterministic while every support problem stays visible."""
    reference = ReferenceStatistics(gender_distribution={"male": 1.0, "female": 0.0})
    students = [{"age": 30, "gender": "other"}, {"age": 30, "gender": "female"}, {"age": 30}]
    report = SyntheticDataValidator(reference).validate_all(students, [])
    row = next(r for r in report["results"] if r["test"] == "gender_distribution")
    assert row["status"] == "failed" and "reason=invalid_category" in row["details"]
    assert "unexpected=['other']" in row["details"] and "zero_probability=['female']" in row["details"]
    assert "n=3" in row["details"] and "invalid_count=1" in row["details"]


@pytest.mark.parametrize("observed", ["rare", "common"])
def test_gender_unrepresentable_positive_reference_is_not_a_structural_zero(observed):
    """Positive Real inputs retain support and an exact diagnostic when float underflows."""
    rare = Fraction(1, 10**400)
    reference = ReferenceStatistics(gender_distribution={"rare": rare, "common": 1 - rare})
    students = [{"age": 30, "gender": observed}] * 10
    report = SyntheticDataValidator(reference).validate_all(students, [])
    json.dumps(report, allow_nan=False)
    row = next(r for r in report["results"] if r["test"] == "gender_distribution")
    assert row["status"] == "not_assessed" and row["passed"] is False
    assert row["statistic"] is row["synthetic"] is row["p_value"] is None
    assert "reason=unrepresentable_reference_probability" in row["details"]
    assert f"{hex(rare.numerator)}/{hex(rare.denominator)}" in row["details"] and "n=10" in row["details"]
    assert "zero_probability_category" not in row["details"]
    assert reference.gender_distribution["rare"] == rare


@pytest.mark.parametrize("category,status,reason", [
    ("common", "not_assessed", "unrepresentable_reference_probability"),
    ("rare", "not_assessed", "unrepresentable_reference_probability"),
    ("unexpected", "failed", "unexpected_category"),
    ("impossible", "failed", "zero_probability_category"),
    (None, "failed", "invalid_category"),
    ([], "not_assessed", "empty_sample"),
])
def test_gender_exact_diagnostic_survives_integer_decimal_conversion_limits(category, status, reason):
    """Large accepted rational probabilities cannot crash any reporting branch."""
    rare = Fraction(1, 10**5000)
    reference = ReferenceStatistics(gender_distribution={"rare": rare, "common": 1 - rare, "impossible": 0})
    students = [] if category == [] else [{"age": 30, "gender": category}]
    report = SyntheticDataValidator(reference).validate_all(students, [])
    json.dumps(report, allow_nan=False)
    row = next(r for r in report["results"] if r["test"] == "gender_distribution")
    assert row["status"] == status and f"reason={reason}" in row["details"]
    assert row["statistic"] is row["synthetic"] is None
    assert row["p_value"] == (0.0 if status == "failed" else None)
    assert f"{hex(rare.numerator)}/{hex(rare.denominator)}" in row["details"]
    assert reference.gender_distribution["rare"] == rare


@pytest.mark.parametrize("kind", ["large_integer", "large_fraction", "nested_integer", "broken_repr"])
def test_invalid_gender_diagnostic_cannot_abort_the_public_report(kind):
    """Invalid labels with unavailable text remain failed checks, including privacy rendering."""
    class BrokenGender:
        """Represent a supplied non-string object whose representation raises."""

        def __repr__(self):
            """Exercise diagnostic failure without changing interpreter limits."""
            raise RuntimeError("no representation")

    category = {"large_integer": 10**5000, "large_fraction": Fraction(1, 10**5000),
                "nested_integer": [10**5000], "broken_repr": BrokenGender()}[kind]
    report = SyntheticDataValidator().validate_all([{"age": 30, "gender": category}], [])
    json.dumps(report, allow_nan=False)
    rows = {r["test"]: r for r in report["results"]}
    row = rows["gender_distribution"]
    assert row["status"] == "failed" and row["p_value"] == 0.0
    assert "reason=invalid_category" in row["details"]
    assert "n=1" in row["details"] and "invalid_count=1" in row["details"]
    if kind in {"large_integer", "large_fraction"}:
        assert f"{hex(category.numerator)}/{hex(category.denominator)}" in row["details"]
    else:
        assert "representation_unavailable" in row["details"]
        assert rows["k_anonymity"]["status"] == "not_assessed"
        assert "reason=unrepresentable_gender_label" in rows["k_anonymity"]["details"]


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
