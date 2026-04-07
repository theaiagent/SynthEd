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

    # ── tuneable constants ──
    _FORUM_LINK_WEIGHT: float = 0.05         # tie strength from co-posting in a forum
    _LIVE_LINK_WEIGHT: float = 0.03          # tie strength from co-attending live session
    _SOCIAL_DEGREE_FACTOR: float = 0.003     # social integration boost per network degree
    _SOCIAL_DEGREE_CAP: float = 0.02         # max social integration boost from peers
    _ENGAGEMENT_CLIP_LO: float = 0.01        # engagement lower bound
    _ENGAGEMENT_CLIP_HI: float = 0.99        # engagement upper bound
    _SOCIAL_CLIP_HI: float = 0.80            # social integration upper bound
    _SAMPLING_THRESHOLD: int = 40            # group size above which we sample peers
    _DEGREE_CAP_PER_ACTIVITY: int = 20       # max peers sampled per activity type

    def _link_group(
        self,
        members: list[str],
        network: SocialNetwork,
        weight: float,
        link_type: str,
        rng: np.random.Generator | None,
    ) -> None:
        """Link members of a co-activity group, sampling for large groups."""
        unique = list(set(members))
        n = len(unique)
        if n < self._SAMPLING_THRESHOLD or rng is None:
            # All-pairs linking (existing behaviour)
            for i, m1 in enumerate(unique):
                for m2 in unique[i + 1:]:
                    network.add_link(m1, m2, weight, link_type)
                    network.add_link(m2, m1, weight, link_type)
        else:
            # Each member samples a bounded subset of random peers
            k = min(self._DEGREE_CAP_PER_ACTIVITY, n - 1)
            for m in unique:
                others = [o for o in unique if o != m]
                sampled = rng.choice(others, size=k, replace=False)
                for peer in sampled:
                    network.add_link(m, peer, weight, link_type)
                    network.add_link(peer, m, weight, link_type)

    def update_network(
        self,
        week: int,
        week_records: dict[str, list[InteractionRecord]],
        network: SocialNetwork,
        rng: np.random.Generator | None = None,
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
            self._link_group(posters, network, self._FORUM_LINK_WEIGHT, "forum", rng)

        # Live session co-attendance also forms ties
        course_live: dict[str, list[str]] = {}
        for sid, records in week_records.items():
            for r in records:
                if r.interaction_type == "live_session":
                    course_live.setdefault(r.course_id, []).append(sid)

        for _course_id, attendees in course_live.items():
            self._link_group(attendees, network, self._LIVE_LINK_WEIGHT, "live_session", rng)

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
            state.current_engagement + eng_influence, self._ENGAGEMENT_CLIP_LO, self._ENGAGEMENT_CLIP_HI
        ))

        # Dropout contagion
        contagion_penalty = network.dropout_contagion(student.id, states)
        if contagion_penalty > 0:
            state.current_engagement = float(np.clip(
                state.current_engagement - contagion_penalty, self._ENGAGEMENT_CLIP_LO, self._ENGAGEMENT_CLIP_HI
            ))

        # Peer connection reinforces social integration (Tinto via ABSS)
        degree = network.get_degree(student.id)
        if degree > 0:
            state.social_integration = float(np.clip(
                state.social_integration + min(degree * self._SOCIAL_DEGREE_FACTOR, self._SOCIAL_DEGREE_CAP),
                self._ENGAGEMENT_CLIP_LO, self._SOCIAL_CLIP_HI
            ))

