"""Kember (1989): Cost-benefit recalculation after major events."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState


class KemberCostBenefit:
    """Students perform ongoing cost-benefit analysis (Kember, 1989)."""

    def recalculate(
        self,
        student: StudentPersona,
        state: SimulationState,
        context: dict,
        records: list[InteractionRecord],
        avg_td: float,
    ) -> None:
        """
        Recalculate cost-benefit perception after major events.

        Triggered during exam weeks or after missed assignment streaks.
        Moore's transactional distance also feeds into perceived value.
        """
        # Poor performance reduces perceived cost-benefit
        recent_quality = [r.quality_score for r in records
                          if r.interaction_type in ("assignment_submit", "exam") and r.quality_score > 0]
        if recent_quality:
            avg_q = np.mean(recent_quality)
            state.perceived_cost_benefit += (avg_q - 0.5) * 0.04
        elif state.missed_assignments_streak >= 2:
            state.perceived_cost_benefit -= 0.03

        # Moore -> Kember: high transactional distance reduces perceived value
        state.perceived_cost_benefit -= (avg_td - 0.5) * 0.02
        state.perceived_cost_benefit = float(np.clip(state.perceived_cost_benefit, 0.05, 0.95))
