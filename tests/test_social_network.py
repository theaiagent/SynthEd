"""Tests for SocialNetwork."""

from synthed.simulation.social_network import SocialNetwork
from synthed.simulation.engine import SimulationState


class TestSocialNetwork:
    def test_add_link_creates_connection(self):
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.5)
        assert "b" in net.get_neighbors("a")

    def test_add_link_strengthens_existing(self):
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.3)
        net.add_link("a", "b", strength=0.2)
        link = net.get_link("a", "b")
        assert link is not None
        assert abs(link.strength - 0.5) < 1e-9

    def test_get_degree_counts_unique_neighbors(self):
        net = SocialNetwork()
        net.add_link("a", "b")
        net.add_link("a", "c")
        net.add_link("a", "d")
        assert net.get_degree("a") == 3

    def test_peer_influence_pulls_toward_mean(self):
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.5)
        net.add_link("a", "c", strength=0.5)
        states = {
            "a": SimulationState(student_id="a", current_engagement=0.3),
            "b": SimulationState(student_id="b", current_engagement=0.8),
            "c": SimulationState(student_id="c", current_engagement=0.8),
        }
        influence = net.peer_influence("a", states)
        # peer mean is 0.8, own is 0.3, pull should be positive
        assert influence > 0

    def test_decay_links_removes_weak(self):
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.03)
        removed = net.decay_links(decay_rate=0.02, min_strength=0.02)
        assert removed == 1
        assert net.get_degree("a") == 0

    def test_network_statistics_keys(self):
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.5)
        stats = net.network_statistics({})
        expected_keys = ["total_nodes", "unique_edges", "mean_degree", "max_degree"]
        for key in expected_keys:
            assert key in stats

    def test_add_link_respects_max_degree(self):
        net = SocialNetwork()
        for i in range(30):
            net.add_link("s1", f"target_{i}", 0.1, "forum")
        assert net.get_degree("s1") == SocialNetwork._MAX_DEGREE

    def test_strengthening_allowed_at_cap(self):
        net = SocialNetwork()
        for i in range(25):
            net.add_link("s1", f"t_{i}", 0.1, "forum")
        net.add_link("s1", "t_0", 0.1, "forum")  # strengthen existing
        link = net.get_link("s1", "t_0")
        assert link is not None
        assert abs(link.strength - 0.2) < 1e-9  # was 0.1, now 0.2

    def test_peer_influence_neighbors_not_in_states(self):
        """peer_influence returns 0.0 when neighbors have no state data (line 129)."""
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.5)
        # States dict does not contain neighbor "b"
        states = {"a": SimulationState(student_id="a", current_engagement=0.5)}
        influence = net.peer_influence("a", states)
        assert influence == 0.0

    def test_peer_influence_own_state_missing(self):
        """peer_influence returns 0.0 when own state is not in states dict (line 134)."""
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.5)
        # States has the neighbor but not the student itself
        states = {"b": SimulationState(student_id="b", current_engagement=0.8)}
        influence = net.peer_influence("a", states)
        assert influence == 0.0

    def test_network_statistics_with_dropout_clustering(self):
        """network_statistics counts dropout neighbor overlap (lines 181-182)."""
        net = SocialNetwork()
        net.add_link("a", "b", strength=0.5)
        net.add_link("b", "c", strength=0.5)
        # Both a and b are dropped out, connected to each other
        states = {
            "a": SimulationState(student_id="a", has_dropped_out=True),
            "b": SimulationState(student_id="b", has_dropped_out=True),
            "c": SimulationState(student_id="c", has_dropped_out=False),
        }
        stats = net.network_statistics(states)
        # Dropout clustering should be computed
        assert "dropout_neighbor_overlap" in stats
        assert stats["dropout_neighbor_overlap"] >= 1
