"""Tests for individual theory modules."""

import numpy as np

from synthed.agents.persona import StudentPersona, BigFiveTraits
from synthed.simulation.engine import InteractionRecord, SimulationState, CommunityOfInquiryState
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.theories import (
    TintoIntegration,
    BeanMetznerPressure,
    MooreTransactionalDistance,
    RovaiPersistence,
    GarrisonCoI,
    BaulkeDropoutPhase,
    KemberCostBenefit,
    SDTMotivationDynamics,
    SDTNeedSatisfaction,
    GonzalezExhaustion,
    ExhaustionState,
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


class TestTinto:
    def test_forum_posts_increase_social_integration(self):
        tinto = TintoIntegration()
        student = StudentPersona()
        state = _make_state(social_integration=0.3)
        records = [
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="forum_post"),
        ]
        tinto.update_integration(student, state, 1, {}, records)
        assert state.social_integration > 0.3


class TestBeanMetzner:
    def test_employed_has_more_pressure(self):
        bm = BeanMetznerPressure()
        employed = StudentPersona(is_employed=True, weekly_work_hours=40,
                                  has_family_responsibilities=True,
                                  financial_stress=0.7)
        unemployed = StudentPersona(is_employed=False, weekly_work_hours=0,
                                    has_family_responsibilities=False,
                                    financial_stress=0.2)
        assert bm.calculate_environmental_pressure(employed) < bm.calculate_environmental_pressure(unemployed)


class TestMoore:
    def test_high_structure_high_td(self):
        moore = MooreTransactionalDistance()
        student = StudentPersona(learner_autonomy=0.3)
        env = ODLEnvironment()
        course = env.courses[0]
        # Higher structure should produce higher TD
        from synthed.simulation.environment import Course
        high_structure = Course(id="T1", name="T1", structure_level=0.9,
                                dialogue_frequency=0.1, instructor_responsiveness=0.2)
        low_structure = Course(id="T2", name="T2", structure_level=0.1,
                               dialogue_frequency=0.8, instructor_responsiveness=0.8)
        td_high = moore.calculate(student, high_structure)
        td_low = moore.calculate(student, low_structure)
        assert td_high > td_low


class TestRovai:
    def test_high_regulation_higher_buffer(self):
        rovai = RovaiPersistence()
        high_reg = StudentPersona(self_regulation=0.9)
        low_reg = StudentPersona(self_regulation=0.2)
        assert rovai.regulation_buffer(high_reg) > rovai.regulation_buffer(low_reg)


class TestGarrison:
    def test_forum_posts_increase_social_presence(self):
        garrison = GarrisonCoI()
        student = StudentPersona()
        state = _make_state()
        initial_sp = state.coi_state.social_presence
        records = [
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="forum_post",
                              metadata={"post_length": 50}),
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="forum_post",
                              metadata={"post_length": 120}),
        ]
        env = ODLEnvironment()
        garrison.update_presences(student, state, 1, records, env.courses)
        assert state.coi_state.social_presence > initial_sp


class TestBaulke:
    def test_low_engagement_advances_phase(self):
        baulke = BaulkeDropoutPhase()
        student = StudentPersona()
        state = _make_state(current_engagement=0.20, dropout_phase=0)
        env = ODLEnvironment()
        rng = np.random.default_rng(42)
        baulke.advance_phase(
            student, state, 5, env,
            lambda s, st: 0.5,
            rng,
        )
        assert state.dropout_phase >= 1


class TestKember:
    def test_missed_assignments_lower_cost_benefit(self):
        kember = KemberCostBenefit()
        student = StudentPersona()
        state = _make_state(
            missed_assignments_streak=3,
            perceived_cost_benefit=0.6,
        )
        records = []  # no academic submissions
        kember.recalculate(student, state, {}, records, avg_td=0.5)
        assert state.perceived_cost_benefit < 0.6


class TestSDT:
    def test_high_needs_produce_intrinsic(self):
        sdt = SDTMotivationDynamics()
        state = _make_state()
        state.sdt_needs = SDTNeedSatisfaction(
            autonomy=0.8, competence=0.8, relatedness=0.7
        )
        result = sdt.evaluate_motivation_shift(state)
        assert result == "intrinsic"


class TestGonzalez:
    def test_assignments_increase_exhaustion(self):
        gonzalez = GonzalezExhaustion()
        student = StudentPersona(
            is_employed=True, weekly_work_hours=40,
            has_family_responsibilities=True,
            financial_stress=0.7, self_regulation=0.3,
            personality=BigFiveTraits(conscientiousness=0.3),
        )
        state = _make_state()
        state.exhaustion = ExhaustionState(exhaustion_level=0.0)
        context = {"active_assignments": ["CS101", "MATH201", "EDU301"]}
        gonzalez.update_exhaustion(student, state, 1, context, [])
        assert state.exhaustion.exhaustion_level > 0.0
