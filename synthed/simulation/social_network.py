"""
SocialNetwork: Emergent peer network for agent-based social simulation.

Implements Epstein & Axtell (1996) principles:
- Bottom-up network formation through shared activity (forum co-posting)
- Local averaging rule for peer influence on engagement
- Dropout contagion through network neighborhoods
- Emergent social stratification as a collective property
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PeerLink:
    """A single edge in the peer network: strength + link type."""
    strength: float = 0.1   # 0-1; aggregated influence weight
    link_types: frozenset[str] = frozenset({"forum"})  # forum, live_session, cohort


class SocialNetwork:
    """
    Epstein & Axtell (1996): Emergent social structure from agent interactions.

    Students form connections through shared forum activity, live sessions,
    and cohort membership. Connections mediate influence on engagement,
    motivation, and dropout contagion.

    Edges are stored as source → {target → PeerLink}, where each PeerLink
    tracks aggregated strength and the set of link types that formed the bond.
    """

    _MAX_DEGREE: int = 25  # hard cap on unique neighbors per node

    def __init__(self) -> None:
        self._link_count: int = 0
        self._adjacency: dict[str, dict[str, PeerLink]] = {}

    def add_link(
        self, source_id: str, target_id: str,
        strength: float = 0.1, link_type: str = "forum",
    ) -> None:
        """Add or strengthen a peer link, tracking link type."""
        self._link_count += 1
        neighbors = self._adjacency.setdefault(source_id, {})
        existing = neighbors.get(target_id)
        if existing is not None:
            # Strengthening existing links is always allowed
            neighbors[target_id] = PeerLink(
                strength=min(existing.strength + strength, 1.0),
                link_types=existing.link_types | {link_type},
            )
        else:
            # New link: enforce hard degree cap
            if len(neighbors) >= self._MAX_DEGREE:
                return
            neighbors[target_id] = PeerLink(
                strength=strength,
                link_types=frozenset({link_type}),
            )

    def decay_links(self, decay_rate: float = 0.02, min_strength: float = 0.01) -> int:
        """
        Decay all link strengths by decay_rate. Remove links below min_strength.
        Returns count of removed links.
        """
        removed = 0
        for source_id in list(self._adjacency.keys()):
            neighbors = self._adjacency[source_id]
            to_remove = []
            for target_id, link in neighbors.items():
                new_strength = link.strength - decay_rate
                if new_strength < min_strength:
                    to_remove.append(target_id)
                    removed += 1
                else:
                    neighbors[target_id] = PeerLink(
                        strength=new_strength,
                        link_types=link.link_types,
                    )
            for tid in to_remove:
                del neighbors[tid]
            if not neighbors:
                del self._adjacency[source_id]
        return removed

    def get_neighbors(self, student_id: str) -> list[str]:
        """Return IDs of all peers connected to this student."""
        return list(self._adjacency.get(student_id, {}).keys())

    def get_link(self, source_id: str, target_id: str) -> PeerLink | None:
        """Return the PeerLink between two students, or None."""
        return self._adjacency.get(source_id, {}).get(target_id)

    def get_degree(self, student_id: str) -> int:
        """Return the number of unique peers connected to this student."""
        return len(self._adjacency.get(student_id, {}))

    def peer_influence(
        self, student_id: str, states: dict[str, Any],
        attribute: str = "current_engagement",
    ) -> float:
        """
        Calculate peer influence on a given attribute.

        Epstein & Axtell: local averaging rule with decay.
        Returns influence delta (can be positive or negative).
        """
        neighbors = self._adjacency.get(student_id, {})
        if not neighbors:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0
        for nid, link in neighbors.items():
            state = states.get(nid)
            if state is not None:
                val = getattr(state, attribute, None)
                if val is not None:
                    weighted_sum += val * link.strength
                    weight_total += link.strength

        if weight_total == 0:
            return 0.0

        peer_mean = weighted_sum / weight_total
        own_state = states.get(student_id)
        if own_state is None:
            return 0.0
        own_val = getattr(own_state, attribute, 0.5)
        # 10% pull toward weighted peer mean
        return (peer_mean - own_val) * 0.1

    def dropout_contagion(
        self, student_id: str, states: dict[str, Any],
    ) -> float:
        """
        Epstein & Axtell: Dropout cascade/tipping point effect.

        Returns additional engagement penalty based on proportion of
        neighbors in advanced dropout phases (>= 3).
        """
        neighbors = self._adjacency.get(student_id, {})
        if not neighbors:
            return 0.0

        dropout_neighbors = sum(
            1 for nid in neighbors
            if nid in states and getattr(states[nid], "dropout_phase", 0) >= 4
        )
        if dropout_neighbors == 0:
            return 0.0

        proportion = dropout_neighbors / len(neighbors)
        return proportion * 0.02

    def network_statistics(self, states: dict[str, Any]) -> dict[str, Any]:
        """Compute summary statistics about the social network."""
        all_ids = set(self._adjacency.keys())
        degrees = [self.get_degree(sid) for sid in all_ids]

        if not degrees:
            return {
                "total_nodes": 0, "total_edges": 0,
                "mean_degree": 0.0, "max_degree": 0,
                "isolates": 0,
            }

        # Count dropout clustering
        dropout_ids = {
            sid for sid in all_ids
            if sid in states and getattr(states[sid], "has_dropped_out", False)
        }
        dropout_neighbor_overlap = 0
        for sid in dropout_ids:
            neighbors = set(self.get_neighbors(sid))
            dropout_neighbor_overlap += len(neighbors & dropout_ids)

        # Count unique edges and link type distribution
        unique_edges = sum(len(targets) for targets in self._adjacency.values())
        link_type_counts: dict[str, int] = {}
        for targets in self._adjacency.values():
            for link in targets.values():
                for lt in link.link_types:
                    link_type_counts[lt] = link_type_counts.get(lt, 0) + 1

        return {
            "total_nodes": len(all_ids),
            "total_link_events": self._link_count,
            "unique_edges": unique_edges,
            "mean_degree": float(np.mean(degrees)),
            "max_degree": max(degrees),
            "isolates": sum(1 for d in degrees if d == 0),
            "link_type_distribution": link_type_counts,
            "dropout_neighbor_overlap": dropout_neighbor_overlap,
        }
