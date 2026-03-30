"""Garrison et al. (2000): Community of Inquiry presences."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState
    from ..environment import Course


class GarrisonCoI:
    """Update Community of Inquiry presences based on weekly activity."""

    def update_presences(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        records: list[InteractionRecord],
        active_courses: list[Course],
    ) -> None:
        """
        Update Community of Inquiry presences based on weekly activity.

        Social presence: driven by forum posts, live sessions, extraversion.
        Cognitive presence: driven by assignment quality, forum depth, openness.
        Teaching presence: driven by course dialogue, instructor responsiveness.
        """
        coi = state.coi_state

        # Social presence
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")
        coi.social_presence += (
            forum_posts * 0.03
            + live_sessions * 0.02
            + (student.personality.extraversion - 0.5) * 0.01
            - 0.02  # decay without activity
        )

        # Cognitive presence
        academic_events = [r for r in records
                          if r.interaction_type in ("assignment_submit", "exam")]
        if academic_events:
            avg_quality = float(np.mean([r.quality_score for r in academic_events]))
            coi.cognitive_presence += (avg_quality - 0.5) * 0.04
        deep_posts = sum(1 for r in records
                        if r.interaction_type == "forum_post"
                        and r.metadata.get("post_length", 0) > 100)
        coi.cognitive_presence += deep_posts * 0.02 - 0.01

        # Teaching presence (environment-driven, modulated by student perception)
        if active_courses:
            avg_dialogue = float(np.mean([c.dialogue_frequency for c in active_courses]))
            avg_responsiveness = float(np.mean([c.instructor_responsiveness for c in active_courses]))
            coi.teaching_presence += (avg_dialogue - 0.4) * 0.02
            coi.teaching_presence += (avg_responsiveness - 0.5) * 0.01
        coi.teaching_presence += (student.institutional_support_access - 0.5) * 0.01

        # Clamp all presences
        coi.social_presence = float(np.clip(coi.social_presence, 0.01, 0.95))
        coi.cognitive_presence = float(np.clip(coi.cognitive_presence, 0.01, 0.95))
        coi.teaching_presence = float(np.clip(coi.teaching_presence, 0.01, 0.95))
