"""Baeulke et al. (2022): Phase-oriented dropout progression."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import numpy as np

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

    def advance_phase(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        env: ODLEnvironment,
        avg_td_fn: Callable[[StudentPersona, SimulationState], float],
        rng: np.random.Generator,
    ) -> None:
        """
        Advance the dropout phase.

        0 -> 1: Non-fit perception -- sensing incongruence with program
        1 -> 2: Thoughts of quitting -- unsystematic consideration of alternatives
        2 -> 3: Deliberation -- consciously weighing pros/cons of staying vs leaving
        3 -> 4: Information search -- targeted search for alternative options
        4 -> 5: Final decision -- committed to withdraw
        """
        eng = state.current_engagement
        history = state.weekly_engagement_history
        avg_td = avg_td_fn(student, state)

        exhausted = hasattr(state, 'exhaustion') and state.exhaustion.exhaustion_level > 0.70

        if state.dropout_phase == 0:
            # Phase 0 -> 1: Non-fit perception
            # Gonzalez: high exhaustion accelerates non-fit perception
            if (eng < 0.40
                    or (eng < 0.45 and state.coi_state.cognitive_presence < 0.25)
                    or (eng < 0.45 and avg_td > 0.55)
                    or (eng < 0.45 and exhausted)):
                state.dropout_phase = 1
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Non-fit perception: questioning fit with program",
                                    "impact": -0.2})

        elif state.dropout_phase == 1:
            # Recovery back to 0 (harder in ODL -- fewer re-engagement mechanisms)
            if eng > 0.50:
                state.dropout_phase = 0
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Re-engaged with program", "impact": 0.2})
            # Phase 1 -> 2: Thoughts of quitting
            elif (eng < 0.36
                  and (state.missed_assignments_streak >= 1
                       or state.social_integration < 0.20)):
                state.dropout_phase = 2
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Thoughts of quitting: considering alternatives "
                                               "after experiencing difficulties",
                                    "impact": -0.25})

        elif state.dropout_phase == 2:
            # Recovery back to 1
            if eng > 0.45:
                state.dropout_phase = 1
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Renewed commitment, thoughts of quitting subsided",
                                    "impact": 0.15})
            # Phase 2 -> 3: Deliberation (requires sustained decline)
            elif eng < 0.32 and len(history) >= 2 and history[-1] < history[-2]:
                state.dropout_phase = 3
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Deliberation: actively weighing whether to continue",
                                    "impact": -0.3})

        elif state.dropout_phase == 3:
            # Recovery back to 2
            if eng > 0.40:
                state.dropout_phase = 2
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Stepped back from deliberation to thoughts of quitting",
                                    "impact": 0.1})
            # Phase 3 -> 4: Information search
            elif eng < 0.25 and state.perceived_cost_benefit < 0.40:
                state.dropout_phase = 4
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Information search: exploring alternatives "
                                               "to current program",
                                    "impact": -0.4})

        elif state.dropout_phase == 4:
            # Recovery still possible but unlikely
            if eng > 0.35 and state.perceived_cost_benefit > 0.45:
                state.dropout_phase = 3
            # Phase 4 -> 5: Final decision -- probabilistic, scaled by triggers
            else:
                triggers = 0
                if eng < 0.10:
                    triggers += 1  # Near-zero engagement
                if state.missed_assignments_streak >= 3:
                    triggers += 1  # Academic failure cascade
                if state.perceived_cost_benefit < 0.15:
                    triggers += 1  # Economic rationality: not worth it
                if student.financial_stress > 0.7:
                    triggers += 1  # Bean & Metzner: environmental crisis
                if exhausted:
                    triggers += 1  # Gonzalez: academic exhaustion crisis
                # Withdrawal deadline at ~70% of semester (Kember)
                withdrawal_week = int(env.total_weeks * 0.70)
                if week == withdrawal_week:
                    triggers += 1

                if triggers >= 1:
                    decision_prob = student.base_dropout_risk * triggers * 0.28
                    if rng.random() < decision_prob:
                        state.dropout_phase = 5
                        state.memory.append({"week": week, "event_type": "dropout",
                                            "details": "Decided to withdraw from program",
                                            "impact": -0.8})
