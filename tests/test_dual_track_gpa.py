"""Tests for dual-track GPA: transcript GPA vs perceived mastery."""
import numpy as np

from synthed.simulation.engine import SimulationState, SimulationEngine
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.theories.kember import KemberCostBenefit
from synthed.simulation.theories.sdt_motivation import SDTMotivationDynamics, SDTNeedSatisfaction
from synthed.simulation.theories.baulke import BaulkeDropoutPhase
from synthed.agents.persona import StudentPersona


class TestSimulationStateMasteryFields:
    def test_initial_mastery_fields_exist(self):
        state = SimulationState(student_id="test-001")
        assert state.perceived_mastery_sum == 0.0
        assert state.perceived_mastery_count == 0

    def test_perceived_mastery_property_no_items(self):
        state = SimulationState(student_id="test-001")
        assert state.perceived_mastery == 0.5

    def test_perceived_mastery_property_with_items(self):
        state = SimulationState(student_id="test-001")
        state.perceived_mastery_sum = 1.2
        state.perceived_mastery_count = 3
        assert abs(state.perceived_mastery - 0.4) < 1e-9


class TestRecordGradedItemDualTrack:
    def test_graded_item_updates_both_tracks(self):
        engine = SimulationEngine(environment=ODLEnvironment(), seed=42)
        state = SimulationState(student_id="test-001")
        engine._record_graded_item(state, 0.6)
        assert state.gpa_count == 1
        assert abs(state.cumulative_gpa - 3.12) < 0.01
        assert state.perceived_mastery_count == 1
        assert abs(state.perceived_mastery - 0.6) < 1e-9

    def test_graded_item_mastery_diverges_from_gpa(self):
        engine = SimulationEngine(environment=ODLEnvironment(), seed=42)
        state = SimulationState(student_id="test-001")
        for q in [0.3, 0.5, 0.7]:
            engine._record_graded_item(state, q)
        assert abs(state.perceived_mastery - 0.5) < 1e-9
        assert state.cumulative_gpa > 2.0

    def test_mastery_zero_quality(self):
        engine = SimulationEngine(environment=ODLEnvironment(), seed=42)
        state = SimulationState(student_id="test-001")
        engine._record_graded_item(state, 0.0)
        assert abs(state.perceived_mastery - 0.0) < 1e-9
        assert state.cumulative_gpa > 0.0


class TestKemberUsesPerceivedMastery:
    """Kember cost-benefit must be driven by perceived mastery, not transcript GPA."""

    def test_high_gpa_low_mastery_does_not_boost_cost_benefit(self):
        """High transcript GPA with low mastery (0.3) should not produce positive GPA boost."""
        kember = KemberCostBenefit()
        student = StudentPersona()
        state = SimulationState(
            student_id="test-001",
            perceived_cost_benefit=0.5,
            cumulative_gpa=3.2,
            gpa_count=5,
            missed_assignments_streak=0,
        )
        state.perceived_mastery_sum = 1.5   # mastery = 0.3
        state.perceived_mastery_count = 5
        initial_cb = state.perceived_cost_benefit
        # neutral quality record so quality factor doesn't dominate
        from synthed.simulation.engine import InteractionRecord
        records = [
            InteractionRecord(student_id="test-001", week=5, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        kember.recalculate(student, state, {}, records, avg_td=0.5)
        # mastery=0.3 < 0.5: GPA contribution should be negative, not positive
        # The _GPA_CB_FACTOR is 0.01, mastery-0.5 = -0.2, delta = -0.002
        # So cost_benefit must NOT have risen by more than a tiny rounding margin
        assert state.perceived_cost_benefit <= initial_cb + 0.003

    def test_low_gpa_high_mastery_boosts_cost_benefit(self):
        """Low transcript GPA with high mastery (0.8) should yield positive mastery contribution."""
        kember = KemberCostBenefit()
        student = StudentPersona()
        state = SimulationState(
            student_id="test-001",
            perceived_cost_benefit=0.5,
            cumulative_gpa=1.2,
            gpa_count=5,
            missed_assignments_streak=0,
        )
        state.perceived_mastery_sum = 4.0   # mastery = 0.8
        state.perceived_mastery_count = 5
        from synthed.simulation.engine import InteractionRecord
        records = [
            InteractionRecord(student_id="test-001", week=5, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        kember.recalculate(student, state, {}, records, avg_td=0.5)
        # mastery=0.8 > 0.5 → positive contribution; previous GPA=1.2 would have been negative
        assert state.perceived_cost_benefit > 0.5


class TestSDTUsesPerceivedMastery:
    """SDT competence need must be anchored to perceived mastery, not transcript GPA."""

    def test_high_gpa_low_mastery_limits_competence_boost(self):
        """High transcript GPA (3.5) with low mastery (0.3) should NOT boost competence."""
        sdt = SDTMotivationDynamics()
        student = StudentPersona(self_efficacy=0.5)
        state = SimulationState(
            student_id="test-001",
            current_engagement=0.5,
            cumulative_gpa=3.5,
            gpa_count=5,
        )
        state.sdt_needs = SDTNeedSatisfaction(competence=0.5)
        state.perceived_mastery_sum = 1.5   # mastery = 0.3
        state.perceived_mastery_count = 5
        from synthed.simulation.engine import InteractionRecord
        records = [
            InteractionRecord(student_id="test-001", week=5, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        sdt.update_needs(student, state, 5, records)
        # mastery=0.3 → negative contribution; GPA would have been strongly positive
        competence_change = state.sdt_needs.competence - 0.5
        assert competence_change < 0.003

    def test_low_gpa_high_mastery_boosts_competence(self):
        """Low transcript GPA (1.2) with high mastery (0.8) should boost competence."""
        sdt = SDTMotivationDynamics()
        student = StudentPersona(self_efficacy=0.5)
        state = SimulationState(
            student_id="test-001",
            current_engagement=0.5,
            cumulative_gpa=1.2,
            gpa_count=5,
        )
        state.sdt_needs = SDTNeedSatisfaction(competence=0.5)
        state.perceived_mastery_sum = 4.0   # mastery = 0.8
        state.perceived_mastery_count = 5
        from synthed.simulation.engine import InteractionRecord
        records = [
            InteractionRecord(student_id="test-001", week=5, course_id="CS101",
                              interaction_type="assignment_submit", quality_score=0.5),
        ]
        sdt.update_needs(student, state, 5, records)
        # mastery=0.8 → positive contribution; old GPA=1.2 would have been negative
        assert state.sdt_needs.competence > 0.5


class TestBaulkeUsesPerceivedMastery:
    """Baulke phase transitions must use perceived mastery, not transcript GPA."""

    def test_nonfit_triggers_on_low_mastery_not_high_gpa(self):
        """Low mastery (0.3) with soft engagement should trigger non-fit even when GPA is high."""
        baulke = BaulkeDropoutPhase()
        student = StudentPersona()
        state = SimulationState(
            student_id="test-001",
            current_engagement=0.43,  # above _NONFIT_ENG_THRESHOLD(0.40), below _NONFIT_ENG_SOFT(0.45)
            dropout_phase=0,
            cumulative_gpa=3.5,   # high GPA — old code would NOT trigger
            gpa_count=3,
        )
        state.perceived_mastery_sum = 0.9   # mastery = 0.3 < _NONFIT_MASTERY_THRESHOLD(0.4)
        state.perceived_mastery_count = 3
        env = ODLEnvironment()
        rng = np.random.default_rng(42)
        baulke.advance_phase(student, state, 5, env, lambda s, st: 0.5, rng)
        # Should advance because mastery is below the threshold
        assert state.dropout_phase == 1

    def test_nonfit_does_not_trigger_high_mastery_soft_engagement(self):
        """High mastery (0.8) at soft engagement should NOT trigger non-fit on mastery condition."""
        baulke = BaulkeDropoutPhase()
        student = StudentPersona()
        state = SimulationState(
            student_id="test-001",
            current_engagement=0.43,  # between thresholds
            dropout_phase=0,
            cumulative_gpa=1.0,   # low GPA — old code would trigger
            gpa_count=3,
        )
        state.perceived_mastery_sum = 4.0   # mastery = 0.8 — high, no trigger
        state.perceived_mastery_count = 5
        env = ODLEnvironment()
        rng = np.random.default_rng(42)
        baulke.advance_phase(student, state, 5, env, lambda s, st: 0.5, rng)
        # High mastery → mastery condition not met; other soft conditions not active
        # (no exhaustion, no high TD, cognitive presence is default 0.5 > _NONFIT_COG_THRESHOLD)
        assert state.dropout_phase == 0
