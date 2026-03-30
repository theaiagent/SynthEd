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
                is_employed=True, weekly_work_hours=50,
                has_family_responsibilities=True, financial_stress=0.9,
                self_regulation=0.15, motivation_type="amotivation",
                goal_commitment=0.15, self_efficacy=0.15,
                perceived_cost_benefit=0.15, learner_autonomy=0.15,
            ))

        low_risk = []
        for i in range(20):
            low_risk.append(StudentPersona(
                name=f"LowRisk{i}",
                personality=BigFiveTraits(conscientiousness=0.9, neuroticism=0.1),
                is_employed=False, weekly_work_hours=0,
                has_family_responsibilities=False, financial_stress=0.1,
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
