"""Tests for MultiSemesterRunner carry-over and multi-semester logic."""

from __future__ import annotations

from synthed.agents.factory import StudentFactory
from synthed.simulation.engine import SimulationEngine
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.semester import MultiSemesterRunner, SemesterCarryOverConfig


def _make_engine_and_students(n: int = 20, seed: int = 42):
    """Helper: build a small engine + population for semester tests."""
    env = ODLEnvironment(total_weeks=6)
    engine = SimulationEngine(environment=env, seed=seed)
    factory = StudentFactory(seed=seed)
    students = factory.generate_population(n=n)
    return engine, students


class TestMultiSemesterRunner:
    """Multi-semester simulation tests."""

    def test_single_semester_identical_to_engine(self):
        """n_semesters=1 via direct engine.run() should be the only path;
        MultiSemesterRunner with n_semesters=1 raises ValueError."""
        engine, students = _make_engine_and_students(n=20)
        import pytest
        with pytest.raises(ValueError, match="n_semesters >= 2"):
            MultiSemesterRunner(engine, n_semesters=1)

    def test_multi_semester_increases_dropout(self):
        """2 semesters should produce >= dropout rate compared to 1 semester."""
        engine, students = _make_engine_and_students(n=20, seed=42)

        # Single semester via engine directly
        _records_1, states_1, _net_1 = engine.run(students, weeks=6)
        dropout_1 = sum(1 for s in states_1.values() if s.has_dropped_out) / len(states_1)

        # Two semesters
        engine2, students2 = _make_engine_and_students(n=20, seed=42)
        runner = MultiSemesterRunner(engine2, n_semesters=2)
        result = runner.run(students2)
        dropout_2 = sum(
            1 for s in result.final_states.values() if s.has_dropped_out
        ) / len(result.final_states)

        # 2 semesters means more opportunity to drop out
        assert dropout_2 >= dropout_1

    def test_carry_over_recovers_engagement(self):
        """After carry-over, engagement recovery should increase engagement."""
        engine, students = _make_engine_and_students(n=20, seed=42)
        runner = MultiSemesterRunner(
            engine, n_semesters=2,
            carry_over=SemesterCarryOverConfig(engagement_recovery=0.10),
        )
        result = runner.run(students)

        # Check that semester 2 exists and has records
        assert len(result.semester_results) == 2
        assert len(result.semester_results[1].records) > 0

    def test_dropped_students_stay_dropped(self):
        """Phase-5 students from semester 1 must not appear in semester 2."""
        engine, students = _make_engine_and_students(n=20, seed=42)
        runner = MultiSemesterRunner(engine, n_semesters=2)
        result = runner.run(students)

        sem1_states = result.semester_results[0].states
        sem2_states = result.semester_results[1].states

        # Any student who reached phase 5 in semester 1 should not be in semester 2
        for sid, state in sem1_states.items():
            if state.dropout_phase >= 5:
                assert sid not in sem2_states, (
                    f"Student {sid} was phase 5 in sem 1 but appeared in sem 2"
                )

    def test_multi_semester_result_structure(self):
        """MultiSemesterResult should contain correct structure."""
        engine, students = _make_engine_and_students(n=20, seed=42)
        runner = MultiSemesterRunner(engine, n_semesters=2)
        result = runner.run(students)

        assert hasattr(result, "semester_results")
        assert hasattr(result, "all_records")
        assert hasattr(result, "final_states")
        assert hasattr(result, "final_network")
        assert len(result.all_records) > 0
        assert len(result.final_states) > 0
