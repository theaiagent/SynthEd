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


class TestKemberGPAFeedback:
    def test_high_gpa_increases_cost_benefit(self):
        kember = KemberCostBenefit()
        student = StudentPersona()
        state = _make_state(
            perceived_cost_benefit=0.50,
            missed_assignments_streak=0,
            cumulative_gpa=3.6,
            gpa_count=5,
        )
        records = [
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.7),
        ]
        kember.recalculate(student, state, {}, records, avg_td=0.5)
        assert state.perceived_cost_benefit > 0.50

    def test_low_gpa_decreases_cost_benefit(self):
        kember = KemberCostBenefit()
        student = StudentPersona()
        state = _make_state(
            perceived_cost_benefit=0.50,
            missed_assignments_streak=0,
            cumulative_gpa=1.2,
            gpa_count=5,
            perceived_mastery_sum=0.0,
            perceived_mastery_count=5,
        )
        records = [
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        kember.recalculate(student, state, {}, records, avg_td=0.5)
        assert state.perceived_cost_benefit < 0.50

    def test_no_gpa_items_no_gpa_effect(self):
        kember = KemberCostBenefit()
        student = StudentPersona()
        state = _make_state(
            perceived_cost_benefit=0.50,
            missed_assignments_streak=3,
            gpa_count=0,
            cumulative_gpa=0.0,
        )
        # With no GPA items, only missed streak should affect cost-benefit
        kember.recalculate(student, state, {}, [], avg_td=0.5)
        # Should still decrease (missed streak), but NOT from GPA
        assert state.perceived_cost_benefit < 0.50


class TestBaulkeGPAFeedback:
    def test_low_gpa_triggers_nonfit(self):
        baulke = BaulkeDropoutPhase()
        student = StudentPersona()
        state = _make_state(
            current_engagement=0.43,
            dropout_phase=0,
            cumulative_gpa=1.4,
            gpa_count=3,
            perceived_mastery_sum=0.0,
            perceived_mastery_count=3,
        )
        env = ODLEnvironment()
        rng = np.random.default_rng(42)
        baulke.advance_phase(student, state, 5, env, lambda s, st: 0.5, rng)
        assert state.dropout_phase == 1

    def test_low_gpa_without_low_engagement_no_nonfit(self):
        baulke = BaulkeDropoutPhase()
        student = StudentPersona()
        state = _make_state(
            current_engagement=0.55,
            dropout_phase=0,
            cumulative_gpa=1.4,
            gpa_count=3,
        )
        env = ODLEnvironment()
        rng = np.random.default_rng(42)
        baulke.advance_phase(student, state, 5, env, lambda s, st: 0.5, rng)
        assert state.dropout_phase == 0

    def test_gpa_gate_minimum_items(self):
        baulke = BaulkeDropoutPhase()
        student = StudentPersona()
        state = _make_state(
            current_engagement=0.43,
            dropout_phase=0,
            cumulative_gpa=1.0,
            gpa_count=1,  # below minimum of 2
        )
        env = ODLEnvironment()
        rng = np.random.default_rng(42)
        baulke.advance_phase(student, state, 5, env, lambda s, st: 0.5, rng)
        # GPA alone shouldn't trigger non-fit with only 1 graded item
        # (may still trigger from low engagement alone if < 0.40)
        # engagement is 0.43, which is above _NONFIT_ENG_THRESHOLD (0.40)
        # but below _NONFIT_ENG_SOFT (0.45) — needs another condition
        # With gpa_count=1, GPA condition doesn't activate
        assert state.dropout_phase == 0


class TestSDTGPAFeedback:
    def test_high_gpa_boosts_competence(self):
        sdt = SDTMotivationDynamics()
        student = StudentPersona(self_efficacy=0.5)
        state = _make_state(
            cumulative_gpa=3.6,
            gpa_count=5,
            perceived_mastery_sum=4.091,
            perceived_mastery_count=5,
        )
        state.sdt_needs = SDTNeedSatisfaction(competence=0.5)
        records = [
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        sdt.update_needs(student, state, 1, records)
        # With high GPA (3.6) and neutral quality (0.5), competence should rise
        assert state.sdt_needs.competence > 0.5

    def test_low_gpa_erodes_competence(self):
        sdt = SDTMotivationDynamics()
        student = StudentPersona(self_efficacy=0.5)
        state = _make_state(
            cumulative_gpa=1.2,
            gpa_count=5,
            perceived_mastery_sum=0.0,
            perceived_mastery_count=5,
        )
        state.sdt_needs = SDTNeedSatisfaction(competence=0.5)
        records = [
            InteractionRecord(student_id="test", week=1, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        sdt.update_needs(student, state, 1, records)
        # With low GPA (1.2) and neutral quality (0.5), competence should drop
        assert state.sdt_needs.competence < 0.5


class TestBeanMetznerCoping:
    """Tests for coping factor in Bean & Metzner module."""

    def test_coping_starts_at_zero(self):
        """SimulationState initializes with coping_factor=0.0."""
        state = _make_state()
        assert state.coping_factor == 0.0

    def test_coping_grows_each_week(self):
        """update_coping increases coping_factor monotonically."""
        bm = BeanMetznerPressure()
        student = StudentPersona(self_regulation=0.7,
                                 personality=BigFiveTraits(conscientiousness=0.7))
        state = _make_state()
        prev = 0.0
        for _ in range(10):
            bm.update_coping(student, state)
            assert state.coping_factor > prev
            prev = state.coping_factor

    def test_coping_never_exceeds_max(self):
        """Coping factor stays within [0.0, 0.5] even after many weeks."""
        bm = BeanMetznerPressure()
        student = StudentPersona(self_regulation=0.95,
                                 personality=BigFiveTraits(conscientiousness=0.95))
        state = _make_state()
        for _ in range(200):
            bm.update_coping(student, state)
        assert 0.0 <= state.coping_factor <= 0.5

    def test_high_regulation_faster_growth(self):
        """High self-regulation students develop coping faster."""
        bm = BeanMetznerPressure()
        high_reg = StudentPersona(self_regulation=0.9,
                                  personality=BigFiveTraits(conscientiousness=0.9))
        low_reg = StudentPersona(self_regulation=0.2,
                                 personality=BigFiveTraits(conscientiousness=0.2))
        state_high = _make_state()
        state_low = _make_state()
        for _ in range(10):
            bm.update_coping(high_reg, state_high)
            bm.update_coping(low_reg, state_low)
        assert state_high.coping_factor > state_low.coping_factor

    def test_coping_attenuates_pressure(self):
        """Coping reduces the magnitude of environmental pressure."""
        bm = BeanMetznerPressure()
        student = StudentPersona(is_employed=True, weekly_work_hours=40,
                                 has_family_responsibilities=True,
                                 financial_stress=0.7)
        pressure_no_coping = bm.calculate_environmental_pressure(student, coping_factor=0.0)
        pressure_with_coping = bm.calculate_environmental_pressure(student, coping_factor=0.3)
        # Both should be negative (pressure), but with coping the magnitude is smaller
        assert pressure_no_coping < 0
        assert pressure_with_coping < 0
        assert abs(pressure_with_coping) < abs(pressure_no_coping)

    def test_coping_zero_preserves_original(self):
        """coping_factor=0.0 produces identical result to the old behavior."""
        bm = BeanMetznerPressure()
        student = StudentPersona(is_employed=True, weekly_work_hours=40,
                                 has_family_responsibilities=True,
                                 financial_stress=0.7)
        p1 = bm.calculate_environmental_pressure(student)
        p2 = bm.calculate_environmental_pressure(student, coping_factor=0.0)
        assert p1 == p2

    def test_diminishing_returns(self):
        """Growth from 0.0 is faster than growth from near the cap."""
        bm = BeanMetznerPressure()
        student = StudentPersona(self_regulation=0.7,
                                 personality=BigFiveTraits(conscientiousness=0.7))
        # Growth from 0.0
        state_low = _make_state()
        bm.update_coping(student, state_low)
        growth_from_zero = state_low.coping_factor

        # Growth from 0.4 (near cap)
        state_high = _make_state(coping_factor=0.4)
        initial = state_high.coping_factor
        bm.update_coping(student, state_high)
        growth_from_high = state_high.coping_factor - initial

        assert growth_from_zero > growth_from_high


class TestRovaiDisability:
    def test_disability_low_support_reduces_floor(self):
        """Disability + low institutional support reduces engagement floor."""
        rovai = RovaiPersistence()
        student_dis = StudentPersona(disability_severity=0.6,
                                     institutional_support_access=0.2,
                                     self_regulation=0.5, goal_commitment=0.5,
                                     self_efficacy=0.5, learner_autonomy=0.5)
        student_no = StudentPersona(disability_severity=0.0,
                                    institutional_support_access=0.2,
                                    self_regulation=0.5, goal_commitment=0.5,
                                    self_efficacy=0.5, learner_autonomy=0.5)
        floor_dis = rovai.engagement_floor(student_dis)
        floor_no = rovai.engagement_floor(student_no)
        assert floor_dis < floor_no

    def test_disability_high_support_no_penalty(self):
        """Disability with high support has no floor penalty."""
        rovai = RovaiPersistence()
        student_dis = StudentPersona(disability_severity=0.5,
                                     institutional_support_access=0.7,
                                     self_regulation=0.5, goal_commitment=0.5,
                                     self_efficacy=0.5, learner_autonomy=0.5)
        student_no = StudentPersona(disability_severity=0.0,
                                    institutional_support_access=0.7,
                                    self_regulation=0.5, goal_commitment=0.5,
                                    self_efficacy=0.5, learner_autonomy=0.5)
        assert rovai.engagement_floor(student_dis) == rovai.engagement_floor(student_no)

    def test_severe_disability_stronger_penalty(self):
        """Higher severity means stronger floor reduction."""
        rovai = RovaiPersistence()
        mild = StudentPersona(disability_severity=0.1, institutional_support_access=0.2,
                              self_regulation=0.5, goal_commitment=0.5,
                              self_efficacy=0.5, learner_autonomy=0.5)
        severe = StudentPersona(disability_severity=0.8, institutional_support_access=0.2,
                                self_regulation=0.5, goal_commitment=0.5,
                                self_efficacy=0.5, learner_autonomy=0.5)
        assert rovai.engagement_floor(severe) < rovai.engagement_floor(mild)


class TestBeanMetznerDisability:
    def test_disability_adds_pressure(self):
        """Disabled student gets more negative pressure."""
        bm = BeanMetznerPressure()
        student_dis = StudentPersona(disability_severity=0.5,
                                     is_employed=True, weekly_work_hours=40,
                                     financial_stress=0.7)
        student_no = StudentPersona(disability_severity=0.0,
                                    is_employed=True, weekly_work_hours=40,
                                    financial_stress=0.7)
        p_dis = bm.calculate_environmental_pressure(student_dis)
        p_no = bm.calculate_environmental_pressure(student_no)
        assert p_dis < p_no  # more negative = more pressure

    def test_severe_disability_more_pressure(self):
        """Higher severity means more environmental pressure."""
        bm = BeanMetznerPressure()
        mild = StudentPersona(disability_severity=0.1, is_employed=False)
        severe = StudentPersona(disability_severity=0.8, is_employed=False)
        assert bm.calculate_environmental_pressure(severe) < bm.calculate_environmental_pressure(mild)
