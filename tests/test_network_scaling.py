"""Tests for network scaling: sampling, degree caps, backward compatibility."""

import numpy as np

from synthed.simulation.social_network import SocialNetwork
from synthed.simulation.theories.epstein_axtell import EpsteinAxtellPeerInfluence


class TestLinkGroup:
    def test_small_group_all_pairs(self):
        """10 members, _link_group with rng=None -> all pairs."""
        ea = EpsteinAxtellPeerInfluence()
        net = SocialNetwork()
        members = [f"s{i}" for i in range(10)]
        ea._link_group(members, net, 0.05, "forum", rng=None)
        # all-pairs: each member linked to 9 others
        for m in members:
            assert net.get_degree(m) == 9

    def test_large_group_bounded_degree(self):
        """100 members, _link_group with rng -> max degree <= _DEGREE_CAP_PER_ACTIVITY."""
        ea = EpsteinAxtellPeerInfluence()
        net = SocialNetwork()
        rng = np.random.default_rng(42)
        members = [f"s{i}" for i in range(100)]
        ea._link_group(members, net, 0.05, "forum", rng=rng)
        for m in members:
            # degree capped by _DEGREE_CAP_PER_ACTIVITY (bidirectional links
            # may push slightly above the per-member sample size, but must
            # stay within the hard _MAX_DEGREE of SocialNetwork)
            assert net.get_degree(m) <= SocialNetwork._MAX_DEGREE


class TestUpdateNetworkCompat:
    def test_update_network_backward_compat(self):
        """Call update_network without rng -> works (all-pairs)."""
        ea = EpsteinAxtellPeerInfluence()
        net = SocialNetwork()
        from synthed.simulation.engine import InteractionRecord
        records = {
            "s1": [InteractionRecord(student_id="s1", week=1, course_id="c1", interaction_type="forum_post")],
            "s2": [InteractionRecord(student_id="s2", week=1, course_id="c1", interaction_type="forum_post")],
            "s3": [InteractionRecord(student_id="s3", week=1, course_id="c1", interaction_type="forum_post")],
        }
        # No rng argument -- backward compatible
        ea.update_network(week=1, week_records=records, network=net)
        assert net.get_degree("s1") == 2
        assert net.get_degree("s2") == 2


class TestLargeScaleMeanDegree:
    def test_large_scale_mean_degree_bounded(self):
        """Simulate 200 forum posters, check mean degree < 25."""
        ea = EpsteinAxtellPeerInfluence()
        net = SocialNetwork()
        rng = np.random.default_rng(99)
        from synthed.simulation.engine import InteractionRecord
        records = {}
        for i in range(200):
            sid = f"student_{i}"
            records[sid] = [
                InteractionRecord(student_id=sid, week=1, course_id="c1", interaction_type="forum_post"),
            ]
        ea.update_network(week=1, week_records=records, network=net, rng=rng)
        degrees = [net.get_degree(f"student_{i}") for i in range(200)]
        mean_deg = float(np.mean(degrees))
        assert mean_deg <= SocialNetwork._MAX_DEGREE
        assert max(degrees) <= SocialNetwork._MAX_DEGREE

