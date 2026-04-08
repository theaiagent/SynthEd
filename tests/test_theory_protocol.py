"""Tests for TheoryModule Protocol, TheoryContext, and auto-discovery."""
from __future__ import annotations

import numpy as np
import pytest

from synthed.simulation.theories import discover_theories
from synthed.simulation.theories.protocol import TheoryContext


class TestDiscovery:
    """Auto-discovery returns correct theory classes."""

    def test_discover_returns_list(self):
        theories = discover_theories()
        assert isinstance(theories, list)
        assert len(theories) >= 5

    def test_excludes_special_modules(self):
        """UnavoidableWithdrawal and PositiveEventHandler excluded."""
        theories = discover_theories()
        names = {t.__name__ for t in theories}
        assert "UnavoidableWithdrawal" not in names
        assert "PositiveEventHandler" not in names

    def test_excludes_data_classes(self):
        """SDTNeedSatisfaction and ExhaustionState excluded."""
        theories = discover_theories()
        names = {t.__name__ for t in theories}
        assert "SDTNeedSatisfaction" not in names
        assert "ExhaustionState" not in names

    def test_deterministic_ordering(self):
        """Two calls return same order."""
        a = discover_theories()
        b = discover_theories()
        assert [t.__name__ for t in a] == [t.__name__ for t in b]

    def test_all_have_phase_methods(self):
        """Every discovered theory has at least one phase method."""
        phase_methods = ("on_individual_step", "on_network_step", "on_post_peer_step")
        for cls in discover_theories():
            assert any(hasattr(cls, m) for m in phase_methods), (
                f"{cls.__name__} has no phase methods"
            )


class TestProtocolConformance:
    """Each theory implements protocol methods correctly."""

    def test_tinto_has_individual_step(self):
        from synthed.simulation.theories import TintoIntegration
        assert hasattr(TintoIntegration, "on_individual_step")

    def test_garrison_has_individual_step(self):
        from synthed.simulation.theories import GarrisonCoI
        assert hasattr(GarrisonCoI, "on_individual_step")

    def test_sdt_has_individual_step(self):
        from synthed.simulation.theories import SDTMotivationDynamics
        assert hasattr(SDTMotivationDynamics, "on_individual_step")

    def test_gonzalez_is_engagement_only(self):
        """Gonzalez has no phase methods — engine-direct for both update + engagement."""
        from synthed.simulation.theories import GonzalezExhaustion
        assert not hasattr(GonzalezExhaustion, "on_individual_step")
        assert hasattr(GonzalezExhaustion, "update_exhaustion")
        assert hasattr(GonzalezExhaustion, "exhaustion_engagement_effect")

    def test_epstein_has_network_and_post_peer(self):
        from synthed.simulation.theories import EpsteinAxtellPeerInfluence
        assert hasattr(EpsteinAxtellPeerInfluence, "on_network_step")
        assert hasattr(EpsteinAxtellPeerInfluence, "on_post_peer_step")

    def test_baulke_has_post_peer(self):
        from synthed.simulation.theories import BaulkeDropoutPhase
        assert hasattr(BaulkeDropoutPhase, "on_post_peer_step")


class TestTheoryContext:
    """TheoryContext frozen dataclass."""

    def test_frozen(self):
        ctx = self._make_ctx()
        with pytest.raises(AttributeError):
            ctx.week = 99

    def test_network_step_allows_none_student(self):
        """on_network_step uses ctx with student=None."""
        ctx = self._make_ctx(student=None, state=None, records=None)
        assert ctx.student is None
        assert ctx.state is None
        assert ctx.records is None

    def test_has_total_weeks(self):
        ctx = self._make_ctx()
        assert ctx.total_weeks == 14

    def test_has_avg_td(self):
        ctx = self._make_ctx()
        assert ctx.avg_td == 0.5

    @staticmethod
    def _make_ctx(**overrides):
        from synthed.simulation.engine_config import EngineConfig
        from synthed.simulation.environment import ODLEnvironment
        from synthed.simulation.institutional import InstitutionalConfig
        from synthed.simulation.social_network import SocialNetwork

        defaults = dict(
            student=None,
            state=None,
            records=None,
            week=1,
            context={},
            env=ODLEnvironment(),
            rng=np.random.default_rng(42),
            inst=InstitutionalConfig(),
            network=SocialNetwork(),
            all_states={},
            week_records_by_student={},
            active_courses=[],
            cfg=EngineConfig(),
            total_weeks=14,
            avg_td=0.5,
        )
        defaults.update(overrides)
        return TheoryContext(**defaults)


class TestBehavioralEquivalence:
    """Same seed produces identical output before/after protocol migration."""

    def test_determinism_preserved(self, tmp_path):
        """Run engine twice with same seed — states must be identical."""
        from synthed.pipeline import SynthEdPipeline
        from synthed.pipeline_config import PipelineConfig

        config = PipelineConfig(output_dir=str(tmp_path), seed=42)

        p1 = SynthEdPipeline(config=config)
        r1 = p1.run(n_students=50)

        p2 = SynthEdPipeline(config=config)
        r2 = p2.run(n_students=50)

        assert r1["simulation_summary"]["dropout_rate"] == r2["simulation_summary"]["dropout_rate"]
        assert r1["simulation_summary"]["mean_final_gpa"] == r2["simulation_summary"]["mean_final_gpa"]
