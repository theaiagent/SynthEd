"""Tests for Baulke institutional modulation via InstitutionalConfig.

Verifies that support_services_quality (SSQ) modulates dropout phase
thresholds through scale_by(), with backward compatibility at SSQ=0.5.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from synthed.simulation.institutional import InstitutionalConfig, scale_by
from synthed.simulation.theories.baulke import BaulkeDropoutPhase


# ── helpers ──────────────────────────────────────────────────────────────


def _make_state(
    engagement: float = 0.50,
    dropout_phase: int = 0,
    social_integration: float = 0.30,
    perceived_cost_benefit: float = 0.50,
    missed_assignments_streak: int = 0,
    perceived_mastery: float = 0.60,
    perceived_mastery_count: int = 3,
    exhaustion_level: float = 0.0,
    weekly_engagement_history: list[float] | None = None,
    env_shock_remaining: int = 0,
    env_shock_magnitude: float = 0.0,
):
    """Minimal SimulationState-like object for unit tests."""

    class _FakeExhaustion:
        def __init__(self, level: float) -> None:
            self.exhaustion_level = level

    class _FakeCoI:
        cognitive_presence: float = 0.50

    class _FakeState:
        pass

    s = _FakeState()
    s.current_engagement = engagement
    s.dropout_phase = dropout_phase
    s.social_integration = social_integration
    s.perceived_cost_benefit = perceived_cost_benefit
    s.missed_assignments_streak = missed_assignments_streak
    s.perceived_mastery = perceived_mastery
    s.perceived_mastery_count = perceived_mastery_count
    s.exhaustion = _FakeExhaustion(exhaustion_level)
    s.weekly_engagement_history = weekly_engagement_history or []
    s.env_shock_remaining = env_shock_remaining
    s.env_shock_magnitude = env_shock_magnitude
    s.coi_state = _FakeCoI()
    s.memory = []
    return s


def _make_persona(base_dropout_risk: float = 0.3, financial_stress: float = 0.3):
    class _FakePersona:
        pass

    p = _FakePersona()
    p.base_dropout_risk = base_dropout_risk
    p.financial_stress = financial_stress
    return p


def _make_env(total_weeks: int = 14):
    class _FakeEnv:
        pass

    e = _FakeEnv()
    e.total_weeks = total_weeks
    return e


def _noop_td(student, state):
    return 0.3


# ── Test Class 1: Neutral Scaling ────────────────────────────────────────


class TestNeutralScaling:
    """SSQ=0.5 must reproduce class constants exactly."""

    def test_scale_by_neutral(self):
        """scale_by(c, 0.5) == c exactly (IEEE 754)."""
        constants = [0.40, 0.45, 0.36, 0.32, 0.25, 0.10, 0.50, 0.45, 0.40, 0.35, 0.45, 0.20, 0.70]
        for c in constants:
            assert scale_by(c, 0.5) == c

    def test_inst_none_matches_default(self):
        """advance_phase(inst=None) == advance_phase(inst=default) for same state."""
        baulke = BaulkeDropoutPhase()
        default_inst = InstitutionalConfig()

        # Forward paths (low engagement drives advancement)
        for phase in range(5):
            state_none = _make_state(engagement=0.30, dropout_phase=phase,
                                     social_integration=0.10,
                                     missed_assignments_streak=2,
                                     weekly_engagement_history=[0.35, 0.32, 0.30])
            state_inst = _make_state(engagement=0.30, dropout_phase=phase,
                                     social_integration=0.10,
                                     missed_assignments_streak=2,
                                     weekly_engagement_history=[0.35, 0.32, 0.30])
            persona = _make_persona()
            env = _make_env()

            rng_a = np.random.default_rng(99)
            rng_b = np.random.default_rng(99)

            baulke.advance_phase(persona, state_none, 5, env, _noop_td, rng_a, inst=None)
            baulke.advance_phase(persona, state_inst, 5, env, _noop_td, rng_b, inst=default_inst)

            assert state_none.dropout_phase == state_inst.dropout_phase, (
                f"Forward phase {phase}: inst=None gave {state_none.dropout_phase}, "
                f"inst=default gave {state_inst.dropout_phase}"
            )

        # Recovery paths (high engagement drives recovery)
        for phase in [1, 2, 3, 4]:
            state_none = _make_state(engagement=0.60, dropout_phase=phase,
                                     perceived_cost_benefit=0.60,
                                     weekly_engagement_history=[0.55, 0.58, 0.60])
            state_inst = _make_state(engagement=0.60, dropout_phase=phase,
                                     perceived_cost_benefit=0.60,
                                     weekly_engagement_history=[0.55, 0.58, 0.60])
            persona = _make_persona()
            env = _make_env()

            rng_a = np.random.default_rng(99)
            rng_b = np.random.default_rng(99)

            baulke.advance_phase(persona, state_none, 5, env, _noop_td, rng_a, inst=None)
            baulke.advance_phase(persona, state_inst, 5, env, _noop_td, rng_b, inst=default_inst)

            assert state_none.dropout_phase == state_inst.dropout_phase, (
                f"Recovery phase {phase}: inst=None gave {state_none.dropout_phase}, "
                f"inst=default gave {state_inst.dropout_phase}"
            )


# ── Test Class 2: Directional Scaling ────────────────────────────────────


class TestDirectionalScaling:
    """Verify threshold direction at SSQ=0.2 and SSQ=0.8."""

    def test_forward_thresholds_high_ssq(self):
        """SSQ=0.8 → forward thresholds LOWER than defaults."""
        baulke = BaulkeDropoutPhase()
        ssq = 0.8
        forward_constants = [
            baulke._NONFIT_ENG_THRESHOLD,
            baulke._NONFIT_ENG_SOFT,
            baulke._PHASE_1_TO_2_ENG,
            baulke._PHASE_2_TO_3_ENG,
            baulke._PHASE_3_TO_4_ENG,
            baulke._TRIGGER_ENG_THRESHOLD,
            baulke._PHASE_1_SOCIAL_THRESHOLD,
        ]
        for c in forward_constants:
            scaled = scale_by(c, 1.0 - ssq)
            assert scaled < c, f"scale_by({c}, {1.0 - ssq}) = {scaled} should be < {c}"

    def test_forward_thresholds_low_ssq(self):
        """SSQ=0.2 → forward thresholds HIGHER than defaults."""
        baulke = BaulkeDropoutPhase()
        ssq = 0.2
        forward_constants = [
            baulke._NONFIT_ENG_THRESHOLD,
            baulke._NONFIT_ENG_SOFT,
            baulke._PHASE_1_TO_2_ENG,
            baulke._PHASE_2_TO_3_ENG,
            baulke._PHASE_3_TO_4_ENG,
            baulke._TRIGGER_ENG_THRESHOLD,
            baulke._PHASE_1_SOCIAL_THRESHOLD,
        ]
        for c in forward_constants:
            scaled = scale_by(c, 1.0 - ssq)
            assert scaled > c, f"scale_by({c}, {1.0 - ssq}) = {scaled} should be > {c}"

    def test_recovery_thresholds_high_ssq(self):
        """SSQ=0.8 → recovery thresholds LOWER (easier to recover)."""
        baulke = BaulkeDropoutPhase()
        ssq = 0.8
        recovery_constants = [
            baulke._RECOVERY_1_TO_0,
            baulke._RECOVERY_2_TO_1,
            baulke._RECOVERY_3_TO_2,
            baulke._RECOVERY_4_TO_3_ENG,
            baulke._RECOVERY_4_TO_3_CB,
        ]
        for c in recovery_constants:
            scaled = scale_by(c, 1.0 - ssq)
            assert scaled < c, f"recovery scale_by({c}, {1.0 - ssq}) = {scaled} should be < {c}"

    def test_exhaustion_threshold_high_ssq(self):
        """SSQ=0.8 → exhaustion threshold HIGHER (harder to be exhausted)."""
        baulke = BaulkeDropoutPhase()
        scaled = scale_by(baulke._EXHAUSTION_THRESHOLD, 0.8)
        assert scaled > baulke._EXHAUSTION_THRESHOLD

    def test_exhaustion_threshold_low_ssq(self):
        """SSQ=0.2 → exhaustion threshold LOWER (easier to be exhausted)."""
        baulke = BaulkeDropoutPhase()
        scaled = scale_by(baulke._EXHAUSTION_THRESHOLD, 0.2)
        assert scaled < baulke._EXHAUSTION_THRESHOLD

    def test_exact_values_at_boundaries(self):
        """Verify exact scale_by outputs at SSQ=0.0 and SSQ=1.0."""
        c = 0.40
        assert scale_by(c, 0.0) == pytest.approx(c * 0.7)
        assert scale_by(c, 1.0) == pytest.approx(c * 1.3)
        assert scale_by(c, 0.5) == pytest.approx(c * 1.0)


# ── Test Class 3: Integration Dropout Rate ───────────────────────────────


class TestIntegrationDropoutRate:
    """Integration test: SSQ affects actual dropout rates via full engine."""

    @pytest.fixture()
    def _run_simulation(self, tmp_path):
        """Run pipeline with given SSQ value, return dropout rate."""
        from synthed.pipeline import SynthEdPipeline

        def _run(ssq: float, n: int = 200, seed: int = 42) -> float:
            inst = dataclasses.replace(InstitutionalConfig(), support_services_quality=ssq)
            pipeline = SynthEdPipeline(
                institutional_config=inst,
                output_dir=str(tmp_path),
                seed=seed,
            )
            report = pipeline.run(n_students=n)
            return report["simulation_summary"]["dropout_rate"]

        return _run

    def test_high_ssq_lower_dropout(self, _run_simulation):
        """SSQ=0.8 should produce lower mean dropout than SSQ=0.5 (10 seeds, eps=0.010).

        Directional smoke test. Not a regression guard for true effect sizes
        below ~0.015 — eps=0.010 is a pending empirical calibration (issue #86).
        """
        seeds = list(range(41, 51))
        default_rate = sum(_run_simulation(0.5, seed=s) for s in seeds) / len(seeds)
        high_ssq_rate = sum(_run_simulation(0.8, seed=s) for s in seeds) / len(seeds)
        assert high_ssq_rate <= default_rate - 0.010, (
            f"SSQ=0.8 mean dropout {high_ssq_rate:.3f} should be < default {default_rate:.3f}"
        )

    def test_low_ssq_higher_dropout(self, _run_simulation):
        """SSQ=0.2 should produce higher mean dropout than SSQ=0.5 (10 seeds, eps=0.010).

        Directional smoke test. Not a regression guard for true effect sizes
        below ~0.015 — eps=0.010 is a pending empirical calibration (issue #86).
        """
        seeds = list(range(41, 51))
        default_rate = sum(_run_simulation(0.5, seed=s) for s in seeds) / len(seeds)
        low_ssq_rate = sum(_run_simulation(0.2, seed=s) for s in seeds) / len(seeds)
        assert low_ssq_rate >= default_rate + 0.010, (
            f"SSQ=0.2 mean dropout {low_ssq_rate:.3f} should be > default {default_rate:.3f}"
        )

    def test_dropout_rate_sanity_bounds(self, _run_simulation):
        """All SSQ values produce dropout in [0.01, 0.70]."""
        for ssq in [0.1, 0.3, 0.5, 0.7, 0.9]:
            rate = _run_simulation(ssq)
            assert 0.01 <= rate <= 0.70, f"SSQ={ssq} dropout {rate:.3f} outside [0.01, 0.70]"
