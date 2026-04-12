"""Tests for the SimulationEngine."""

from synthed.agents.factory import StudentFactory
from synthed.simulation.engine import SimulationEngine
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.social_network import SocialNetwork


class TestSimulationEngine:
    def _run_sim(self, n=10, seed=42, weeks=None):
        env = ODLEnvironment()
        factory = StudentFactory(seed=seed)
        students = factory.generate_population(n=n)
        engine = SimulationEngine(environment=env, seed=seed)
        records, states, network = engine.run(students, weeks=weeks)
        return students, records, states, network, env

    def test_run_returns_three_tuple(self):
        students, records, states, network, _ = self._run_sim(n=5)
        assert isinstance(records, list)
        assert isinstance(states, dict)
        assert isinstance(network, SocialNetwork)

    def test_all_students_have_state(self):
        students, _, states, _, _ = self._run_sim(n=10)
        for s in students:
            assert s.id in states

    def test_engagement_history_length(self):
        students, _, states, _, env = self._run_sim(n=10)
        for s in students:
            state = states[s.id]
            if not state.has_dropped_out:
                assert len(state.weekly_engagement_history) == env.total_weeks

    def test_engagement_bounded(self):
        _, _, states, _, _ = self._run_sim(n=20)
        for state in states.values():
            for eng in state.weekly_engagement_history:
                assert 0.01 <= eng <= 0.99, f"Engagement {eng} out of bounds"

    def test_dropout_phase_max_5(self):
        _, _, states, _, _ = self._run_sim(n=20)
        for state in states.values():
            assert state.dropout_phase <= 5

    def test_deterministic_with_seed(self):
        _, _, states1, _, _ = self._run_sim(n=15, seed=42)
        _, _, states2, _, _ = self._run_sim(n=15, seed=42)
        dropouts1 = sum(1 for s in states1.values() if s.has_dropped_out)
        dropouts2 = sum(1 for s in states2.values() if s.has_dropped_out)
        assert dropouts1 == dropouts2

    def test_empty_student_list(self):
        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=42)
        records, states, network = engine.run([])
        assert records == []
        assert states == {}

    def test_high_risk_cohort_drops_more(self):
        from synthed.agents.persona import StudentPersona, BigFiveTraits

        env = ODLEnvironment()

        high_risk = []
        for i in range(20):
            high_risk.append(StudentPersona(
                name=f"HighRisk{i}",
                personality=BigFiveTraits(conscientiousness=0.15, neuroticism=0.85),
                employment_intensity=0.83, family_responsibility_level=0.8,
                financial_stress=0.9,
                self_regulation=0.15, motivation_type="amotivation",
                goal_commitment=0.15, self_efficacy=0.15,
                perceived_cost_benefit=0.15, learner_autonomy=0.15,
            ))

        low_risk = []
        for i in range(20):
            low_risk.append(StudentPersona(
                name=f"LowRisk{i}",
                personality=BigFiveTraits(conscientiousness=0.9, neuroticism=0.1),
                employment_intensity=0.0, family_responsibility_level=0.0,
                financial_stress=0.1,
                self_regulation=0.9, motivation_type="intrinsic",
                goal_commitment=0.9, self_efficacy=0.9,
                perceived_cost_benefit=0.9, learner_autonomy=0.85,
            ))

        engine_hr = SimulationEngine(environment=env, seed=42)
        _, states_hr, _ = engine_hr.run(high_risk)

        engine_lr = SimulationEngine(environment=env, seed=42)
        _, states_lr, _ = engine_lr.run(low_risk)

        hr_dropouts = sum(1 for s in states_hr.values() if s.has_dropped_out)
        lr_dropouts = sum(1 for s in states_lr.values() if s.has_dropped_out)
        assert hr_dropouts >= lr_dropouts

    def test_summary_statistics_with_unavoidable_withdrawals(self):
        """summary_statistics handles withdrawal_reason in phase_dist (lines 574, 585)."""
        from synthed.simulation.state import SimulationState

        states = {
            "s1": SimulationState(
                student_id="s1",
                has_dropped_out=True,
                dropout_week=3,
                withdrawal_reason="serious_illness",
                weekly_engagement_history=[0.5, 0.4, 0.3],
            ),
            "s2": SimulationState(
                student_id="s2",
                has_dropped_out=True,
                dropout_week=5,
                withdrawal_reason="family_emergency",
                weekly_engagement_history=[0.6, 0.5, 0.4, 0.3, 0.2],
            ),
            "s3": SimulationState(
                student_id="s3",
                has_dropped_out=False,
                weekly_engagement_history=[0.7, 0.7, 0.7],
            ),
        }

        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=42)
        summary = engine.summary_statistics(states)

        assert summary["dropout_count"] == 2
        assert summary["unavoidable_withdrawal_count"] == 2
        assert "serious_illness" in summary["unavoidable_withdrawal_reasons"]
        assert "family_emergency" in summary["unavoidable_withdrawal_reasons"]
        phase_dist = summary["dropout_phase_distribution"]
        assert "unavoidable_withdrawal" in phase_dist

    def test_summary_includes_std_final_engagement(self):
        """summary_statistics returns std_final_engagement for retained students."""
        from synthed.simulation.state import SimulationState

        states = {
            "s1": SimulationState(
                student_id="s1", has_dropped_out=False,
                weekly_engagement_history=[0.8, 0.7, 0.6],
            ),
            "s2": SimulationState(
                student_id="s2", has_dropped_out=False,
                weekly_engagement_history=[0.4, 0.3, 0.2],
            ),
            "s3": SimulationState(
                student_id="s3", has_dropped_out=True, dropout_week=2,
                weekly_engagement_history=[0.5, 0.3],
            ),
        }

        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=42)
        summary = engine.summary_statistics(states)

        assert "std_final_engagement" in summary
        # Only retained students (s1=0.6, s2=0.2) contribute
        assert summary["std_final_engagement"] is not None
        assert summary["std_final_engagement"] > 0  # two different values → nonzero std
        assert summary["mean_final_engagement"] is not None

    def test_std_final_engagement_none_when_all_dropout(self):
        """std_final_engagement is None when all students dropped out."""
        from synthed.simulation.state import SimulationState

        states = {
            "s1": SimulationState(
                student_id="s1", has_dropped_out=True, dropout_week=3,
                weekly_engagement_history=[0.5],
            ),
        }
        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=42)
        summary = engine.summary_statistics(states)
        assert summary["std_final_engagement"] is None

    def test_course_not_found_skipped(self):
        """Simulation skips courses not found by ID (line 358)."""
        from synthed.agents.persona import StudentPersona

        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=42)

        # Create a student with an enrolled_courses count higher than available
        student = StudentPersona(
            name="Test",
            enrolled_courses=4,
        )

        # Manually run with a state that has an invalid course ID
        from synthed.simulation.state import SimulationState
        states = {
            student.id: SimulationState(
                student_id=student.id,
                current_engagement=0.5,
                courses_active=["NONEXISTENT_COURSE_ID"],
            ),
        }
        engine.network = SocialNetwork()

        # _simulate_student_week should handle missing course gracefully
        context = env.get_week_context(1)
        records = engine._simulate_student_week(student, states[student.id], 1, context)
        # No crash, no records for the nonexistent course
        assert isinstance(records, list)
