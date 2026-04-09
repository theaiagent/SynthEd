"""Gonzalez et al. (2025): Academic exhaustion as mediator of dropout."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ..institutional import InstitutionalConfig, scale_by

if TYPE_CHECKING:
    from ..state import InteractionRecord, SimulationState
    from ...agents.persona import StudentPersona


@dataclass
class ExhaustionState:
    """Gonzalez et al. (2025): Academic exhaustion as mediator.

    Exhaustion accumulates from workload, environmental stressors,
    and low self-regulation.  It erodes engagement and, above a
    threshold, accelerates Baulke dropout-phase progression.

    recovery_capacity degrades with sustained high exhaustion,
    modelling the cumulative toll described in the burnout literature.
    """

    exhaustion_level: float = 0.0   # 0-1
    recovery_capacity: float = 1.0  # 0-1; decreases with sustained exhaustion


class GonzalezExhaustion:
    """Academic-exhaustion mediator (Gonzalez et al., 2025).

    Accumulation sources
    --------------------
    * Active assignments in the current week
    * Environmental stressors (employment, family, financial stress)
    * Low self-regulation

    Recovery sources
    ----------------
    * High resilience (self_regulation + conscientiousness)
    * Positive environmental events
    * recovery_capacity (degrades when exhaustion stays high)
    """

    # ── tuneable constants (kept moderate to avoid >90 % dropout) ──
    _ASSIGNMENT_LOAD_WEIGHT: float = 0.025
    _STRESSOR_WEIGHT: float = 0.020
    _LOW_REGULATION_WEIGHT: float = 0.015
    _RECOVERY_BASE: float = 0.035
    _RECOVERY_CAP_DECAY: float = 0.02
    _RECOVERY_CAP_REGEN: float = 0.01
    _ENGAGEMENT_IMPACT: float = 0.04
    _DROPOUT_THRESHOLD: float = 0.70

    # ------------------------------------------------------------------
    def update_exhaustion(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        context: dict,
        records: list[InteractionRecord],
        inst: InstitutionalConfig | None = None,
    ) -> None:
        """Advance exhaustion for one student-week."""
        ex = state.exhaustion
        accumulation = 0.0

        # 1. Assignment load this week
        active_assignments = len(context.get("active_assignments", []))
        effective_alw = scale_by(
            self._ASSIGNMENT_LOAD_WEIGHT,
            1.0 - (inst.curriculum_flexibility if inst else 0.5),
        )  # [inst: curriculum_flexibility] inverted
        accumulation += active_assignments * effective_alw

        # 2. Environmental stressors (Bean & Metzner overlap)
        if student.is_employed:
            accumulation += (student.weekly_work_hours / 40.0) * self._STRESSOR_WEIGHT
        if student.has_family_responsibilities:
            accumulation += self._STRESSOR_WEIGHT * 0.6
        accumulation += student.financial_stress * self._STRESSOR_WEIGHT

        # 3. Low self-regulation amplifies exhaustion
        accumulation += max(0.0, 0.5 - student.self_regulation) * self._LOW_REGULATION_WEIGHT

        # ── Recovery ──
        resilience = (student.self_regulation + student.personality.conscientiousness) / 2.0
        effective_rb = scale_by(
            self._RECOVERY_BASE,
            inst.support_services_quality if inst else 0.5,
        )  # [inst: support_services_quality]
        recovery = effective_rb * resilience * ex.recovery_capacity

        # Positive events grant a bonus recovery burst
        if context.get("positive_event"):
            recovery += 0.02

        # ── Net change ──
        delta = accumulation - recovery
        ex.exhaustion_level = float(np.clip(ex.exhaustion_level + delta, 0.0, 1.0))

        # ── Recovery-capacity degradation / regeneration ──
        if ex.exhaustion_level > 0.60:
            ex.recovery_capacity = float(
                np.clip(ex.recovery_capacity - self._RECOVERY_CAP_DECAY, 0.1, 1.0)
            )
        elif ex.exhaustion_level < 0.30:
            ex.recovery_capacity = float(
                np.clip(ex.recovery_capacity + self._RECOVERY_CAP_REGEN, 0.1, 1.0)
            )

    # ------------------------------------------------------------------
    def exhaustion_engagement_effect(self, state: SimulationState) -> float:
        """Return the negative engagement delta caused by exhaustion."""
        return -state.exhaustion.exhaustion_level * self._ENGAGEMENT_IMPACT

    # ------------------------------------------------------------------
    def exhaustion_accelerates_dropout(self, state: SimulationState) -> bool:
        """Return *True* when exhaustion exceeds the acceleration threshold."""
        return state.exhaustion.exhaustion_level > self._DROPOUT_THRESHOLD
