"""Rovai (2003): Self-regulation buffer and engagement floor for persistence."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona


class RovaiPersistence:
    """Rovai (2003): Accessibility and digital skills as persistence factors."""

    def regulation_buffer(self, student: StudentPersona) -> float:
        """
        High self-regulation students resist engagement decay.
        Returns a positive or negative adjustment to engagement.
        """
        return (student.self_regulation - 0.5) * 0.03

    def engagement_floor(self, student: StudentPersona) -> float:
        """
        Persona-based engagement floor.

        Students with strong self-regulation, goal commitment, and self-efficacy
        have a personal floor below which engagement does not drop.
        This models resilience: some students persist despite adversity.
        """
        personal_floor = (
            student.self_regulation * 0.15
            + student.goal_commitment * 0.12
            + student.self_efficacy * 0.10
            + student.learner_autonomy * 0.08  # Moore: autonomous learners persist
        ) * 0.50  # Scale: max ~0.22 for high-resilience students
        return personal_floor
