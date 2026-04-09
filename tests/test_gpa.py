"""Tests for GPA/academic success computation."""

import csv

from synthed.agents.persona import StudentPersona, BigFiveTraits
from synthed.agents.factory import StudentFactory
from synthed.simulation.engine import SimulationEngine
from synthed.simulation.state import SimulationState
from synthed.simulation.environment import ODLEnvironment
from synthed.data_output.exporter import DataExporter


class TestGPAComputation:
    """GPA tracking across the simulation lifecycle."""

    def _run_sim(self, n=10, seed=42, weeks=None):
        env = ODLEnvironment()
        factory = StudentFactory(seed=seed)
        students = factory.generate_population(n=n)
        engine = SimulationEngine(environment=env, seed=seed)
        records, states, network = engine.run(students, weeks=weeks)
        return students, records, states, network, engine

    def test_gpa_starts_at_zero(self):
        """New SimulationState should have cumulative_gpa=0 and gpa_count=0."""
        state = SimulationState(student_id="test")
        assert state.cumulative_gpa == 0.0
        assert state.gpa_points_sum == 0.0
        assert state.gpa_count == 0

    def test_gpa_updates_after_simulation(self):
        """After running the simulation, at least some students should have GPA > 0."""
        students, records, states, _, _ = self._run_sim(n=20)
        students_with_gpa = [s for s in states.values() if s.gpa_count > 0]
        assert len(students_with_gpa) > 0, "No students received graded items"
        for state in students_with_gpa:
            assert state.cumulative_gpa > 0.0

    def test_gpa_bounded_0_to_4(self):
        """GPA must stay within the 0.0-4.0 range."""
        _, _, states, _, _ = self._run_sim(n=30, seed=123)
        for state in states.values():
            if state.gpa_count > 0:
                assert 0.0 <= state.cumulative_gpa <= 4.0, (
                    f"GPA {state.cumulative_gpa} out of [0, 4] range"
                )

    def test_gpa_count_matches_graded_items(self):
        """gpa_count should equal total assignments submitted + exams taken."""
        students, records, states, _, _ = self._run_sim(n=10)
        for student in students:
            state = states[student.id]
            graded_records = [
                r for r in records
                if r.student_id == student.id
                and r.interaction_type in ("assignment_submit", "exam")
            ]
            assert state.gpa_count == len(graded_records), (
                f"Student {student.id}: gpa_count={state.gpa_count} "
                f"but {len(graded_records)} graded records"
            )

    def test_gpa_consistent_with_points(self):
        """cumulative_gpa should equal gpa_points_sum / gpa_count."""
        _, _, states, _, _ = self._run_sim(n=20)
        for state in states.values():
            if state.gpa_count > 0:
                expected = state.gpa_points_sum / state.gpa_count
                assert abs(state.cumulative_gpa - expected) < 1e-9, (
                    f"GPA {state.cumulative_gpa} != points/count "
                    f"({state.gpa_points_sum}/{state.gpa_count}={expected})"
                )

    def test_gpa_in_outcomes_csv(self, tmp_path):
        """outcomes.csv should include a final_gpa column with valid values."""
        students, records, states, network, _ = self._run_sim(n=15)
        exporter = DataExporter(output_dir=str(tmp_path))
        exporter.export_outcomes(students, states, network)

        outcomes_path = tmp_path / "outcomes.csv"
        assert outcomes_path.exists()

        with open(outcomes_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "final_gpa" in reader.fieldnames
            rows = list(reader)

        # At least some students should have a non-empty final_gpa
        gpa_values = [r["final_gpa"] for r in rows if r["final_gpa"] != ""]
        assert len(gpa_values) > 0, "No students have final_gpa in outcomes.csv"
        for gpa_str in gpa_values:
            gpa = float(gpa_str)
            assert 0.0 <= gpa <= 4.0

    def test_gpa_in_summary_statistics(self):
        """summary_statistics should include mean_final_gpa."""
        students, _, states, _, engine = self._run_sim(n=20)
        stats = engine.summary_statistics(states)
        assert "mean_final_gpa" in stats
        if stats["mean_final_gpa"] is not None:
            assert 0.0 <= stats["mean_final_gpa"] <= 4.0

    def test_high_ability_students_have_higher_gpa(self):
        """Students with higher prior_gpa and self-efficacy should tend to earn higher GPA."""
        env = ODLEnvironment()

        high_ability = []
        for i in range(20):
            high_ability.append(StudentPersona(
                name=f"HighAbility{i}",
                personality=BigFiveTraits(conscientiousness=0.9, neuroticism=0.1),
                prior_gpa=3.8,
                self_efficacy=0.9,
                self_regulation=0.9,
                time_management=0.9,
                academic_reading_writing=0.9,
                motivation_type="intrinsic",
                goal_commitment=0.9,
                is_employed=False,
                weekly_work_hours=0,
                has_family_responsibilities=False,
                financial_stress=0.1,
                perceived_cost_benefit=0.9,
                learner_autonomy=0.85,
                digital_literacy=0.9,
            ))

        low_ability = []
        for i in range(20):
            low_ability.append(StudentPersona(
                name=f"LowAbility{i}",
                personality=BigFiveTraits(conscientiousness=0.15, neuroticism=0.85),
                prior_gpa=1.5,
                self_efficacy=0.15,
                self_regulation=0.15,
                time_management=0.2,
                academic_reading_writing=0.2,
                motivation_type="amotivation",
                goal_commitment=0.15,
                is_employed=True,
                weekly_work_hours=50,
                has_family_responsibilities=True,
                financial_stress=0.9,
                perceived_cost_benefit=0.15,
                learner_autonomy=0.15,
                digital_literacy=0.3,
            ))

        engine_ha = SimulationEngine(environment=env, seed=42)
        _, states_ha, _ = engine_ha.run(high_ability)

        engine_la = SimulationEngine(environment=env, seed=42)
        _, states_la, _ = engine_la.run(low_ability)

        ha_gpas = [s.cumulative_gpa for s in states_ha.values() if s.gpa_count > 0]
        la_gpas = [s.cumulative_gpa for s in states_la.values() if s.gpa_count > 0]

        # High-ability students should have graded items
        assert len(ha_gpas) > 0, "No high-ability students had graded items"

        if ha_gpas and la_gpas:
            mean_ha = sum(ha_gpas) / len(ha_gpas)
            mean_la = sum(la_gpas) / len(la_gpas)
            assert mean_ha > mean_la, (
                f"High-ability mean GPA ({mean_ha:.2f}) should exceed "
                f"low-ability mean GPA ({mean_la:.2f})"
            )

    def test_gpa_feedback_loop_stability(self):
        """Verify no runaway effects from GPA feedback — all values stay bounded."""
        students, records, states, _, _ = self._run_sim(n=50, seed=42)
        for state in states.values():
            assert 0.0 <= state.cumulative_gpa <= 4.0
            assert 0.0 <= state.perceived_cost_benefit <= 1.0
            assert 0.0 <= state.current_engagement <= 1.0
            assert 0.0 <= state.sdt_needs.competence <= 1.0
