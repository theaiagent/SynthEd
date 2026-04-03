"""Aggregate statistics computed from simulation states."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .engine import SimulationState

logger = logging.getLogger(__name__)


def summary_statistics(
    states: dict[str, SimulationState],
    grading_scale_value: int,
) -> dict[str, Any]:
    """Compute aggregate statistics from simulation states.

    Parameters
    ----------
    states:
        Mapping of student ID to their final :class:`SimulationState`.
    grading_scale_value:
        Numeric value of the grading scale (e.g. ``GradingScale.value``).
    """
    total = len(states)
    dropouts = sum(1 for s in states.values() if s.has_dropped_out)
    dropout_weeks = [s.dropout_week for s in states.values() if s.dropout_week]
    final_engagements = [
        s.weekly_engagement_history[-1] if s.weekly_engagement_history else 0
        for s in states.values() if not s.has_dropped_out
    ]
    phase_dist: dict[str | int, int] = {}
    for s in states.values():
        if s.withdrawal_reason is not None:
            key = "unavoidable_withdrawal"
        elif s.has_dropped_out:
            key = 5  # Baulke phase 5 (decided)
        else:
            key = s.dropout_phase
        phase_dist[key] = phase_dist.get(key, 0) + 1

    # Unavoidable withdrawal breakdown
    withdrawal_reasons: dict[str, int] = {}
    for s in states.values():
        if s.withdrawal_reason is not None:
            withdrawal_reasons[s.withdrawal_reason] = (
                withdrawal_reasons.get(s.withdrawal_reason, 0) + 1
            )
    withdrawal_count = sum(withdrawal_reasons.values())

    # GPA statistics (only for students with graded items)
    gpa_values = [s.cumulative_gpa for s in states.values() if s.gpa_count > 0]
    mean_final_gpa = float(np.mean(gpa_values)) if gpa_values else None

    # Outcome distribution
    outcomes = [s.outcome for s in states.values() if s.outcome is not None]
    n_outcomes = max(len(outcomes) if outcomes else total, 1)
    if n_outcomes < total:
        logger.warning("Only %d/%d students have an assigned outcome", n_outcomes, total)
    outcome_counts: dict[str, int] = {}
    for o in outcomes:
        outcome_counts[o] = outcome_counts.get(o, 0) + 1

    return {
        "total_students": total,
        "dropout_count": dropouts,
        "dropout_rate": dropouts / total if total > 0 else 0,
        "mean_dropout_week": float(np.mean(dropout_weeks)) if dropout_weeks else None,
        "std_dropout_week": float(np.std(dropout_weeks)) if dropout_weeks else None,
        "mean_final_engagement": float(np.mean(final_engagements)) if final_engagements else None,
        "std_final_engagement": float(np.std(final_engagements)) if final_engagements else None,
        "mean_final_gpa": mean_final_gpa,
        "retained_students": total - dropouts,
        "dropout_phase_distribution": {
            (f"phase_{k}" if isinstance(k, int) else str(k)): v
            for k, v in sorted(phase_dist.items(), key=lambda x: (isinstance(x[0], str), x[0]))
        },
        "unavoidable_withdrawal_count": withdrawal_count,
        "unavoidable_withdrawal_reasons": withdrawal_reasons,
        "pass_rate": outcome_counts.get("Pass", 0) / n_outcomes,
        "distinction_rate": outcome_counts.get("Distinction", 0) / n_outcomes,
        "fail_rate": outcome_counts.get("Fail", 0) / n_outcomes,
        "withdrawn_rate": outcome_counts.get("Withdrawn", 0) / n_outcomes,
        "outcome_distribution": outcome_counts,
        "grading_scale": grading_scale_value,
    }
