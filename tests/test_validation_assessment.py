"""Regression checks for undefined validation measurements and coverage."""

import json

import pytest

from synthed.validation import ReferenceStatistics, SyntheticDataValidator


def test_constant_correlation_is_not_assessed_and_serializes_as_null():
    """Constant data has no correlation estimate and must not emit NaN."""
    students = [{"student_id": str(i), "self_efficacy": 0.5} for i in range(20)]
    outcomes = {str(i): {"final_engagement": 0.5} for i in range(20)}
    row = SyntheticDataValidator()._correlation_test(
        students, outcomes, "self_efficacy", "final_engagement",
        "bandura_self_efficacy_engagement", "positive", 0.3, "Efficacy",
    )
    assert row.synthetic_value is None
    assert row.statistic is None
    assert row.p_value is None
    assert row.status == "not_assessed"
    assert row.passed is False
    assert "constant" in row.details
    json.dumps(vars(row), allow_nan=False)


def test_empty_population_reports_no_assessed_checks():
    """An empty cohort must return coverage without pretending to assess it."""
    report = SyntheticDataValidator().validate_all([], [], {})
    assert report["summary"]["assessed_tests"] == 0
    assert report["summary"]["overall_quality"] == "N/A (Not assessed)"
    assert report["summary"]["not_assessed"] == report["summary"]["total_tests"]
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_correlation_input_is_not_assessed(bad_value):
    """Non-finite pairs must remain visible as unassessed, not be dropped."""
    students = [{"student_id": str(i), "self_efficacy": i / 20} for i in range(20)]
    students[4]["self_efficacy"] = bad_value
    outcomes = {str(i): {"final_engagement": i / 25} for i in range(20)}
    row = SyntheticDataValidator()._correlation_test(
        students, outcomes, "self_efficacy", "final_engagement",
        "bandura_self_efficacy_engagement", "positive", 0.3, "Efficacy",
    )
    assert row.synthetic_value is None
    assert row.status == "not_assessed"
    assert "non_finite" in row.details


def test_non_finite_dropout_phase_cannot_pass_phase_distribution():
    """An unknown numeric phase must not count as evidence of nonterminal phases."""
    rows = SyntheticDataValidator(reference=ReferenceStatistics(dropout_rate=0.17))._validate_correlations(
        [], [{"student_id": "a", "final_dropout_phase": float("nan")}],
    )
    row = next(r for r in rows if r.test_name == "baulke_phase_distribution")
    assert row.status == "not_assessed"
    assert "non_finite" in row.details
    assert row.reference_value == 0.17


@pytest.mark.parametrize("n,expected", [(10, "not_assessed"), (11, "passed")])
def test_pair_eligibility_boundary_is_preserved(n, expected):
    """The existing eleven-pair gate stays unchanged with explicit coverage."""
    row = SyntheticDataValidator()._paired_correlation(
        list(range(n)), list(range(n)), "pairs", "positive", 0.3, "pairs",
    )
    assert row.status == expected


def test_requested_empty_temporal_data_produces_unassessed_rows():
    """A requested temporal assessment must explain missing inputs."""
    report = SyntheticDataValidator().validate_all([], [], {})
    rows = {r["test"]: r for r in report["results"]}
    for name in ("engagement_trajectory_divergence", "dropout_negative_trend_rate", "dropout_early_attrition"):
        assert rows[name]["status"] == "not_assessed"
        assert rows[name]["details"]


def test_undefined_correlation_output_retains_pair_count(monkeypatch):
    """Undefined library output must disclose how much evidence was attempted."""
    from synthed.validation import validator

    monkeypatch.setattr(validator.stats, "pearsonr", lambda *args: (float("nan"), float("nan")))
    row = SyntheticDataValidator()._paired_correlation(
        list(range(20)), list(range(20)), "pairs", "positive", 0.3, "pairs",
    )
    assert row.status == "not_assessed"
    assert "undefined_statistic" in row.details
    assert "n=20" in row.details


def test_undefined_sdt_output_retains_both_group_counts(monkeypatch):
    """Eligible motivation groups remain documented if their t statistic fails."""
    from synthed.validation import validator

    monkeypatch.setattr(validator.stats, "ttest_ind", lambda *args: (float("nan"), float("nan")))
    students = [{"student_id": str(i), "motivation_type": "intrinsic" if i < 5 else "amotivation"}
                for i in range(10)]
    outcomes = [{"student_id": str(i), "final_engagement": (i + 1) / 12} for i in range(10)]
    rows = SyntheticDataValidator()._validate_correlations(students, outcomes)
    row = next(r for r in rows if r.test_name == "sdt_intrinsic_vs_amotivation")
    assert row.status == "not_assessed"
    assert "intrinsic_n=5" in row.details
    assert "amotivation_n=5" in row.details
