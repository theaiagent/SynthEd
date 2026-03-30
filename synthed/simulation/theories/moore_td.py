"""Moore (1993): Transactional distance calculation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import SimulationState
    from ..environment import Course, ODLEnvironment


class MooreTransactionalDistance:
    """
    Moore (1993): Transactional distance = f(structure, dialogue, autonomy).
    """

    def calculate(self, student: StudentPersona, course: Course) -> float:
        """
        Calculate transactional distance for a student-course pair.

        High structure + low dialogue + low autonomy = high transactional distance.
        Returns 0-1 where higher = more distant (worse for engagement).
        """
        td = (
            course.structure_level * 0.35
            - course.dialogue_frequency * 0.30
            - student.learner_autonomy * 0.25
            - course.instructor_responsiveness * 0.10
        )
        return float(np.clip(td + 0.30, 0.0, 1.0))

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
        return float(np.mean(distances)) if distances else 0.5
