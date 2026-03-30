"""Rovai (2003): Self-regulation buffer and engagement floor for persistence."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona


class RovaiPersistence:
    """Rovai (2003): Accessibility and digital skills as persistence factors."""

    # ── tuneable constants ──
    _REGULATION_FACTOR: float = 0.03       # self-regulation sensitivity for engagement buffer
    _FLOOR_REGULATION_WEIGHT: float = 0.15 # self-regulation weight in engagement floor
    _FLOOR_GOAL_WEIGHT: float = 0.12       # goal commitment weight in engagement floor
    _FLOOR_EFFICACY_WEIGHT: float = 0.10   # self-efficacy weight in engagement floor
    _FLOOR_AUTONOMY_WEIGHT: float = 0.08   # learner autonomy weight in engagement floor
    _FLOOR_SCALE: float = 0.50             # scale factor; max floor ~0.22 for high-resilience

    def regulation_buffer(self, student: StudentPersona) -> float:
        """
        High self-regulation students resist engagement decay.
        Returns a positive or negative adjustment to engagement.
        """
        return (student.self_regulation - 0.5) * self._REGULATION_FACTOR

    def engagement_floor(self, student: StudentPersona) -> float:
        """
        Persona-based engagement floor.

        Students with strong self-regulation, goal commitment, and self-efficacy
        have a personal floor below which engagement does not drop.
        This models resilience: some students persist despite adversity.
        """
        personal_floor = (
            student.self_regulation * self._FLOOR_REGULATION_WEIGHT
            + student.goal_commitment * self._FLOOR_GOAL_WEIGHT
            + student.self_efficacy * self._FLOOR_EFFICACY_WEIGHT
            + student.learner_autonomy * self._FLOOR_AUTONOMY_WEIGHT  # Moore: autonomous learners persist
        ) * self._FLOOR_SCALE  # Scale: max ~0.22 for high-resilience students
        return personal_floor
