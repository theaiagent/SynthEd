"""Epstein & Axtell (1996): Agent-based social simulation -- peer influence and contagion."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState
    from ..social_network import SocialNetwork


class EpsteinAxtellPeerInfluence:
    """Agent-based social simulation with peer influence and contagion."""

    def update_network(
        self,
        week: int,
        week_records: dict[str, list[InteractionRecord]],
        network: SocialNetwork,
    ) -> None:
        """
        Epstein & Axtell (1996): Form/strengthen links based on co-activity.
        Students who post in the same forum in the same week form weak ties.
        """
        # Group forum posters by course
        course_posters: dict[str, list[str]] = {}
        for sid, records in week_records.items():
            for r in records:
                if r.interaction_type == "forum_post":
                    course_posters.setdefault(r.course_id, []).append(sid)

        for _course_id, posters in course_posters.items():
            unique_posters = list(set(posters))
            for i, p1 in enumerate(unique_posters):
                for p2 in unique_posters[i + 1:]:
                    network.add_link(p1, p2, 0.05, "forum")
                    network.add_link(p2, p1, 0.05, "forum")

        # Live session co-attendance also forms ties
        course_live: dict[str, list[str]] = {}
        for sid, records in week_records.items():
            for r in records:
                if r.interaction_type == "live_session":
                    course_live.setdefault(r.course_id, []).append(sid)

        for _course_id, attendees in course_live.items():
            unique_attendees = list(set(attendees))
            for i, a1 in enumerate(unique_attendees):
                for a2 in unique_attendees[i + 1:]:
                    network.add_link(a1, a2, 0.03, "live_session")
                    network.add_link(a2, a1, 0.03, "live_session")

    def apply_peer_influence(
        self,
        student: StudentPersona,
        state: SimulationState,
        states: dict[str, SimulationState],
        network: SocialNetwork,
    ) -> None:
        """
        Epstein & Axtell (1996): Peer contagion effects.

        Three influence channels:
        1. Engagement contagion: peers pull engagement toward local mean
        2. Dropout contagion: peers in dropout phases increase risk
        3. Social integration reinforcement via peer connection
        """
        # Engagement contagion
        eng_influence = network.peer_influence(student.id, states, "current_engagement")
        state.current_engagement = float(np.clip(
            state.current_engagement + eng_influence, 0.01, 0.99
        ))

        # Dropout contagion
        contagion_penalty = network.dropout_contagion(student.id, states)
        if contagion_penalty > 0:
            state.current_engagement = float(np.clip(
                state.current_engagement - contagion_penalty, 0.01, 0.99
            ))

        # Peer connection reinforces social integration (Tinto via ABSS)
        degree = network.get_degree(student.id)
        if degree > 0:
            state.social_integration = float(np.clip(
                state.social_integration + min(degree * 0.003, 0.02), 0.01, 0.80
            ))
