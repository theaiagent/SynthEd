"""Unavoidable Withdrawal Events: Life events that force immediate dropout.

Models real-world events (serious illness, family emergency, forced relocation,
etc.) that cause students to withdraw regardless of their academic engagement
or motivation.  These are independent of the Baulke dropout-phase process.

The per-semester probability is converted to a weekly probability so that the
cumulative chance over the full semester matches the configured rate.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.random import Generator

    from ..state import SimulationState
    from ...agents.persona import StudentPersona

logger = logging.getLogger(__name__)


class UnavoidableWithdrawal:
    """Life-event withdrawal model with configurable per-semester probability."""

    _EVENT_WEIGHTS: dict[str, float] = {
        "serious_illness": 0.30,
        "family_emergency": 0.20,
        "forced_relocation": 0.15,
        "career_change": 0.15,
        "military_deployment": 0.10,
        "death": 0.05,
        "legal_issues": 0.05,
    }

    def __init__(
        self,
        per_semester_probability: float,
        total_weeks: int,
    ) -> None:
        if not 0.0 <= per_semester_probability <= 1.0:
            raise ValueError(
                f"per_semester_probability must be between 0.0 and 1.0, "
                f"got {per_semester_probability}"
            )
        if total_weeks <= 0:
            raise ValueError(
                f"total_weeks must be positive, got {total_weeks}"
            )

        # Validate event weights sum to 1.0
        weights_sum = sum(self._EVENT_WEIGHTS.values())
        if abs(weights_sum - 1.0) > 1e-9:
            raise ValueError(f"_EVENT_WEIGHTS must sum to 1.0, got {weights_sum}")

        self.per_semester_probability = per_semester_probability
        self.total_weeks = total_weeks

        # Pre-compute event arrays for rng.choice (avoid per-call allocation)
        self._events: list[str] = list(self._EVENT_WEIGHTS.keys())
        self._weights: np.ndarray = np.array(list(self._EVENT_WEIGHTS.values()))

        # Convert semester probability to weekly probability:
        # P(at least one event in N weeks) = 1 - (1 - p_week)^N = p_semester
        # => p_week = 1 - (1 - p_semester)^(1/N)
        if per_semester_probability > 0.0:
            self.weekly_probability: float = 1.0 - (
                (1.0 - per_semester_probability) ** (1.0 / total_weeks)
            )
        else:
            self.weekly_probability = 0.0

    def check_withdrawal(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        rng: Generator,
    ) -> bool:
        """Roll for an unavoidable withdrawal event this week.

        If triggered, sets ``state.has_dropped_out``, ``state.dropout_week``,
        ``state.withdrawal_reason``, and appends a memory entry.

        Returns:
            True if the student was withdrawn, False otherwise.
        """
        if state.has_dropped_out:
            return False
        if self.weekly_probability <= 0.0:
            return False

        if rng.random() >= self.weekly_probability:
            return False

        # Select a reason weighted by _EVENT_WEIGHTS
        reason = rng.choice(self._events, p=self._weights)

        state.has_dropped_out = True
        state.dropout_week = week
        state.withdrawal_reason = reason
        state.memory.append({
            "week": week,
            "event_type": "unavoidable_withdrawal",
            "details": f"Withdrew due to {reason.replace('_', ' ')}",
            "impact": -1.0,
        })

        logger.debug(
            "Student %s withdrew in week %d due to %s",
            student.id, week, reason,
        )
        return True
