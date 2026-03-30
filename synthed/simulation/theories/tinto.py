"""Tinto (1975): Academic and social integration updates."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState


class TintoIntegration:
    """Update Tinto's academic and social integration based on week's events."""

    def update_integration(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        context: dict,
        records: list[InteractionRecord],
    ) -> None:
        """Update Tinto's academic and social integration based on week's events."""

        # Academic integration: driven by assignment/exam performance
        academic_events = [r for r in records if r.interaction_type in ("assignment_submit", "exam")]
        if academic_events:
            avg_quality = np.mean([r.quality_score for r in academic_events])
            # Good performance strengthens academic integration
            state.academic_integration += (avg_quality - 0.5) * 0.05
        else:
            # No academic activity -> slight erosion
            state.academic_integration -= 0.02

        # Social integration: driven by forum posts (Tinto + Durkheim)
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        forum_reads = sum(1 for r in records if r.interaction_type == "forum_read")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")

        if forum_posts > 0:
            state.social_integration += 0.03 * min(forum_posts, 3)
        if live_sessions > 0:
            state.social_integration += 0.02
        if forum_reads > 0 and forum_posts == 0:
            state.social_integration += 0.005  # Lurking helps minimally
        if forum_posts == 0 and forum_reads == 0 and live_sessions == 0:
            state.social_integration -= 0.03  # Durkheim: isolation erodes connection

        state.academic_integration = float(np.clip(state.academic_integration, 0.01, 0.95))
        state.social_integration = float(np.clip(state.social_integration, 0.01, 0.80))
