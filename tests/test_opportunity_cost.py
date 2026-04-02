"""Tests for Kember opportunity cost mechanism."""

from synthed.simulation.engine import SimulationState
from synthed.simulation.theories.kember import KemberCostBenefit
from synthed.agents.persona import PersonaConfig
from synthed.agents.factory import StudentFactory


class TestOpportunityCostPressure:
    """Employed students with high financial stress should lose cost-benefit."""

    def _make_student(self, is_employed=True, financial_stress=0.7):
        factory = StudentFactory(config=PersonaConfig(
            employment_rate=1.0 if is_employed else 0.0,
            financial_stress_mean=financial_stress,
        ), seed=42)
        return factory.generate_population(n=1)[0]

    def test_employed_high_stress_reduces_cb(self):
        """Employed student with financial_stress > 0.5 should see CB decrease."""
        kember = KemberCostBenefit()
        student = self._make_student(is_employed=True, financial_stress=0.8)
        state = SimulationState(student_id=student.id)
        state.perceived_cost_benefit = 0.6

        initial_cb = state.perceived_cost_benefit
        kember.recalculate(student, state, context={}, records=[], avg_td=0.5,
                           week=7, total_weeks=14)

        assert state.perceived_cost_benefit < initial_cb

    def test_unemployed_no_opportunity_cost(self):
        """Unemployed student should NOT get opportunity cost penalty."""
        kember = KemberCostBenefit()
        student = self._make_student(is_employed=False, financial_stress=0.8)
        state = SimulationState(student_id=student.id)
        state.perceived_cost_benefit = 0.6

        initial_cb = state.perceived_cost_benefit
        kember.recalculate(student, state, context={}, records=[], avg_td=0.5,
                           week=7, total_weeks=14)

        assert state.perceived_cost_benefit >= initial_cb - 0.01

    def test_low_stress_no_opportunity_cost(self):
        """Employed but low financial stress should NOT trigger opportunity cost."""
        kember = KemberCostBenefit()
        student = self._make_student(is_employed=True, financial_stress=0.2)
        state = SimulationState(student_id=student.id)
        state.perceived_cost_benefit = 0.6

        initial_cb = state.perceived_cost_benefit
        kember.recalculate(student, state, context={}, records=[], avg_td=0.5,
                           week=7, total_weeks=14)

        assert state.perceived_cost_benefit >= initial_cb - 0.01


class TestTimeDiscount:
    """Cost-benefit should erode more as the semester progresses."""

    def _make_student(self):
        factory = StudentFactory(config=PersonaConfig(
            employment_rate=1.0,
            financial_stress_mean=0.7,
        ), seed=42)
        return factory.generate_population(n=1)[0]

    def test_late_semester_stronger_erosion(self):
        """Week 12/14 should produce more CB erosion than week 2/14."""
        kember = KemberCostBenefit()
        student = self._make_student()

        state_early = SimulationState(student_id=student.id)
        state_early.perceived_cost_benefit = 0.5
        kember.recalculate(student, state_early, context={}, records=[], avg_td=0.5,
                           week=2, total_weeks=14)

        state_late = SimulationState(student_id=student.id)
        state_late.perceived_cost_benefit = 0.5
        kember.recalculate(student, state_late, context={}, records=[], avg_td=0.5,
                           week=12, total_weeks=14)

        assert state_late.perceived_cost_benefit < state_early.perceived_cost_benefit

    def test_backward_compatible_without_week_params(self):
        """recalculate without week/total_weeks should not crash."""
        kember = KemberCostBenefit()
        student = self._make_student()
        state = SimulationState(student_id=student.id)
        state.perceived_cost_benefit = 0.5

        kember.recalculate(student, state, context={}, records=[], avg_td=0.5)
        assert 0.0 < state.perceived_cost_benefit < 1.0
