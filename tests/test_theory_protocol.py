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

    def test_canonical_order(self):
        """Exact canonical order — changing this breaks determinism."""
        expected = [
            "TintoIntegration",
            "GarrisonCoI",
            "SDTMotivationDynamics",
            "EpsteinAxtellPeerInfluence",
            "BaulkeDropoutPhase",
        ]
        actual = [t.__name__ for t in discover_theories()]
        assert actual == expected, f"Theory order changed: {actual} != {expected}"

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


class TestEngagementDelta:
    """Each theory's contribute_engagement_delta returns expected values."""

    @staticmethod
    def _make_engagement_ctx(**overrides):
        """Build a TheoryContext with real student + state for engagement tests."""
        from synthed.agents.factory import StudentFactory
        from synthed.simulation.engine_config import EngineConfig
        from synthed.simulation.environment import ODLEnvironment
        from synthed.simulation.institutional import InstitutionalConfig
        from synthed.simulation.social_network import SocialNetwork
        from synthed.simulation.state import SimulationState

        env = ODLEnvironment()
        factory = StudentFactory(seed=42)
        student = factory.generate_population(1)[0]
        state = SimulationState(student_id=student.id, courses_active=[c.id for c in env.courses])

        defaults = dict(
            student=student,
            state=state,
            records=[],
            week=3,
            context={},
            env=env,
            rng=np.random.default_rng(42),
            inst=InstitutionalConfig(),
            network=SocialNetwork(),
            all_states={},
            week_records_by_student={},
            active_courses=list(env.courses),
            cfg=EngineConfig(),
            total_weeks=14,
            avg_td=0.5,
        )
        defaults.update(overrides)
        return TheoryContext(**defaults)

    def test_tinto_engagement_delta(self):
        from synthed.simulation.theories import TintoIntegration
        ctx = self._make_engagement_ctx()
        t = TintoIntegration()
        delta = t.contribute_engagement_delta(ctx)
        assert isinstance(delta, float)

    def test_bean_metzner_engagement_delta(self):
        from synthed.simulation.theories import BeanMetznerPressure
        ctx = self._make_engagement_ctx()
        t = BeanMetznerPressure()
        delta = t.contribute_engagement_delta(ctx)
        assert isinstance(delta, float)
        assert delta <= 0.0  # environmental pressure is always non-positive

    def test_bean_metzner_shock_side_effects(self):
        """BeanMetzner contribute_engagement_delta manages shock state."""
        from synthed.simulation.theories import BeanMetznerPressure
        ctx = self._make_engagement_ctx()
        ctx.state.env_shock_remaining = 2
        ctx.state.env_shock_magnitude = 0.5
        t = BeanMetznerPressure()
        delta = t.contribute_engagement_delta(ctx)
        assert ctx.state.env_shock_remaining == 1
        assert isinstance(delta, float)

    def test_positive_events_engagement_delta(self):
        from synthed.simulation.theories import PositiveEventHandler
        ctx = self._make_engagement_ctx(context={"positive_event": "financial_aid_disbursement"})
        t = PositiveEventHandler()
        delta = t.contribute_engagement_delta(ctx)
        assert delta > 0.0

    def test_positive_events_no_event_returns_zero(self):
        from synthed.simulation.theories import PositiveEventHandler
        ctx = self._make_engagement_ctx()
        t = PositiveEventHandler()
        assert t.contribute_engagement_delta(ctx) == 0.0

    def test_rovai_engagement_delta(self):
        from synthed.simulation.theories import RovaiPersistence
        ctx = self._make_engagement_ctx()
        t = RovaiPersistence()
        delta = t.contribute_engagement_delta(ctx)
        assert isinstance(delta, float)

    def test_sdt_engagement_delta_intrinsic(self):
        from synthed.simulation.theories import SDTMotivationDynamics
        ctx = self._make_engagement_ctx()
        ctx.state.current_motivation_type = "intrinsic"
        t = SDTMotivationDynamics()
        delta = t.contribute_engagement_delta(ctx)
        assert delta > 0.0

    def test_sdt_engagement_delta_amotivation(self):
        from synthed.simulation.theories import SDTMotivationDynamics
        ctx = self._make_engagement_ctx()
        ctx.state.current_motivation_type = "amotivation"
        t = SDTMotivationDynamics()
        delta = t.contribute_engagement_delta(ctx)
        assert delta < 0.0

    def test_moore_engagement_delta(self):
        from synthed.simulation.theories import MooreTransactionalDistance
        ctx = self._make_engagement_ctx(avg_td=0.7)
        t = MooreTransactionalDistance()
        delta = t.contribute_engagement_delta(ctx)
        assert delta < 0.0  # high TD -> negative engagement effect

    def test_garrison_engagement_delta(self):
        from synthed.simulation.theories import GarrisonCoI
        ctx = self._make_engagement_ctx()
        t = GarrisonCoI()
        delta = t.contribute_engagement_delta(ctx)
        assert isinstance(delta, float)

    def test_gonzalez_engagement_delta(self):
        from synthed.simulation.theories import GonzalezExhaustion
        ctx = self._make_engagement_ctx()
        ctx.state.exhaustion.exhaustion_level = 0.5
        t = GonzalezExhaustion()
        delta = t.contribute_engagement_delta(ctx)
        assert delta < 0.0  # exhaustion drags engagement down

    def test_kember_engagement_delta_with_exam(self):
        from synthed.simulation.theories import KemberCostBenefit
        ctx = self._make_engagement_ctx(context={"is_exam_week": True})
        t = KemberCostBenefit()
        delta = t.contribute_engagement_delta(ctx)
        assert isinstance(delta, float)

    def test_kember_returns_zero_when_no_trigger(self):
        from synthed.simulation.theories import KemberCostBenefit
        ctx = self._make_engagement_ctx(context={})
        ctx.state.missed_assignments_streak = 0
        t = KemberCostBenefit()
        assert t.contribute_engagement_delta(ctx) == 0.0

    def test_engagement_theories_sorted_by_order(self):
        """Engine._engagement_theories is sorted by _ENGAGEMENT_ORDER."""
        from synthed.pipeline import SynthEdPipeline
        from synthed.pipeline_config import PipelineConfig
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            config = PipelineConfig(output_dir=td, seed=42)
            pipeline = SynthEdPipeline(config=config)
            engine = pipeline.engine
            orders = [t._ENGAGEMENT_ORDER for t in engine._engagement_theories]
            assert orders == sorted(orders)
            assert len(orders) == 9  # 9 theories contribute engagement

    def test_engagement_order_canonical(self):
        """Verify exact _ENGAGEMENT_ORDER values match plan."""
        from synthed.simulation.theories import (
            TintoIntegration, BeanMetznerPressure, PositiveEventHandler,
            RovaiPersistence, SDTMotivationDynamics, MooreTransactionalDistance,
            GarrisonCoI, GonzalezExhaustion, KemberCostBenefit,
        )
        expected = [
            (TintoIntegration, 100),
            (BeanMetznerPressure, 200),
            (PositiveEventHandler, 300),
            (RovaiPersistence, 400),
            (SDTMotivationDynamics, 500),
            (MooreTransactionalDistance, 600),
            (GarrisonCoI, 700),
            (GonzalezExhaustion, 800),
            (KemberCostBenefit, 900),
        ]
        for cls, order in expected:
            assert cls._ENGAGEMENT_ORDER == order, f"{cls.__name__}._ENGAGEMENT_ORDER != {order}"


class TestBehavioralEquivalence:
    """Same seed produces identical output before/after protocol migration."""

    def test_determinism_preserved(self, tmp_path):
        """Run engine twice with same seed in separate dirs — states must be identical."""
        from synthed.pipeline import SynthEdPipeline
        from synthed.pipeline_config import PipelineConfig

        c1 = PipelineConfig(output_dir=str(tmp_path / "run1"), seed=42)
        c2 = PipelineConfig(output_dir=str(tmp_path / "run2"), seed=42)

        r1 = SynthEdPipeline(config=c1).run(n_students=50)
        r2 = SynthEdPipeline(config=c2).run(n_students=50)

        s1 = r1["simulation_summary"]
        s2 = r2["simulation_summary"]
        assert s1["dropout_rate"] == s2["dropout_rate"]
        assert s1["mean_final_gpa"] == s2["mean_final_gpa"]
        assert s1["total_students"] == s2["total_students"]
        assert s1["dropout_count"] == s2["dropout_count"]
