"""
Positive environmental events that counter constant negative pressure in ODL.

Addresses the asymmetry identified in architectural review: Bean & Metzner's
environmental factors are always negative, but real students experience
positive events too (financial aid, breaks, institutional support).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..state import SimulationState
    from ...agents.persona import StudentPersona


# Event name -> {effect_key: magnitude}
EVENT_EFFECTS: dict[str, dict[str, float]] = {
    "orientation_welcome": {
        "engagement_boost": 0.03,
        "social_integration_boost": 0.02,
        "teaching_presence_boost": 0.03,
    },
    "financial_aid_disbursement": {
        "engagement_boost": 0.02,
        "cost_benefit_boost": 0.03,
    },
    "semester_break": {
        "engagement_boost": 0.01,
        # Note: exhaustion recovery handled by GonzalezExhaustion via context["positive_event"]
    },
    "holiday_boost": {
        "engagement_boost": 0.015,
    },
    "peer_study_group": {
        "engagement_boost": 0.02,
        "social_integration_boost": 0.015,
    },
}


class PositiveEventHandler:
    """Apply positive environmental events to student state."""

    def apply(
        self,
        event_name: str | None,
        student: StudentPersona,
        state: SimulationState,
    ) -> float:
        """
        Apply positive event effects and return engagement boost.

        Returns the engagement delta (always >= 0).
        Other state modifications (social_integration, cost_benefit, etc.)
        are applied directly to state.
        """
        if not event_name:
            return 0.0

        effects = EVENT_EFFECTS.get(event_name, {})
        if not effects:
            return 0.0

        engagement_boost = effects.get("engagement_boost", 0.0)

        if "social_integration_boost" in effects:
            boost = effects["social_integration_boost"]
            state.social_integration = min(state.social_integration + boost, 0.80)

        if "cost_benefit_boost" in effects:
            boost = effects["cost_benefit_boost"]
            state.perceived_cost_benefit = min(
                state.perceived_cost_benefit + boost, 0.95
            )

        if "teaching_presence_boost" in effects:
            boost = effects["teaching_presence_boost"]
            state.coi_state.teaching_presence = min(
                state.coi_state.teaching_presence + boost, 0.95
            )

        return engagement_boost
