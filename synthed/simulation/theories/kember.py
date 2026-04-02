"""Kember (1989): Cost-benefit recalculation after major events."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState


class KemberCostBenefit:
    """Students perform ongoing cost-benefit analysis (Kember, 1989)."""

    # ── tuneable constants ──
    _QUALITY_FACTOR: float = 0.04            # cost-benefit sensitivity to academic quality
    _MISSED_PENALTY: float = 0.03            # penalty per missed-assignment streak event
    _TD_PENALTY_FACTOR: float = 0.02         # Moore TD influence on perceived value
    _TEACHING_PRESENCE_FACTOR: float = 0.03  # Garrison teaching presence boost
    _COI_COMPOSITE_FACTOR: float = 0.02      # CoI composite influence on value
    _GPA_CB_FACTOR: float = 0.01             # cost-benefit sensitivity to cumulative GPA
    _GPA_SCALE: float = 4.0                   # GPA scale denominator
    _OC_FACTOR: float = 0.015              # opportunity cost pressure per week
    _OC_STRESS_THRESHOLD: float = 0.5      # financial_stress above this triggers OC
    _TIME_DISCOUNT_FACTOR: float = 0.008   # time-based CB erosion per week
    _CLIP_LO: float = 0.05                   # cost-benefit lower bound
    _CLIP_HI: float = 0.95                   # cost-benefit upper bound

    def recalculate(
        self,
        student: StudentPersona,
        state: SimulationState,
        context: dict,
        records: list[InteractionRecord],
        avg_td: float,
        week: int | None = None,
        total_weeks: int | None = None,
    ) -> None:
        """
        Recalculate cost-benefit perception after academic events.

        Triggered when graded items are submitted, during exam weeks,
        or after missed assignment streaks. Cumulative GPA anchors the
        perceived return on educational investment.
        """
        # Poor performance reduces perceived cost-benefit
        recent_quality = [r.quality_score for r in records
                          if r.interaction_type in ("assignment_submit", "exam") and r.quality_score > 0]
        if recent_quality:
            avg_q = np.mean(recent_quality)
            state.perceived_cost_benefit += (avg_q - 0.5) * self._QUALITY_FACTOR
        elif state.missed_assignments_streak >= 2:
            state.perceived_cost_benefit -= self._MISSED_PENALTY

        # Moore -> Kember: high transactional distance reduces perceived value
        state.perceived_cost_benefit -= (avg_td - 0.5) * self._TD_PENALTY_FACTOR

        # Garrison -> Kember: teaching presence modulates perceived value
        state.perceived_cost_benefit += (state.coi_state.teaching_presence - 0.5) * self._TEACHING_PRESENCE_FACTOR

        # CoI composite: engaged learning community = higher perceived value
        coi_composite = (
            state.coi_state.social_presence
            + state.coi_state.cognitive_presence
            + state.coi_state.teaching_presence
        ) / 3
        state.perceived_cost_benefit += (coi_composite - 0.4) * self._COI_COMPOSITE_FACTOR

        # Perceived mastery -> Kember: student's actual understanding modulates perceived value
        if state.perceived_mastery_count > 0:
            mastery = state.perceived_mastery
            state.perceived_cost_benefit += (mastery - 0.5) * self._GPA_CB_FACTOR

        # Kember (1989): opportunity cost — employed students with financial pressure
        # experience "what else could I be doing with this time/money?"
        if (student is not None and week is not None and total_weeks is not None
                and student.is_employed
                and student.financial_stress > self._OC_STRESS_THRESHOLD):
            oc_pressure = student.financial_stress * self._OC_FACTOR
            semester_progress = week / total_weeks
            oc_pressure *= (0.5 + 0.5 * semester_progress)
            state.perceived_cost_benefit -= oc_pressure
            if student.has_family_responsibilities:
                state.perceived_cost_benefit -= self._OC_FACTOR * 0.3

        state.perceived_cost_benefit = float(np.clip(state.perceived_cost_benefit, self._CLIP_LO, self._CLIP_HI))
