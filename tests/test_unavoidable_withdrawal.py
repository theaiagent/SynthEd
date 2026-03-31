"""Tests for the UnavoidableWithdrawal theory module."""

import numpy as np
import pytest

from synthed.agents.persona import StudentPersona, PersonaConfig
from synthed.simulation.engine import SimulationState, CommunityOfInquiryState
from synthed.simulation.theories import (
    SDTNeedSatisfaction,
    ExhaustionState,
    UnavoidableWithdrawal,
)


def _make_state(**kwargs):
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


class TestZeroProbability:
    def test_zero_probability_never_triggers(self):
        uw = UnavoidableWithdrawal(per_semester_probability=0.0, total_weeks=14)
        student = StudentPersona()
        rng = np.random.default_rng(42)
        for week in range(1, 15):
            state = _make_state()
            result = uw.check_withdrawal(student, state, week, rng)
            assert result is False
            assert state.has_dropped_out is False
            assert state.withdrawal_reason is None


class TestCertainProbability:
    def test_certain_probability_always_triggers(self):
        uw = UnavoidableWithdrawal(per_semester_probability=1.0, total_weeks=14)
        student = StudentPersona()
        rng = np.random.default_rng(42)
        state = _make_state()
        result = uw.check_withdrawal(student, state, 1, rng)
        assert result is True
        assert state.has_dropped_out is True
        assert state.withdrawal_reason is not None


class TestWithdrawalFields:
    def test_withdrawal_sets_all_fields(self):
        uw = UnavoidableWithdrawal(per_semester_probability=1.0, total_weeks=14)
        student = StudentPersona()
        rng = np.random.default_rng(42)
        state = _make_state()
        uw.check_withdrawal(student, state, 5, rng)

        assert state.has_dropped_out is True
        assert state.dropout_week == 5
        assert state.withdrawal_reason in UnavoidableWithdrawal._EVENT_WEIGHTS
        assert len(state.memory) == 1
        assert state.memory[0]["event_type"] == "unavoidable_withdrawal"
        assert state.memory[0]["week"] == 5
        assert state.memory[0]["impact"] == -1.0


class TestWeeklyProbabilityConversion:
    def test_weekly_probability_conversion(self):
        p_semester = 0.10
        total_weeks = 14
        uw = UnavoidableWithdrawal(
            per_semester_probability=p_semester,
            total_weeks=total_weeks,
        )
        # Verify: (1 - p_week)^14 == (1 - p_semester)
        cumulative = 1.0 - (1.0 - uw.weekly_probability) ** total_weeks
        assert abs(cumulative - p_semester) < 1e-10


class TestStatisticalRate:
    def test_statistical_rate_over_many_students(self):
        p_semester = 0.10
        total_weeks = 14
        uw = UnavoidableWithdrawal(
            per_semester_probability=p_semester,
            total_weeks=total_weeks,
        )
        rng = np.random.default_rng(123)
        n_students = 5000
        withdrawals = 0
        for _ in range(n_students):
            state = _make_state()
            student = StudentPersona()
            for week in range(1, total_weeks + 1):
                if uw.check_withdrawal(student, state, week, rng):
                    withdrawals += 1
                    break
        rate = withdrawals / n_students
        # Expect ~10%, allow 7%-13%
        assert 0.07 <= rate <= 0.13, f"Rate {rate:.3f} outside 7%-13%"


class TestInvalidProbability:
    def test_invalid_probability_raises(self):
        with pytest.raises(ValueError, match="per_semester_probability"):
            UnavoidableWithdrawal(per_semester_probability=-0.1, total_weeks=14)
        with pytest.raises(ValueError, match="per_semester_probability"):
            UnavoidableWithdrawal(per_semester_probability=1.5, total_weeks=14)
        with pytest.raises(ValueError, match="total_weeks"):
            UnavoidableWithdrawal(per_semester_probability=0.1, total_weeks=0)


class TestPersonaConfigValidation:
    def test_persona_config_validation(self):
        # Valid value should work
        config = PersonaConfig(unavoidable_withdrawal_rate=0.01)
        assert config.unavoidable_withdrawal_rate == 0.01

        # Too high should fail (max 0.05)
        with pytest.raises(ValueError, match="unavoidable_withdrawal_rate"):
            PersonaConfig(unavoidable_withdrawal_rate=0.10)

        # Negative should fail
        with pytest.raises(ValueError, match="unavoidable_withdrawal_rate"):
            PersonaConfig(unavoidable_withdrawal_rate=-0.01)


class TestEventWeights:
    def test_event_weights_sum_to_one(self):
        total = sum(UnavoidableWithdrawal._EVENT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-10


class TestWithdrawalReasonDefault:
    def test_withdrawal_reason_is_none_by_default(self):
        state = _make_state()
        assert state.withdrawal_reason is None
