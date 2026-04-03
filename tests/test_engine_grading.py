"""Engine integration tests for GradingConfig."""
from __future__ import annotations

import numpy as np
import pytest

from synthed.simulation.engine import SimulationEngine, SimulationState
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.grading import GradingConfig, GradingScale
from synthed.simulation.institutional import InstitutionalConfig


class TestSimulationStateGrading:
    def test_new_fields_exist(self):
        state = SimulationState(student_id="S001")
        assert state.midterm_exam_scores == []
        assert state.assignment_scores == []
        assert state.forum_scores == []
        assert state.final_score is None
        assert state.semester_grade is None
        assert state.outcome is None
        assert state.n_total_assignments == 0
        assert state.n_total_forums == 0


class TestEngineGradingConfig:
    def test_engine_accepts_grading_config(self):
        cfg = GradingConfig(scale=GradingScale.SCALE_4, grade_floor=0.45)
        engine = SimulationEngine(ODLEnvironment(), grading_config=cfg)
        assert engine.grading_config.scale == GradingScale.SCALE_4

    def test_engine_default_grading_config(self):
        engine = SimulationEngine(ODLEnvironment())
        assert engine.grading_config.scale == GradingScale.SCALE_100

    def test_inst_config_affects_quality(self):
        from synthed.agents.factory import StudentFactory
        from synthed.agents.persona import PersonaConfig

        high = InstitutionalConfig(instructional_design_quality=0.90)
        low = InstitutionalConfig(instructional_design_quality=0.10)
        factory = StudentFactory(PersonaConfig(), seed=42)
        students = factory.generate_population(n=200)

        engine_h = SimulationEngine(ODLEnvironment(), seed=42, institutional_config=high)
        engine_l = SimulationEngine(ODLEnvironment(), seed=42, institutional_config=low)
        _, states_h, _ = engine_h.run(students)
        _, states_l, _ = engine_l.run(students)

        gpas_h = [s.cumulative_gpa for s in states_h.values() if s.gpa_count > 0]
        gpas_l = [s.cumulative_gpa for s in states_l.values() if s.gpa_count > 0]
        assert np.mean(gpas_h) > np.mean(gpas_l)


class TestEngineOutcomes:
    def test_completed_student_has_outcome(self):
        from synthed.agents.factory import StudentFactory
        from synthed.agents.persona import PersonaConfig
        factory = StudentFactory(PersonaConfig(), seed=42)
        students = factory.generate_population(n=50)
        engine = SimulationEngine(ODLEnvironment(), seed=42)
        _, states, _ = engine.run(students)
        for state in states.values():
            if state.has_dropped_out:
                assert state.outcome == "Withdrawn"
            elif state.gpa_count > 0:
                assert state.outcome in ("Distinction", "Pass", "Fail")
                # semester_grade can be None if student missed final (outcome=Fail)
                if state.final_score is not None:
                    assert state.semester_grade is not None

    def test_late_submission_penalized(self):
        """Geç teslim kaliteyi düşürür."""
        from synthed.agents.factory import StudentFactory
        from synthed.agents.persona import PersonaConfig
        cfg = GradingConfig(late_penalty=0.10)
        factory = StudentFactory(PersonaConfig(), seed=42)
        students = factory.generate_population(n=50)
        engine = SimulationEngine(ODLEnvironment(), seed=42, grading_config=cfg)
        _, states, _ = engine.run(students)
        assert any(s.gpa_count > 0 for s in states.values())
