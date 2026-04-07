"""Deci & Ryan (1985): Self-Determination Theory — Basic Psychological Needs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState


@dataclass
class SDTNeedSatisfaction:
    """Deci & Ryan (1985): Basic Psychological Needs.

    Each need is tracked on a 0-1 scale where higher values indicate
    greater satisfaction of that need in the learning environment.
    """

    # ── composite weights ──
    _AUTONOMY_COMPOSITE_WEIGHT: ClassVar[float] = 0.35  # autonomy weight in composite score
    _COMPETENCE_COMPOSITE_WEIGHT: ClassVar[float] = 0.40  # competence weight in composite score
    _RELATEDNESS_COMPOSITE_WEIGHT: ClassVar[float] = 0.25  # relatedness weight in composite score

    autonomy: float = 0.5
    competence: float = 0.5
    relatedness: float = 0.5

    @property
    def composite(self) -> float:
        """Weighted composite of all three needs."""
        return self.autonomy * self._AUTONOMY_COMPOSITE_WEIGHT + self.competence * self._COMPETENCE_COMPOSITE_WEIGHT + self.relatedness * self._RELATEDNESS_COMPOSITE_WEIGHT


class SDTMotivationDynamics:
    """Update SDT need satisfaction and derive motivation type shifts.

    Autonomy: from learner_autonomy + low course structure.
    Competence: from academic outcomes (assignment/exam quality).
    Relatedness: from social_integration + CoI social_presence.
    """

    # ── tuneable constants ──
    _AUTONOMY_FACTOR: float = 0.03           # autonomy need sensitivity to learner autonomy
    _AUTONOMY_REGULATION_FACTOR: float = 0.01  # self-regulation's contribution to autonomy
    _AUTONOMY_DECAY: float = 0.005           # weekly autonomy decay toward neutral
    _COMPETENCE_QUALITY_FACTOR: float = 0.06 # competence sensitivity to academic quality
    _COMPETENCE_EROSION: float = 0.02        # competence erosion when no academic activity
    _COMPETENCE_STREAK_PENALTY: float = 0.02 # per-streak competence erosion
    _COMPETENCE_STREAK_CAP: int = 3          # max streak multiplier for competence
    _COMPETENCE_EFFICACY_FACTOR: float = 0.01  # self-efficacy buffer for competence
    _COMPETENCE_GPA_FACTOR: float = 0.008    # competence sensitivity to cumulative GPA (weekly)
    _GPA_SCALE: float = 4.0                   # GPA scale denominator
    _RELATEDNESS_SOCIAL_FACTOR: float = 0.02 # social integration influence on relatedness
    _RELATEDNESS_COI_FACTOR: float = 0.02    # CoI social presence influence on relatedness
    _RELATEDNESS_FORUM_BOOST: float = 0.015  # relatedness boost per forum post
    _RELATEDNESS_LIVE_BOOST: float = 0.01    # relatedness boost per live session
    _RELATEDNESS_DECAY: float = 0.01         # weekly relatedness decay
    _NEED_CLIP_LO: float = 0.01             # lower bound for all needs
    _NEED_CLIP_HI: float = 0.99             # upper bound for all needs
    _INTRINSIC_THRESHOLD: float = 0.60       # composite above this → intrinsic motivation
    _EXTRINSIC_THRESHOLD: float = 0.35       # composite above this → extrinsic motivation

    def update_needs(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        records: list[InteractionRecord],
    ) -> None:
        """Update need satisfaction based on weekly events.

        Autonomy rises when the learner has high autonomy and the course
        structure is not overly rigid (proxied by learner_autonomy).
        Competence tracks academic outcomes — good grades raise it,
        missed assignments or low scores erode it.
        Relatedness mirrors social bonds (social_integration + CoI social_presence).
        """
        needs = state.sdt_needs

        # ── Autonomy ──
        # High learner_autonomy satisfies autonomy need; low drags it down.
        autonomy_delta = (student.learner_autonomy - 0.5) * self._AUTONOMY_FACTOR
        # Self-regulation supports sense of control
        autonomy_delta += (student.self_regulation - 0.5) * self._AUTONOMY_REGULATION_FACTOR
        # Small weekly decay toward neutral
        autonomy_delta -= self._AUTONOMY_DECAY
        needs.autonomy = float(np.clip(needs.autonomy + autonomy_delta, self._NEED_CLIP_LO, self._NEED_CLIP_HI))

        # ── Competence ──
        academic_events = [
            r for r in records
            if r.interaction_type in ("assignment_submit", "exam")
        ]
        if academic_events:
            avg_quality = float(np.mean([r.quality_score for r in academic_events]))
            competence_delta = (avg_quality - 0.5) * self._COMPETENCE_QUALITY_FACTOR
        else:
            # No academic activity this week — slight erosion
            competence_delta = -self._COMPETENCE_EROSION

        # Missed assignment streak erodes competence belief
        if state.missed_assignments_streak >= 2:
            competence_delta -= self._COMPETENCE_STREAK_PENALTY * min(state.missed_assignments_streak - 1, self._COMPETENCE_STREAK_CAP)

        # Self-efficacy provides a small buffer
        competence_delta += (student.self_efficacy - 0.5) * self._COMPETENCE_EFFICACY_FACTOR
        # Perceived mastery anchors competence belief to actual understanding
        if state.perceived_mastery_count > 0:
            mastery = state.perceived_mastery
            competence_delta += (mastery - 0.5) * self._COMPETENCE_GPA_FACTOR
        needs.competence = float(np.clip(needs.competence + competence_delta, self._NEED_CLIP_LO, self._NEED_CLIP_HI))

        # ── Relatedness ──
        # Social integration and CoI social_presence both feed relatedness
        relatedness_delta = (state.social_integration - 0.4) * self._RELATEDNESS_SOCIAL_FACTOR
        relatedness_delta += (state.coi_state.social_presence - 0.3) * self._RELATEDNESS_COI_FACTOR

        # Forum posts and live sessions boost relatedness
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")
        relatedness_delta += forum_posts * self._RELATEDNESS_FORUM_BOOST + live_sessions * self._RELATEDNESS_LIVE_BOOST

        # Weekly decay
        relatedness_delta -= self._RELATEDNESS_DECAY
        needs.relatedness = float(np.clip(needs.relatedness + relatedness_delta, self._NEED_CLIP_LO, self._NEED_CLIP_HI))

    def evaluate_motivation_shift(self, state: SimulationState) -> str:
        """Return current motivation type based on composite need satisfaction.

        Thresholds follow SDT predictions:
        - High need satisfaction → intrinsic motivation
        - Moderate satisfaction → extrinsic (identified/introjected regulation)
        - Low satisfaction → amotivation
        """
        composite = state.sdt_needs.composite
        if composite >= self._INTRINSIC_THRESHOLD:
            return "intrinsic"
        if composite >= self._EXTRINSIC_THRESHOLD:
            return "extrinsic"
        return "amotivation"

