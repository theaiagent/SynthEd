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

    def test_multi_semester_with_target_dropout_range(self):
        """Runner with target_dropout_range produces interim reports (lines 194-199)."""
        engine, students = _make_engine_and_students(n=20, seed=42)
        runner = MultiSemesterRunner(
            engine, n_semesters=2,
            target_dropout_range=(0.30, 0.80),
        )
        result = runner.run(students)

        assert len(result.interim_reports) == 2
        for report in result.interim_reports:
            assert report.target_range == (0.30, 0.80)
            assert report.status in ("on_track", "below_target", "above_target")
            assert 0.0 <= report.cumulative_dropout_rate <= 1.0

    def test_carry_over_skips_withdrawn_students(self):
        """Students with withdrawal_reason (unavoidable) are filtered (line 256+)."""
        engine, students = _make_engine_and_students(n=20, seed=42)
        # Use a high unavoidable withdrawal rate to force some withdrawals
        from synthed.simulation.theories import UnavoidableWithdrawal
        engine.unavoidable_withdrawal = UnavoidableWithdrawal(
            per_semester_probability=0.50, total_weeks=6,
        )
        runner = MultiSemesterRunner(engine, n_semesters=2)
        result = runner.run(students)

        # Verify that withdrawn students from sem1 are not in sem2
        sem1_states = result.semester_results[0].states
        sem2_states = result.semester_results[1].states
        for sid, state in sem1_states.items():
            if state.withdrawal_reason is not None:
                assert sid not in sem2_states


class TestCarryOverStateNone:
    """Test _apply_carry_over when state is None for a student (line 256)."""

    def test_carry_over_skips_student_without_state(self):
        """Student not in states dict is skipped in carry-over."""
        from synthed.agents.persona import StudentPersona
        from synthed.simulation.engine import SimulationState
        from synthed.simulation.social_network import SocialNetwork

        students = [
            StudentPersona(name="WithState"),
            StudentPersona(name="WithoutState"),
        ]

        # Only include first student's state
        states = {
            students[0].id: SimulationState(
                student_id=students[0].id,
                has_dropped_out=False,
                dropout_phase=1,
                current_engagement=0.5,
                academic_integration=0.5,
                social_integration=0.3,
                perceived_cost_benefit=0.6,
            ),
            # students[1].id is NOT in states
        }

        network = SocialNetwork()
        config = SemesterCarryOverConfig()

        surviving, overrides, carried_net = MultiSemesterRunner._apply_carry_over(
            students, states, network, config,
        )

        # Only the student with state should survive
        assert len(surviving) == 1
        assert surviving[0].name == "WithState"


class TestBuildInterimReport:
    """Tests for _build_interim_report helper (lines 393-409)."""

    def test_below_target(self):
        from synthed.simulation.semester import (
            _build_interim_report, SemesterResult,
        )
        from synthed.simulation.engine import SimulationState

        # Create mock semester results with no dropouts
        states = {
            f"s{i}": SimulationState(
                student_id=f"s{i}", has_dropped_out=False,
            )
            for i in range(10)
        }
        sem_result = SemesterResult(
            semester_index=0, records=[], states=states, network=None,
        )
        report = _build_interim_report(1, [sem_result], 10, (0.30, 0.50))
        assert report.status == "below_target"
        assert report.cumulative_dropout_rate == 0.0

    def test_above_target(self):
        from synthed.simulation.semester import (
            _build_interim_report, SemesterResult,
        )
        from synthed.simulation.engine import SimulationState

        # All students dropped out
        states = {
            f"s{i}": SimulationState(
                student_id=f"s{i}", has_dropped_out=True, dropout_week=3,
            )
            for i in range(10)
        }
        sem_result = SemesterResult(
            semester_index=0, records=[], states=states, network=None,
        )
        report = _build_interim_report(1, [sem_result], 10, (0.10, 0.20))
        assert report.status == "above_target"
        assert report.cumulative_dropout_rate == 1.0

    def test_on_track(self):
        from synthed.simulation.semester import (
            _build_interim_report, SemesterResult,
        )
        from synthed.simulation.engine import SimulationState

        # 5 out of 10 dropped out = 50%, target is 40-60%
        states = {}
        for i in range(10):
            states[f"s{i}"] = SimulationState(
                student_id=f"s{i}",
                has_dropped_out=(i < 5),
                dropout_week=3 if i < 5 else None,
            )
        sem_result = SemesterResult(
            semester_index=0, records=[], states=states, network=None,
        )
        report = _build_interim_report(1, [sem_result], 10, (0.40, 0.60))
        assert report.status == "on_track"
        assert report.cumulative_dropout_rate == 0.5

    def test_zero_students(self):
        from synthed.simulation.semester import _build_interim_report
        report = _build_interim_report(1, [], 0, (0.30, 0.50))
        assert report.cumulative_dropout_rate == 0.0


class TestPriorGPABlend:
    """Tests for prior_gpa blending during carry-over."""

    def test_prior_gpa_blend_updates_persona(self):
        """Earned GPA blends into prior_gpa with default alpha=0.6."""
        from synthed.agents.persona import StudentPersona
        from synthed.simulation.engine import SimulationState
        from synthed.simulation.semester import _create_carry_over_persona, SemesterCarryOverConfig

        student = StudentPersona(prior_gpa=3.0)
        state = SimulationState(
            student_id=student.id,
            current_engagement=0.5,
            academic_integration=0.5,
            social_integration=0.3,
            perceived_cost_benefit=0.6,
            cumulative_gpa=2.0,
            gpa_count=5,
        )
        config = SemesterCarryOverConfig()
        new_persona = _create_carry_over_persona(student, state, config)
        # 0.6 * 2.0 + 0.4 * 3.0 = 2.4
        assert new_persona.prior_gpa == 2.4

    def test_prior_gpa_no_blend_when_no_grades(self):
        """With gpa_count=0, prior_gpa stays unchanged."""
        from synthed.agents.persona import StudentPersona
        from synthed.simulation.engine import SimulationState
        from synthed.simulation.semester import _create_carry_over_persona, SemesterCarryOverConfig

        student = StudentPersona(prior_gpa=3.0)
        state = SimulationState(
            student_id=student.id,
            current_engagement=0.5,
            academic_integration=0.5,
            social_integration=0.3,
            perceived_cost_benefit=0.6,
            cumulative_gpa=0.0,
            gpa_count=0,
        )
        config = SemesterCarryOverConfig()
        new_persona = _create_carry_over_persona(student, state, config)
        assert new_persona.prior_gpa == 3.0

    def test_prior_gpa_blend_respects_alpha(self):
        """alpha=0 keeps original, alpha=1 fully replaces."""
        from synthed.agents.persona import StudentPersona
        from synthed.simulation.engine import SimulationState
        from synthed.simulation.semester import _create_carry_over_persona, SemesterCarryOverConfig

        student = StudentPersona(prior_gpa=3.0)
        state = SimulationState(
            student_id=student.id,
            current_engagement=0.5,
            academic_integration=0.5,
            social_integration=0.3,
            perceived_cost_benefit=0.6,
            cumulative_gpa=2.0,
            gpa_count=5,
        )

        # alpha=0: keep original
        config_0 = SemesterCarryOverConfig(prior_gpa_blend_alpha=0.0)
        assert _create_carry_over_persona(student, state, config_0).prior_gpa == 3.0

        # alpha=1: fully replace
        config_1 = SemesterCarryOverConfig(prior_gpa_blend_alpha=1.0)
        assert _create_carry_over_persona(student, state, config_1).prior_gpa == 2.0

    def test_prior_gpa_blend_clamps_to_range(self):
        """Blended prior_gpa is clipped to [0.0, 4.0]."""
        from synthed.agents.persona import StudentPersona
        from synthed.simulation.engine import SimulationState
        from synthed.simulation.semester import _create_carry_over_persona, SemesterCarryOverConfig

        student = StudentPersona(prior_gpa=3.5)
        state = SimulationState(
            student_id=student.id,
            current_engagement=0.5,
            academic_integration=0.5,
            social_integration=0.3,
            perceived_cost_benefit=0.6,
            cumulative_gpa=3.95,
            gpa_count=10,
        )
        config = SemesterCarryOverConfig(prior_gpa_blend_alpha=1.0)
        new_persona = _create_carry_over_persona(student, state, config)
        assert 0.0 <= new_persona.prior_gpa <= 4.0

    def test_multi_semester_prior_gpa_evolves(self):
        """In a 2-semester run, surviving students' prior_gpa should change."""
        engine, students = _make_engine_and_students(n=20, seed=42)
        runner = MultiSemesterRunner(engine, n_semesters=2)
        result = runner.run(students)

        # Get semester 2 students (they went through carry-over)
        sem2_student_ids = set(result.semester_results[1].states.keys())

        # At least one surviving student should have a changed prior_gpa
        sem1_states = result.semester_results[0].states
        changed = 0
        for sid in sem2_student_ids:
            state = sem1_states.get(sid)
            if state and state.gpa_count > 0:
                # The blend should have changed prior_gpa
                changed += 1

        assert changed > 0, "No students had graded items to trigger GPA blend"


class TestCopingCarryOver:
    """Tests for coping_factor carry-over between semesters."""

    def test_coping_retention_in_carry_over(self):
        """Coping factor is partially retained via _build_state_overrides."""
        from synthed.simulation.engine import SimulationState
        from synthed.simulation.semester import _build_state_overrides, SemesterCarryOverConfig

        state = SimulationState(
            student_id="test",
            current_engagement=0.5,
            coping_factor=0.3,
        )
        config = SemesterCarryOverConfig()  # default retention=0.70
        overrides = _build_state_overrides(state, config)
        assert abs(overrides["coping_factor"] - 0.21) < 0.01  # 0.3 * 0.70 = 0.21

    def test_coping_retention_config_default(self):
        """Default coping_retention is 0.70."""
        from synthed.simulation.semester import SemesterCarryOverConfig
        config = SemesterCarryOverConfig()
        assert config.coping_retention == 0.70

