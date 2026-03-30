"""Bean & Metzner (1985): Environmental pressure calculation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona


class BeanMetznerPressure:
    """Environmental pressure from work, family, and finances (Bean & Metzner, 1985)."""

    # ── tuneable constants ──
    _OVERWORK_THRESHOLD_HOURS: int = 30       # weekly hours beyond which overwork penalty applies
    _OVERWORK_PENALTY: float = 0.025          # engagement erosion from overwork
    _FAMILY_PENALTY: float = 0.02             # engagement erosion from family responsibilities
    _FINANCIAL_STRESS_THRESHOLD: float = 0.5  # stress level triggering financial penalty
    _FINANCIAL_PENALTY: float = 0.015         # engagement erosion from financial stress

    def calculate_environmental_pressure(self, student: StudentPersona) -> float:
        """
        Calculate environmental pressure for ODL students.

        ODL students face heavier external burdens (employment, family, finances).
        Returns a negative value representing engagement erosion.
        """
        env_pressure = 0.0
        if student.is_employed and student.weekly_work_hours > self._OVERWORK_THRESHOLD_HOURS:
            env_pressure -= self._OVERWORK_PENALTY  # Overwork erodes engagement
        if student.has_family_responsibilities:
            env_pressure -= self._FAMILY_PENALTY
        if student.financial_stress > self._FINANCIAL_STRESS_THRESHOLD:
            env_pressure -= self._FINANCIAL_PENALTY
        return env_pressure
