"""Deci & Ryan (1985): Self-Determination Theory — Basic Psychological Needs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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

    autonomy: float = 0.5
    competence: float = 0.5
    relatedness: float = 0.5

    @property
    def composite(self) -> float:
        """Weighted composite of all three needs."""
        return self.autonomy * 0.35 + self.competence * 0.40 + self.relatedness * 0.25


class SDTMotivationDynamics:
    """Update SDT need satisfaction and derive motivation type shifts.

    Autonomy: from learner_autonomy + low course structure.
    Competence: from academic outcomes (assignment/exam quality).
    Relatedness: from social_integration + CoI social_presence.
    """

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
        autonomy_delta = (student.learner_autonomy - 0.5) * 0.03
        # Self-regulation supports sense of control
        autonomy_delta += (student.self_regulation - 0.5) * 0.01
        # Small weekly decay toward neutral
        autonomy_delta -= 0.005
        needs.autonomy = float(np.clip(needs.autonomy + autonomy_delta, 0.01, 0.99))

        # ── Competence ──
        academic_events = [
            r for r in records
            if r.interaction_type in ("assignment_submit", "exam")
        ]
        if academic_events:
            avg_quality = float(np.mean([r.quality_score for r in academic_events]))
            competence_delta = (avg_quality - 0.5) * 0.06
        else:
            # No academic activity this week — slight erosion
            competence_delta = -0.02

        # Missed assignment streak erodes competence belief
        if state.missed_assignments_streak >= 2:
            competence_delta -= 0.02 * min(state.missed_assignments_streak - 1, 3)

        # Self-efficacy provides a small buffer
        competence_delta += (student.self_efficacy - 0.5) * 0.01
        needs.competence = float(np.clip(needs.competence + competence_delta, 0.01, 0.99))

        # ── Relatedness ──
        # Social integration and CoI social_presence both feed relatedness
        relatedness_delta = (state.social_integration - 0.4) * 0.02
        relatedness_delta += (state.coi_state.social_presence - 0.3) * 0.02

        # Forum posts and live sessions boost relatedness
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")
        relatedness_delta += forum_posts * 0.015 + live_sessions * 0.01

        # Weekly decay
        relatedness_delta -= 0.01
        needs.relatedness = float(np.clip(needs.relatedness + relatedness_delta, 0.01, 0.99))

    def evaluate_motivation_shift(self, state: SimulationState) -> str:
        """Return current motivation type based on composite need satisfaction.

        Thresholds follow SDT predictions:
        - High need satisfaction → intrinsic motivation
        - Moderate satisfaction → extrinsic (identified/introjected regulation)
        - Low satisfaction → amotivation
        """
        composite = state.sdt_needs.composite
        if composite >= 0.60:
            return "intrinsic"
        if composite >= 0.35:
            return "extrinsic"
        return "amotivation"
