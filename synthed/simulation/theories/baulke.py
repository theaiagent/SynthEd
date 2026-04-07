"""Baeulke et al. (2022): Phase-oriented dropout progression."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import numpy as np

from ..institutional import InstitutionalConfig, scale_by

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import SimulationState
    from ..environment import ODLEnvironment


class BaulkeDropoutPhase:
    """
    Advance the dropout phase based on Baeulke, Grunschel & Dresel (2022).

    Six-phase model integrating Betsch (2005) decision-making and
    Rubicon action-phase model (Achtziger & Gollwitzer, 2010).
    """

    # ── phase 0 → 1: non-fit perception ──
    _NONFIT_ENG_THRESHOLD: float = 0.40          # engagement below this triggers non-fit
    _NONFIT_ENG_SOFT: float = 0.45               # softer threshold when combined with other factors
    _NONFIT_COG_THRESHOLD: float = 0.25           # cognitive presence threshold for soft trigger
    _NONFIT_TD_THRESHOLD: float = 0.55            # transactional distance threshold for soft trigger
    _EXHAUSTION_THRESHOLD: float = 0.70           # exhaustion level that accelerates dropout
    _NONFIT_GPA_THRESHOLD: float = 1.6          # GPA below this contributes to non-fit perception
    _NONFIT_GPA_MIN_ITEMS: int = 2             # minimum graded items for non-fit GPA signal
    _TRIGGER_GPA_THRESHOLD: float = 1.2        # GPA below this is an additional phase 4->5 trigger
    _TRIGGER_GPA_MIN_ITEMS: int = 2            # minimum graded items for phase 4->5 GPA trigger
    _NONFIT_MASTERY_THRESHOLD: float = 0.4    # perceived mastery below this contributes to non-fit
    _TRIGGER_MASTERY_THRESHOLD: float = 0.3   # perceived mastery below this is phase 4->5 trigger

    # ── phase 1 → 0 / 1 → 2 ──
    _RECOVERY_1_TO_0: float = 0.50               # engagement above this recovers to phase 0
    _PHASE_1_TO_2_ENG: float = 0.36              # engagement below this advances to phase 2
    _PHASE_1_SOCIAL_THRESHOLD: float = 0.20       # social integration threshold for phase 2

    # ── phase 2 → 1 / 2 → 3 ──
    _RECOVERY_2_TO_1: float = 0.45               # engagement above this recovers to phase 1
    _PHASE_2_TO_3_ENG: float = 0.32              # engagement below this advances to phase 3
    _SHOCK_SEVERITY_THRESHOLD: float = 0.7       # shock magnitude above this triggers phase 2→3

    # ── phase 3 → 2 / 3 → 4 ──
    _RECOVERY_3_TO_2: float = 0.40               # engagement above this recovers to phase 2
    _PHASE_3_TO_4_ENG: float = 0.25              # engagement below this advances to phase 4
    _PHASE_3_TO_4_CB: float = 0.40               # cost-benefit threshold for phase 4

    # ── phase 4 → 3 / 4 → 5 ──
    _RECOVERY_4_TO_3_ENG: float = 0.35           # engagement above this recovers to phase 3
    _RECOVERY_4_TO_3_CB: float = 0.45            # cost-benefit above this recovers to phase 3
    _TRIGGER_ENG_THRESHOLD: float = 0.10          # near-zero engagement trigger
    _TRIGGER_MISSED_STREAK: int = 3               # missed assignment streak trigger
    _TRIGGER_CB_THRESHOLD: float = 0.15           # cost-benefit "not worth it" trigger
    _TRIGGER_FINANCIAL_THRESHOLD: float = 0.7     # financial stress crisis trigger
    _WITHDRAWAL_WEEK_FRACTION: float = 0.70       # fraction of semester for withdrawal deadline
    _DECISION_RISK_MULTIPLIER: float = 0.28       # scales base_dropout_risk per trigger

    # ── memory impact values ──
    _IMPACT_NONFIT: float = -0.2
    _IMPACT_RECOVERY_1_TO_0: float = 0.2
    _IMPACT_PHASE_2: float = -0.25
    _IMPACT_RECOVERY_2_TO_1: float = 0.15
    _IMPACT_PHASE_3: float = -0.3
    _IMPACT_RECOVERY_3_TO_2: float = 0.1
    _IMPACT_PHASE_4: float = -0.4
    _IMPACT_DROPOUT: float = -0.8

    def _modulated_thresholds(self, ssq: float) -> dict[str, float]:
        """Compute phase-transition thresholds scaled by institutional SSQ.

        All thresholds use ``1.0 - ssq`` (inverted) so that higher SSQ
        (better institution) produces *lower* numeric thresholds.  For
        forward thresholds this means the student must be in worse shape
        to advance toward dropout.  For recovery thresholds a lower bar
        means the student recovers more easily.  Exhaustion is the sole
        exception — it uses direct ``ssq`` so better institutions raise
        the bar for what counts as "exhausted".

        At SSQ = 0.5, every value equals its class constant exactly.
        """
        inv = 1.0 - ssq
        return {
            "nonfit_eng": scale_by(self._NONFIT_ENG_THRESHOLD, inv),
            "nonfit_eng_soft": scale_by(self._NONFIT_ENG_SOFT, inv),
            "phase_1_to_2_eng": scale_by(self._PHASE_1_TO_2_ENG, inv),
            "phase_1_social": scale_by(self._PHASE_1_SOCIAL_THRESHOLD, inv),
            "phase_2_to_3_eng": scale_by(self._PHASE_2_TO_3_ENG, inv),
            "phase_3_to_4_eng": scale_by(self._PHASE_3_TO_4_ENG, inv),
            "trigger_eng": scale_by(self._TRIGGER_ENG_THRESHOLD, inv),
            "recovery_1_to_0": scale_by(self._RECOVERY_1_TO_0, inv),
            "recovery_2_to_1": scale_by(self._RECOVERY_2_TO_1, inv),
            "recovery_3_to_2": scale_by(self._RECOVERY_3_TO_2, inv),
            "recovery_4_to_3_eng": scale_by(self._RECOVERY_4_TO_3_ENG, inv),
            "recovery_4_to_3_cb": scale_by(self._RECOVERY_4_TO_3_CB, inv),
            "exhaustion": scale_by(self._EXHAUSTION_THRESHOLD, ssq),
        }

    def advance_phase(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        env: ODLEnvironment,
        avg_td_fn: Callable[[StudentPersona, SimulationState], float],
        rng: np.random.Generator,
        inst: InstitutionalConfig | None = None,
    ) -> None:
        """
        Advance the dropout phase.

        0 -> 1: Non-fit perception -- sensing incongruence with program
        1 -> 2: Thoughts of quitting -- unsystematic consideration of alternatives
        2 -> 3: Deliberation -- consciously weighing pros/cons of staying vs leaving
        3 -> 4: Information search -- targeted search for alternative options
        4 -> 5: Final decision -- committed to withdraw

        Parameters
        ----------
        inst : InstitutionalConfig | None
            If provided, ``support_services_quality`` modulates phase
            transition thresholds via :func:`scale_by`.  At the default
            SSQ = 0.5 all thresholds equal the class constants exactly.
        """
        ssq = inst.support_services_quality if inst is not None else 0.5
        t = self._modulated_thresholds(ssq)

        eng = state.current_engagement
        history = state.weekly_engagement_history
        avg_td = avg_td_fn(student, state)

        exhausted = hasattr(state, 'exhaustion') and state.exhaustion.exhaustion_level > t["exhaustion"]

        if state.dropout_phase == 0:
            # Phase 0 -> 1: Non-fit perception
            # Gonzalez: high exhaustion accelerates non-fit perception
            if (eng < t["nonfit_eng"]
                    or (eng < t["nonfit_eng_soft"] and state.coi_state.cognitive_presence < self._NONFIT_COG_THRESHOLD)
                    or (eng < t["nonfit_eng_soft"] and avg_td > self._NONFIT_TD_THRESHOLD)
                    or (eng < t["nonfit_eng_soft"] and exhausted)
                    or (eng < t["nonfit_eng_soft"]
                        and state.perceived_mastery_count >= self._NONFIT_GPA_MIN_ITEMS
                        and state.perceived_mastery < self._NONFIT_MASTERY_THRESHOLD)):
                state.dropout_phase = 1
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Non-fit perception: questioning fit with program",
                                    "impact": self._IMPACT_NONFIT})

        elif state.dropout_phase == 1:
            # Recovery back to 0 (harder in ODL -- fewer re-engagement mechanisms)
            if eng > t["recovery_1_to_0"]:
                state.dropout_phase = 0
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Re-engaged with program", "impact": self._IMPACT_RECOVERY_1_TO_0})
            # Phase 1 -> 2: Thoughts of quitting
            elif (eng < t["phase_1_to_2_eng"]
                  and (state.missed_assignments_streak >= 1
                       or state.social_integration < t["phase_1_social"])):
                state.dropout_phase = 2
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Thoughts of quitting: considering alternatives "
                                               "after experiencing difficulties",
                                    "impact": self._IMPACT_PHASE_2})

        elif state.dropout_phase == 2:
            # Recovery back to 1
            if eng > t["recovery_2_to_1"]:
                state.dropout_phase = 1
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Renewed commitment, thoughts of quitting subsided",
                                    "impact": self._IMPACT_RECOVERY_2_TO_1})
            # Phase 2 -> 3: Deliberation (requires sustained decline or severe life shock)
            elif (eng < t["phase_2_to_3_eng"] and len(history) >= 2 and history[-1] < history[-2]
                    or (state.env_shock_remaining > 0
                        and state.env_shock_magnitude > self._SHOCK_SEVERITY_THRESHOLD)):
                state.dropout_phase = 3
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Deliberation: actively weighing whether to continue",
                                    "impact": self._IMPACT_PHASE_3})

        elif state.dropout_phase == 3:
            # Recovery back to 2
            if eng > t["recovery_3_to_2"]:
                state.dropout_phase = 2
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Stepped back from deliberation to thoughts of quitting",
                                    "impact": self._IMPACT_RECOVERY_3_TO_2})
            # Phase 3 -> 4: Information search
            elif eng < t["phase_3_to_4_eng"] and state.perceived_cost_benefit < self._PHASE_3_TO_4_CB:
                state.dropout_phase = 4
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Information search: exploring alternatives "
                                               "to current program",
                                    "impact": self._IMPACT_PHASE_4})

        elif state.dropout_phase == 4:
            # Recovery still possible but unlikely
            if eng > t["recovery_4_to_3_eng"] and state.perceived_cost_benefit > t["recovery_4_to_3_cb"]:
                state.dropout_phase = 3
            # Phase 4 -> 5: Final decision -- probabilistic, scaled by triggers
            else:
                triggers = 0
                if eng < t["trigger_eng"]:
                    triggers += 1  # Near-zero engagement
                if state.missed_assignments_streak >= self._TRIGGER_MISSED_STREAK:
                    triggers += 1  # Academic failure cascade
                if state.perceived_cost_benefit < self._TRIGGER_CB_THRESHOLD:
                    triggers += 1  # Economic rationality: not worth it
                if student.financial_stress > self._TRIGGER_FINANCIAL_THRESHOLD:
                    triggers += 1  # Bean & Metzner: environmental crisis
                if exhausted:
                    triggers += 1  # Gonzalez: academic exhaustion crisis
                if (state.perceived_mastery_count >= self._TRIGGER_GPA_MIN_ITEMS
                        and state.perceived_mastery < self._TRIGGER_MASTERY_THRESHOLD):
                    triggers += 1  # Academic failure: mastery below recoverable threshold
                # Withdrawal deadline at ~70% of semester (Kember)
                withdrawal_week = int(env.total_weeks * self._WITHDRAWAL_WEEK_FRACTION)
                if week == withdrawal_week:
                    triggers += 1

                if triggers >= 1:
                    decision_prob = student.base_dropout_risk * triggers * self._DECISION_RISK_MULTIPLIER
                    if rng.random() < decision_prob:
                        state.dropout_phase = 5
                        state.memory.append({"week": week, "event_type": "dropout",
                                            "details": "Decided to withdraw from program",
                                            "impact": self._IMPACT_DROPOUT})
