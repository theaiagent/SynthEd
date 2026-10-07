"""Shared coverage and quality semantics for modern and historical reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


def result_status(row: Mapping[str, Any]) -> str:
    """Read a result status without treating unassessed rows as failures."""
    passed = row.get("passed", False)
    if isinstance(passed, np.bool_):
        passed = bool(passed)
    if not isinstance(passed, bool):
        raise TypeError("Validation passed flag must be bool")
    status = row.get("status")
    if status is None:
        return "passed" if passed else "failed"
    if status not in {"passed", "failed", "not_assessed"}:
        raise ValueError(f"Unknown validation status: {status!r}")
    if passed != (status == "passed"):
        raise ValueError("Validation status and passed flag disagree")
    return status


def quality_grade(pass_rate: float, assessed_tests: int) -> str:
    """Grade assessed checks using existing thresholds; no checks means N/A."""
    if assessed_tests == 0:
        return "N/A (Not assessed)"
    for threshold, label in ((0.9, "A (Excellent)"), (0.75, "B (Good)"),
                             (0.6, "C (Acceptable)"), (0.4, "D (Poor)")):
        if pass_rate >= threshold:
            return label
    return "F (Unacceptable)"


def summarize_results(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count assessment coverage and calculate quality from assessed rows only."""
    statuses = [result_status(row) for row in rows]
    passed, failed = statuses.count("passed"), statuses.count("failed")
    assessed = passed + failed
    unassessed = statuses.count("not_assessed")
    rate = passed / assessed if assessed else 0.0
    return {"total_tests": len(rows), "assessed_tests": assessed,
            "passed": passed, "failed": failed, "not_assessed": unassessed,
            "pass_rate": rate, "overall_quality": quality_grade(rate, assessed),
            "assessment_complete": unassessed == 0}


def validation_summary(validation: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize coverage while preserving summary-only historical reports."""
    rows = validation.get("results")
    if isinstance(rows, (list, tuple)):
        return summarize_results(rows)
    summary = dict(validation.get("summary") or {})
    if not summary:
        return summarize_results([])
    summary.setdefault("assessed_tests", summary.get("total_tests", 0))
    summary.setdefault("not_assessed", 0)
    summary.setdefault("assessment_complete", summary["not_assessed"] == 0)
    return summary
