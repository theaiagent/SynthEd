"""Moore (1993): Transactional distance calculation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..state import SimulationState
    from ..environment import Course, ODLEnvironment
    from .protocol import TheoryContext


class MooreTransactionalDistance:
    """
    Moore (1993): Transactional distance = f(structure, dialogue, autonomy).
    """

    _ENGAGEMENT_ORDER: int = 600  # engagement composition order

    # ── tuneable constants ──
    _STRUCTURE_WEIGHT: float = 0.35      # weight of course structure (raises TD)
    _DIALOGUE_WEIGHT: float = 0.30       # weight of dialogue frequency (lowers TD)
    _AUTONOMY_WEIGHT: float = 0.25       # weight of learner autonomy (lowers TD)
    _RESPONSIVENESS_WEIGHT: float = 0.10 # weight of instructor responsiveness (lowers TD)
    _OFFSET: float = 0.30               # baseline offset to centre TD distribution
    _DEFAULT_TD: float = 0.5            # fallback when no active courses

    def calculate(self, student: StudentPersona, course: Course) -> float:
        """
        Calculate transactional distance for a student-course pair.

        High structure + low dialogue + low autonomy = high transactional distance.
        Returns 0-1 where higher = more distant (worse for engagement).
        """
        td = (
            course.structure_level * self._STRUCTURE_WEIGHT
            - course.dialogue_frequency * self._DIALOGUE_WEIGHT
            - student.learner_autonomy * self._AUTONOMY_WEIGHT
            - course.instructor_responsiveness * self._RESPONSIVENESS_WEIGHT
        )
        return float(np.clip(td + self._OFFSET, 0.0, 1.0))

    def average(
        self,
        student: StudentPersona,
        state: SimulationState,
        env: ODLEnvironment,
    ) -> float:
        """Average transactional distance across active courses."""
        distances = []
        for cid in state.courses_active:
            course = env.get_course_by_id(cid)
            if course:
                distances.append(self.calculate(student, course))
        return float(np.mean(distances)) if distances else self._DEFAULT_TD

    def contribute_engagement_delta(self, ctx: TheoryContext) -> float:
        """Transactional distance effect on engagement (Moore, 1993)."""
        return -(ctx.avg_td - 0.5) * ctx.cfg._TD_EFFECT_FACTOR
