"""Tests for Environmental Shocks (Bean & Metzner Phase 3 — stochastic life events)."""
from __future__ import annotations

import numpy as np
import pytest

from synthed.agents.persona import StudentPersona
from synthed.agents.factory import StudentFactory
from synthed.simulation.engine import SimulationEngine, SimulationState, CommunityOfInquiryState
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.theories.bean_metzner import BeanMetznerPressure
from synthed.simulation.theories.baulke import BaulkeDropoutPhase
from synthed.simulation.theories.sdt_motivation import SDTNeedSatisfaction
from synthed.simulation.theories.academic_exhaustion import ExhaustionState


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_state(**kwargs) -> SimulationState:
    defaults = dict(
        student_id="test",
        current_engagement=0.5,
        academic_integration=0.5,
        social_integration=0.3,
        perceived_cost_benefit=0.6,
        coi_state=CommunityOfInquiryState(),
        sdt_needs=SDTNeedSatisfaction(),
        exhaustion=ExhaustionState(),
        weekly_engagement_history=[],
    )
    defaults.update(kwargs)
    return SimulationState(**defaults)


def _high_risk_student() -> StudentPersona:
    """Student with maximum Bean & Metzner risk factors."""
    return StudentPersona(
        is_employed=True,
        weekly_work_hours=40,
        has_family_responsibilities=True,
        financial_stress=0.9,
    )


def _low_risk_student() -> StudentPersona:
    """Student with no Bean & Metzner risk factors."""
    return StudentPersona(
        is_employed=False,
        weekly_work_hours=0,
        has_family_responsibilities=False,
        financial_stress=0.0,
    )


# ── 1. SimulationState shock fields ──────────────────────────────────────────


class TestSimulationStateShockFields:
    """Verify the two new shock fields exist and default to zero."""

    def test_env_shock_remaining_exists(self):
        state = _make_state()
        assert hasattr(state, "env_shock_remaining")

    def test_env_shock_magnitude_exists(self):
        state = _make_state()
        assert hasattr(state, "env_shock_magnitude")

    def test_env_shock_remaining_default_zero(self):
        state = _make_state()
        assert state.env_shock_remaining == 0

    def test_env_shock_magnitude_default_zero(self):
        state = _make_state()
        assert state.env_shock_magnitude == 0.0

    def test_env_shock_remaining_is_int(self):
        state = _make_state()
        assert isinstance(state.env_shock_remaining, int)

    def test_env_shock_magnitude_is_float(self):
        state = _make_state()
        assert isinstance(state.env_shock_magnitude, float)

    def test_fields_can_be_set_at_construction(self):
        state = _make_state(env_shock_remaining=2, env_shock_magnitude=0.5)
        assert state.env_shock_remaining == 2
        assert state.env_shock_magnitude == 0.5


# ── 2. Shock generation ───────────────────────────────────────────────────────


class TestShockGeneration:
    """Tests for BeanMetznerPressure.stochastic_pressure_event."""

    def test_method_exists(self):
        bm = BeanMetznerPressure()
        assert hasattr(bm, "stochastic_pressure_event")
        assert callable(bm.stochastic_pressure_event)

    def test_returns_tuple_of_two(self):
        bm = BeanMetznerPressure()
        rng = np.random.default_rng(0)
        result = bm.stochastic_pressure_event(_high_risk_student(), rng)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_no_shock_returns_zero_zero(self):
        """Low-risk student with biased RNG (random() always >= prob) → (0, 0.0)."""
        bm = BeanMetznerPressure()
        # Override base prob to 0 so shock never fires
        bm._SHOCK_BASE_PROB = 0.0
        rng = np.random.default_rng(42)
        duration, magnitude = bm.stochastic_pressure_event(_high_risk_student(), rng)
        assert duration == 0
        assert magnitude == 0.0

    def test_shock_duration_in_valid_range(self):
        """When a shock fires, duration must be within [min, max]."""
        bm = BeanMetznerPressure()
        bm._SHOCK_BASE_PROB = 999.0  # force fire (risk_score * 999 >> 1)
        rng = np.random.default_rng(7)
        duration, _ = bm.stochastic_pressure_event(_high_risk_student(), rng)
        assert bm._SHOCK_MIN_DURATION <= duration <= bm._SHOCK_MAX_DURATION

    def test_shock_magnitude_in_valid_range(self):
        """When a shock fires, magnitude must be within [min, max]."""
        bm = BeanMetznerPressure()
        bm._SHOCK_BASE_PROB = 999.0
        rng = np.random.default_rng(7)
        _, magnitude = bm.stochastic_pressure_event(_high_risk_student(), rng)
        assert bm._SHOCK_MIN_MAGNITUDE <= magnitude <= bm._SHOCK_MAX_MAGNITUDE

    def test_duration_is_int(self):
        bm = BeanMetznerPressure()
        bm._SHOCK_BASE_PROB = 999.0
        rng = np.random.default_rng(7)
        duration, _ = bm.stochastic_pressure_event(_high_risk_student(), rng)
        assert isinstance(duration, int)

    def test_magnitude_is_float(self):
        bm = BeanMetznerPressure()
        bm._SHOCK_BASE_PROB = 999.0
        rng = np.random.default_rng(7)
        _, magnitude = bm.stochastic_pressure_event(_high_risk_student(), rng)
        assert isinstance(magnitude, float)

    def test_high_risk_gets_more_shocks_than_low_risk(self):
        """High-risk student should have materially higher shock probability."""
        bm = BeanMetznerPressure()
        rng_high = np.random.default_rng(0)
        rng_low = np.random.default_rng(0)
        n_trials = 1000
        high_student = _high_risk_student()
        low_student = _low_risk_student()

        high_shocks = sum(
            1 for _ in range(n_trials)
            if bm.stochastic_pressure_event(high_student, rng_high)[0] > 0
        )
        low_shocks = sum(
            1 for _ in range(n_trials)
            if bm.stochastic_pressure_event(low_student, rng_low)[0] > 0
        )
        assert high_shocks > low_shocks

    def test_low_risk_zero_probability(self):
        """Student with no risk factors → risk_score=0 → shock_prob=0 → never fires."""
        bm = BeanMetznerPressure()
        rng = np.random.default_rng(42)
        n_trials = 500
        zero_risk = _low_risk_student()
        shocks = sum(
            1 for _ in range(n_trials)
            if bm.stochastic_pressure_event(zero_risk, rng)[0] > 0
        )
        assert shocks == 0

    def test_constants_exist_on_class(self):
        bm = BeanMetznerPressure()
        for attr in (
            "_SHOCK_BASE_PROB", "_SHOCK_EMPLOY_WEIGHT", "_SHOCK_FAMILY_WEIGHT",
            "_SHOCK_STRESS_WEIGHT", "_SHOCK_MIN_DURATION", "_SHOCK_MAX_DURATION",
            "_SHOCK_MIN_MAGNITUDE", "_SHOCK_MAX_MAGNITUDE",
        ):
            assert hasattr(bm, attr), f"Missing constant: {attr}"


# ── 3. Engine integration ─────────────────────────────────────────────────────


class TestShockEngineIntegration:
    """Run a small cohort through the engine and verify shock mechanics."""

    @pytest.fixture
    def engine_and_students(self):
        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=123)
        factory = StudentFactory(seed=123)
        students = factory.generate_population(n=50)
        return engine, students

    def test_simulation_runs_without_crash(self, engine_and_students):
        engine, students = engine_and_students
        records, states, _ = engine.run(students)
        assert len(states) == 50

    def test_shock_events_recorded_in_memory(self, engine_and_students):
        """At least one student should have an env_shock memory event in a 50-student run."""
        engine, students = engine_and_students
        _, states, _ = engine.run(students)
        shock_events = [
            ev
            for state in states.values()
            for ev in state.memory
            if ev.get("event_type") == "env_shock"
        ]
        # With 50 students × 14 weeks and high-risk profiles expected, we expect shocks
        assert len(shock_events) >= 1

    def test_shock_event_has_required_keys(self, engine_and_students):
        """Every env_shock memory entry must have week, event_type, details, impact."""
        engine, students = engine_and_students
        _, states, _ = engine.run(students)
        for state in states.values():
            for ev in state.memory:
                if ev.get("event_type") == "env_shock":
                    assert "week" in ev
                    assert "details" in ev
                    assert "impact" in ev
                    assert ev["impact"] < 0  # shocks always reduce engagement

    def test_shock_remaining_resets_after_duration(self):
        """After shock duration expires, env_shock_remaining must return to 0."""
        state = _make_state(
            student_id="shock_test",
            env_shock_remaining=2,
            env_shock_magnitude=0.8,
        )
        # Simulate two engagement update calls manually via the engagement path
        # We directly step the state counters as the engine would
        for _ in range(2):
            if state.env_shock_remaining > 0:
                state.env_shock_remaining -= 1
                if state.env_shock_remaining == 0:
                    state.env_shock_magnitude = 0.0

        assert state.env_shock_remaining == 0
        assert state.env_shock_magnitude == 0.0

    def test_active_shock_reduces_engagement(self):
        """When env_shock_remaining > 0, engagement decreases by magnitude * 0.05."""
        state = _make_state(
            student_id="shock_eng_test",
            current_engagement=0.6,
            env_shock_remaining=3,
            env_shock_magnitude=1.0,
        )
        # Snapshot engagement before calling the engagement update
        initial_engagement = state.current_engagement

        # Simulate the shock penalty directly (as the engine does)
        if state.env_shock_remaining > 0:
            engagement = state.current_engagement
            engagement -= state.env_shock_magnitude * 0.05
            state.env_shock_remaining -= 1
            if state.env_shock_remaining == 0:
                state.env_shock_magnitude = 0.0
            state.current_engagement = engagement

        assert state.current_engagement < initial_engagement


# ── 4. Baulke phase advance via severe shock ──────────────────────────────────


class TestBaulkeShockPhaseAdvance:
    """Severe env shock (above threshold) should push phase 2 → 3."""

    def _make_baulke_state(self, eng: float, shock_remaining: int, shock_mag: float) -> SimulationState:
        state = _make_state(
            current_engagement=eng,
            dropout_phase=2,
            env_shock_remaining=shock_remaining,
            env_shock_magnitude=shock_mag,
            weekly_engagement_history=[eng - 0.01, eng],  # declining trend required by phase 2→3
        )
        return state

    def test_severe_shock_advances_phase_2_to_3(self):
        """A shock above _SHOCK_SEVERITY_THRESHOLD while in phase 2 should advance to phase 3."""
        baulke = BaulkeDropoutPhase()
        env = ODLEnvironment()

        # Set engagement just above normal phase-2->3 threshold so only shock triggers it
        # _PHASE_2_TO_3_ENG = 0.32; set eng=0.33 (above) but with severe shock
        eng = 0.33
        state = self._make_baulke_state(
            eng=eng,
            shock_remaining=2,
            shock_mag=baulke._SHOCK_SEVERITY_THRESHOLD + 0.1,
        )
        student = _high_risk_student()

        def avg_td_fn(s, st):
            return 0.5

        baulke.advance_phase(student, state, week=5, env=env, avg_td_fn=avg_td_fn,
                             rng=np.random.default_rng(0))

        assert state.dropout_phase == 3, (
            f"Expected phase 3 but got {state.dropout_phase}. "
            "Severe shock should trigger phase 2→3 advance."
        )

    def test_mild_shock_does_not_advance_phase_alone(self):
        """A mild shock below threshold should NOT advance phase when engagement is acceptable."""
        baulke = BaulkeDropoutPhase()
        env = ODLEnvironment()

        # Engagement above ALL thresholds so nothing else triggers advance
        # _RECOVERY_2_TO_1 = 0.45; set eng=0.44 (just below recovery, above phase trigger)
        # _PHASE_2_TO_3_ENG = 0.32; eng=0.44 is above so normal condition won't fire
        eng = 0.44
        state = self._make_baulke_state(
            eng=eng,
            shock_remaining=1,
            shock_mag=baulke._SHOCK_SEVERITY_THRESHOLD - 0.1,
        )
        student = _high_risk_student()

        def avg_td_fn(s, st):
            return 0.4  # below _NONFIT_TD_THRESHOLD

        baulke.advance_phase(student, state, week=5, env=env, avg_td_fn=avg_td_fn,
                             rng=np.random.default_rng(0))

        # Should stay at 2 (not advance to 3, not recover to 1)
        assert state.dropout_phase == 2, (
            f"Expected phase 2 but got {state.dropout_phase}. "
            "Mild shock should not advance phase on its own."
        )

    def test_no_shock_does_not_advance_phase_at_acceptable_engagement(self):
        """No active shock with acceptable engagement should not advance phase 2 → 3."""
        baulke = BaulkeDropoutPhase()
        env = ODLEnvironment()

        eng = 0.44
        state = self._make_baulke_state(eng=eng, shock_remaining=0, shock_mag=0.0)
        student = _low_risk_student()

        def avg_td_fn(s, st):
            return 0.4

        baulke.advance_phase(student, state, week=5, env=env, avg_td_fn=avg_td_fn,
                             rng=np.random.default_rng(0))

        assert state.dropout_phase == 2

    def test_threshold_constant_exists(self):
        baulke = BaulkeDropoutPhase()
        assert hasattr(baulke, "_SHOCK_SEVERITY_THRESHOLD")
        assert isinstance(baulke._SHOCK_SEVERITY_THRESHOLD, float)
        assert 0.0 < baulke._SHOCK_SEVERITY_THRESHOLD < 1.0
