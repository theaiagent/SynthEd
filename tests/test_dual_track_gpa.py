"""Tests for dual-track GPA: transcript GPA vs perceived mastery."""
from synthed.simulation.engine import SimulationState, SimulationEngine
from synthed.simulation.environment import ODLEnvironment


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
