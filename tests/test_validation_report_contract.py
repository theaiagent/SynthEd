"""Coverage and legacy compatibility for the shared validation report contract."""

import pytest

from synthed.validation.report_contract import (
    quality_grade, result_status, summarize_results, validation_summary,
)


def test_summary_excludes_unassessed_rows_from_pass_rate():
    """One unassessed row must change coverage without changing assessed quality."""
    summary = summarize_results([
        {"passed": True}, {"passed": False},
        {"passed": False, "status": "not_assessed", "details": "constant input"},
    ])
    assert summary == {"total_tests": 3, "assessed_tests": 2, "passed": 1,
                       "failed": 1, "not_assessed": 1, "pass_rate": 0.5,
                       "overall_quality": "D (Poor)", "assessment_complete": False}


def test_no_assessed_rows_have_no_quality_grade():
    """An empty or unassessed report is not an F result."""
    assert quality_grade(0, 0) == "N/A (Not assessed)"
    assert summarize_results([])["assessment_complete"] is True
    assert summarize_results([{"status": "not_assessed", "passed": False}])["assessment_complete"] is False


def test_modern_results_override_stale_summary():
    """Coverage must be derived from actual rows when they are available."""
    summary = validation_summary({"summary": {"passed": 20}, "results": [
        {"passed": True}, {"passed": False, "status": "not_assessed"},
    ]})
    assert summary["passed"] == 1
    assert summary["assessed_tests"] == 1
    assert summary["not_assessed"] == 1


def test_summary_only_legacy_report_keeps_its_original_grade():
    """Historical summaries must not acquire guessed missing assessments."""
    original = {"total_tests": 4, "passed": 3, "failed": 1,
                "pass_rate": 0.75, "overall_quality": "B (Good)"}
    report = {"summary": original}
    summary = validation_summary(report)
    assert summary["assessed_tests"] == 4
    assert summary["not_assessed"] == 0
    assert summary["overall_quality"] == "B (Good)"
    assert original == report["summary"]


@pytest.mark.parametrize("row", [{"status": "other"}, {"status": "passed", "passed": False},
                                 {"status": "not_assessed", "passed": True}])
def test_invalid_row_status_cannot_be_silently_classified(row):
    """Inconsistent external rows must fail before a score is displayed."""
    with pytest.raises(ValueError):
        result_status(row)
