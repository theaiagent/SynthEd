"""Bean & Metzner (1985): Environmental pressure calculation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona


class BeanMetznerPressure:
    """Environmental pressure from work, family, and finances (Bean & Metzner, 1985)."""

    def calculate_environmental_pressure(self, student: StudentPersona) -> float:
        """
        Calculate environmental pressure for ODL students.

        ODL students face heavier external burdens (employment, family, finances).
        Returns a negative value representing engagement erosion.
        """
        env_pressure = 0.0
        if student.is_employed and student.weekly_work_hours > 30:
            env_pressure -= 0.025  # Overwork erodes engagement
        if student.has_family_responsibilities:
            env_pressure -= 0.02
        if student.financial_stress > 0.5:
            env_pressure -= 0.015
        return env_pressure
