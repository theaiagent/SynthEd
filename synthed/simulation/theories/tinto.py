"""Tinto (1975): Academic and social integration updates."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..state import InteractionRecord, SimulationState
    from .protocol import TheoryContext


class TintoIntegration:
    """Update Tinto's academic and social integration based on week's events."""

    _PHASE_ORDER: int = 10        # discovery sort (on_individual_step)
    _ENGAGEMENT_ORDER: int = 100  # engagement composition order

    # ── tuneable constants ──
    _ACADEMIC_QUALITY_FACTOR: float = 0.05   # academic integration boost per quality delta
    _ACADEMIC_EROSION: float = 0.02          # weekly erosion when no academic activity
    _FORUM_POST_BOOST: float = 0.03          # social integration boost per forum post
    _MAX_POST_CREDIT: int = 3                # max forum posts that count
    _LIVE_SESSION_BOOST: float = 0.02        # social integration boost for live attendance
    _LURK_BOOST: float = 0.005               # minimal boost for reading without posting
    _ISOLATION_EROSION: float = 0.03         # Durkheim: erosion when fully isolated
    _ACADEMIC_CLIP_LO: float = 0.01          # academic integration lower bound
    _ACADEMIC_CLIP_HI: float = 0.95          # academic integration upper bound
    _SOCIAL_CLIP_LO: float = 0.01            # social integration lower bound
    _SOCIAL_CLIP_HI: float = 0.80            # social integration upper bound

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
            state.academic_integration += (avg_quality - 0.5) * self._ACADEMIC_QUALITY_FACTOR
        else:
            # No academic activity -> slight erosion
            state.academic_integration -= self._ACADEMIC_EROSION

        # Social integration: driven by forum posts (Tinto + Durkheim)
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        forum_reads = sum(1 for r in records if r.interaction_type == "forum_read")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")

        if forum_posts > 0:
            state.social_integration += self._FORUM_POST_BOOST * min(forum_posts, self._MAX_POST_CREDIT)
        if live_sessions > 0:
            state.social_integration += self._LIVE_SESSION_BOOST
        if forum_reads > 0 and forum_posts == 0:
            state.social_integration += self._LURK_BOOST  # Lurking helps minimally
        if forum_posts == 0 and forum_reads == 0 and live_sessions == 0:
            state.social_integration -= self._ISOLATION_EROSION  # Durkheim: isolation erodes connection

        state.academic_integration = float(np.clip(state.academic_integration, self._ACADEMIC_CLIP_LO, self._ACADEMIC_CLIP_HI))
        state.social_integration = float(np.clip(state.social_integration, self._SOCIAL_CLIP_LO, self._SOCIAL_CLIP_HI))

    def on_individual_step(self, ctx: TheoryContext) -> None:
        """Protocol dispatch: Phase 1 per-student."""
        self.update_integration(ctx.student, ctx.state, ctx.week, ctx.context, ctx.records)

    def contribute_engagement_delta(self, ctx: TheoryContext) -> float:
        """Integration effect on engagement (Tinto, 1975)."""
        decay_attenuation = 1.0 / (1.0 + ctx.cfg._DECAY_DAMPING_FACTOR * (ctx.week - 1) ** 0.5)
        return (
            ctx.state.academic_integration * ctx.cfg._TINTO_ACADEMIC_WEIGHT
            + ctx.state.social_integration * ctx.cfg._TINTO_SOCIAL_WEIGHT
            - ctx.cfg._TINTO_DECAY_BASE * decay_attenuation
        )
