"""Bean & Metzner (1985): Environmental pressure calculation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..state import SimulationState


class BeanMetznerPressure:
    """Environmental pressure from work, family, and finances (Bean & Metzner, 1985)."""

    # ── tuneable constants ──
    _OVERWORK_THRESHOLD_HOURS: int = 30       # weekly hours beyond which overwork penalty applies
    _OVERWORK_PENALTY: float = 0.025          # engagement erosion from overwork
    _FAMILY_PENALTY: float = 0.02             # engagement erosion from family responsibilities
    _FINANCIAL_STRESS_THRESHOLD: float = 0.5  # stress level triggering financial penalty
    _FINANCIAL_PENALTY: float = 0.015         # engagement erosion from financial stress
    _DISABILITY_PENALTY: float = 0.015           # engagement erosion from disability-related challenges
    _COPING_MAX: float = 0.50              # maximum coping factor (50% pressure reduction)
    _COPING_GROWTH_RATE: float = 0.03      # weekly growth rate (modulated by aptitude)
    _COPING_REG_WEIGHT: float = 0.60       # self-regulation weight in coping aptitude
    _COPING_CONSC_WEIGHT: float = 0.40     # conscientiousness weight in coping aptitude

    # ── Environmental shocks ──
    _SHOCK_BASE_PROB: float = 0.04
    _SHOCK_EMPLOY_WEIGHT: float = 0.3
    _SHOCK_FAMILY_WEIGHT: float = 0.3
    _SHOCK_STRESS_WEIGHT: float = 0.4
    _SHOCK_MIN_DURATION: int = 1
    _SHOCK_MAX_DURATION: int = 3
    _SHOCK_MIN_MAGNITUDE: float = 0.3
    _SHOCK_MAX_MAGNITUDE: float = 1.0

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
        if student.disability_severity > 0:
            env_pressure -= self._DISABILITY_PENALTY * student.disability_severity
        return env_pressure * (1.0 - coping_factor)

    def stochastic_pressure_event(
        self, student: StudentPersona, rng: np.random.Generator,
    ) -> tuple[int, float]:
        """Generate a stochastic environmental shock.

        Returns (duration, magnitude) or (0, 0.0) if no shock occurs.
        Risk is modulated by employment status, family responsibilities, and financial stress.
        """
        risk_score = (
            (1.0 if student.is_employed else 0.0) * self._SHOCK_EMPLOY_WEIGHT
            + (1.0 if student.has_family_responsibilities else 0.0) * self._SHOCK_FAMILY_WEIGHT
            + student.financial_stress * self._SHOCK_STRESS_WEIGHT
        )
        shock_prob = self._SHOCK_BASE_PROB * risk_score
        if rng.random() >= shock_prob:
            return 0, 0.0
        duration = int(rng.integers(self._SHOCK_MIN_DURATION, self._SHOCK_MAX_DURATION + 1))
        magnitude = float(rng.uniform(self._SHOCK_MIN_MAGNITUDE, self._SHOCK_MAX_MAGNITUDE))
        return duration, magnitude

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
