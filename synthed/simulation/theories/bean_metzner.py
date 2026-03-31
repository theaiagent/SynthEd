"""Bean & Metzner (1985): Environmental pressure calculation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import SimulationState


class BeanMetznerPressure:
    """Environmental pressure from work, family, and finances (Bean & Metzner, 1985)."""

    # ── tuneable constants ──
    _OVERWORK_THRESHOLD_HOURS: int = 30       # weekly hours beyond which overwork penalty applies
    _OVERWORK_PENALTY: float = 0.025          # engagement erosion from overwork
    _FAMILY_PENALTY: float = 0.02             # engagement erosion from family responsibilities
    _FINANCIAL_STRESS_THRESHOLD: float = 0.5  # stress level triggering financial penalty
    _FINANCIAL_PENALTY: float = 0.015         # engagement erosion from financial stress
    _COPING_MAX: float = 0.50              # maximum coping factor (50% pressure reduction)
    _COPING_GROWTH_RATE: float = 0.03      # weekly growth rate (modulated by aptitude)
    _COPING_REG_WEIGHT: float = 0.60       # self-regulation weight in coping aptitude
    _COPING_CONSC_WEIGHT: float = 0.40     # conscientiousness weight in coping aptitude

    def calculate_environmental_pressure(
        self, student: StudentPersona, coping_factor: float = 0.0,
    ) -> float:
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
        return env_pressure * (1.0 - coping_factor)

    def update_coping(self, student: StudentPersona, state: SimulationState) -> None:
        """Advance coping_factor based on student aptitude (weekly call).

        Growth follows diminishing returns: faster when coping is low,
        slower as it approaches the cap. Self-regulation and conscientiousness
        jointly determine coping aptitude.
        """
        aptitude = (
            student.self_regulation * self._COPING_REG_WEIGHT
            + student.personality.conscientiousness * self._COPING_CONSC_WEIGHT
        )
        growth = self._COPING_GROWTH_RATE * aptitude * (self._COPING_MAX - state.coping_factor)
        state.coping_factor = float(np.clip(
            state.coping_factor + growth, 0.0, self._COPING_MAX,
        ))
