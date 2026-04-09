"""Garrison et al. (2000): Community of Inquiry presences."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..state import InteractionRecord, SimulationState
    from .protocol import TheoryContext
    from ..environment import Course


class GarrisonCoI:
    """Update Community of Inquiry presences based on weekly activity."""

    _PHASE_ORDER: int = 20

    # ── tuneable constants ──
    _FORUM_POST_SOCIAL_BOOST: float = 0.03    # social presence boost per forum post
    _LIVE_SESSION_SOCIAL_BOOST: float = 0.02  # social presence boost per live session
    _EXTRAVERSION_FACTOR: float = 0.01        # extraversion influence on social presence
    _SOCIAL_DECAY: float = 0.02               # weekly social presence decay
    _COGNITIVE_QUALITY_FACTOR: float = 0.04   # cognitive presence boost per quality delta
    _DEEP_POST_BOOST: float = 0.02            # boost for substantive forum posts
    _DEEP_POST_MIN_LENGTH: int = 100          # minimum post length for deep post credit
    _COGNITIVE_DECAY: float = 0.01            # weekly cognitive presence decay
    _DIALOGUE_FACTOR: float = 0.02            # teaching presence boost per dialogue delta
    _RESPONSIVENESS_FACTOR: float = 0.01      # teaching presence boost per responsiveness delta
    _SUPPORT_ACCESS_FACTOR: float = 0.01      # institutional support influence
    _PRESENCE_CLIP_LO: float = 0.01           # lower bound for all presences
    _PRESENCE_CLIP_HI: float = 0.95           # upper bound for all presences

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
            forum_posts * self._FORUM_POST_SOCIAL_BOOST
            + live_sessions * self._LIVE_SESSION_SOCIAL_BOOST
            + (student.personality.extraversion - 0.5) * self._EXTRAVERSION_FACTOR
            - self._SOCIAL_DECAY  # decay without activity
        )

        # Cognitive presence
        academic_events = [r for r in records
                          if r.interaction_type in ("assignment_submit", "exam")]
        if academic_events:
            avg_quality = float(np.mean([r.quality_score for r in academic_events]))
            coi.cognitive_presence += (avg_quality - 0.5) * self._COGNITIVE_QUALITY_FACTOR
        deep_posts = sum(1 for r in records
                        if r.interaction_type == "forum_post"
                        and r.metadata.get("post_length", 0) > self._DEEP_POST_MIN_LENGTH)
        coi.cognitive_presence += deep_posts * self._DEEP_POST_BOOST - self._COGNITIVE_DECAY

        # Teaching presence (environment-driven, modulated by student perception)
        if active_courses:
            avg_dialogue = float(np.mean([c.dialogue_frequency for c in active_courses]))
            avg_responsiveness = float(np.mean([c.instructor_responsiveness for c in active_courses]))
            coi.teaching_presence += (avg_dialogue - 0.4) * self._DIALOGUE_FACTOR
            coi.teaching_presence += (avg_responsiveness - 0.5) * self._RESPONSIVENESS_FACTOR
        coi.teaching_presence += (student.institutional_support_access - 0.5) * self._SUPPORT_ACCESS_FACTOR

        # Clamp all presences
        coi.social_presence = float(np.clip(coi.social_presence, self._PRESENCE_CLIP_LO, self._PRESENCE_CLIP_HI))
        coi.cognitive_presence = float(np.clip(coi.cognitive_presence, self._PRESENCE_CLIP_LO, self._PRESENCE_CLIP_HI))
        coi.teaching_presence = float(np.clip(coi.teaching_presence, self._PRESENCE_CLIP_LO, self._PRESENCE_CLIP_HI))

    def on_individual_step(self, ctx: TheoryContext) -> None:
        """Protocol dispatch: Phase 1 per-student."""
        self.update_presences(ctx.student, ctx.state, ctx.week, ctx.records, ctx.active_courses)
