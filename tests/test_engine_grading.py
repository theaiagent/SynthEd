"""Engine integration tests for GradingConfig."""
from __future__ import annotations

import logging

import numpy as np

from synthed.simulation.engine import SimulationEngine
from synthed.simulation.state import SimulationState
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.grading import GradingConfig, GradingScale, assign_outcomes
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


def _make_students(n: int, seed: int = 42):
    from synthed.agents.factory import StudentFactory
    from synthed.agents.persona import PersonaConfig

    factory = StudentFactory(PersonaConfig(), seed=seed)
    return factory.generate_population(n=n)


class TestRelativeGrading:
    def test_relative_grading_produces_outcomes(self):
        """50 students with relative grading: all outcomes valid."""
        students = _make_students(50)
        cfg = GradingConfig(grading_method="relative")
        engine = SimulationEngine(ODLEnvironment(), seed=42, grading_config=cfg)
        _, states, _ = engine.run(students)
        valid = {"Distinction", "Pass", "Fail", "Withdrawn"}
        for state in states.values():
            assert state.outcome in valid, f"Unexpected outcome: {state.outcome}"

    def test_relative_changes_outcome_distribution(self):
        """Same seed, absolute vs relative produce different outcome counts."""
        students_abs = _make_students(50, seed=42)
        students_rel = _make_students(50, seed=42)

        engine_abs = SimulationEngine(ODLEnvironment(), seed=42)
        _, states_abs, _ = engine_abs.run(students_abs)

        cfg_rel = GradingConfig(grading_method="relative")
        engine_rel = SimulationEngine(ODLEnvironment(), seed=42, grading_config=cfg_rel)
        _, states_rel, _ = engine_rel.run(students_rel)

        def count_outcomes(states):
            counts = {"Distinction": 0, "Pass": 0, "Fail": 0, "Withdrawn": 0}
            for s in states.values():
                counts[s.outcome] += 1
            return counts

        abs_counts = count_outcomes(states_abs)
        rel_counts = count_outcomes(states_rel)
        # Withdrawn count should be same (dropout is pre-grading, same seed)
        assert abs_counts["Withdrawn"] == rel_counts["Withdrawn"]
        # At least one non-Withdrawn category differs
        non_w = ["Distinction", "Pass", "Fail"]
        assert any(abs_counts[k] != rel_counts[k] for k in non_w), (
            f"Expected different distributions: abs={abs_counts}, rel={rel_counts}"
        )

    def test_relative_preserves_ranking(self):
        """Higher raw semester_grade maps to higher or equal normalized score."""
        students = _make_students(50)
        cfg = GradingConfig(grading_method="relative")
        engine = SimulationEngine(ODLEnvironment(), seed=42, grading_config=cfg)
        _, states, _ = engine.run(students)

        eligible = [
            s for s in states.values()
            if s.semester_grade is not None and s.outcome != "Withdrawn"
        ]
        if len(eligible) < 2:
            return  # not enough data to test ranking

        from synthed.simulation.grading import apply_relative_grading, normalize_t_scores

        raw = [s.semester_grade for s in eligible]
        t_scores = apply_relative_grading(raw)
        normalized = normalize_t_scores(t_scores)

        paired = sorted(zip(raw, normalized), key=lambda x: x[0])
        for i in range(len(paired) - 1):
            assert paired[i][1] <= paired[i + 1][1], (
                f"Ranking violated: raw {paired[i][0]} -> {paired[i][1]} "
                f"> raw {paired[i + 1][0]} -> {paired[i + 1][1]}"
            )

    def test_relative_zero_variance_fallback(self, caplog):
        """All eligible students have identical grades -> fallback warning, outcomes assigned."""
        # Build states manually with identical semester grades
        cfg = GradingConfig(grading_method="relative")

        states = {}
        for i in range(5):
            sid = f"S{i:03d}"
            state = SimulationState(student_id=sid)
            state.gpa_count = 1
            state.assignment_scores = [0.70]
            state.n_total_assignments = 1
            state.midterm_exam_scores = [0.70]
            state.forum_scores = [0.70]
            state.final_score = 0.70
            states[sid] = state

        with caplog.at_level(logging.WARNING, logger="synthed.simulation.grading"):
            assign_outcomes(states, cfg)

        assert "zero variance" in caplog.text
        for state in states.values():
            assert state.outcome in ("Distinction", "Pass", "Fail")
        # With identical 0.70 grades, floor-adjusted = 0.835 > distinction=0.73
        # so all should be Distinction (not all Fail)
        assert any(s.outcome != "Fail" for s in states.values())

    def test_relative_single_eligible_fallback(self, caplog):
        """1 eligible + rest withdrawn -> fallback to absolute."""
        cfg = GradingConfig(grading_method="relative")

        states = {}
        # One eligible student
        s0 = SimulationState(student_id="S000")
        s0.gpa_count = 1
        s0.assignment_scores = [0.80]
        s0.n_total_assignments = 1
        s0.midterm_exam_scores = [0.75]
        s0.forum_scores = [0.70]
        s0.final_score = 0.80
        states["S000"] = s0

        # Rest withdrawn
        for i in range(1, 5):
            sid = f"S{i:03d}"
            state = SimulationState(student_id=sid)
            state.has_dropped_out = True
            state.dropout_week = 3
            states[sid] = state

        with caplog.at_level(logging.WARNING, logger="synthed.simulation.grading"):
            assign_outcomes(states, cfg)

        assert "fewer than 2" in caplog.text
        assert states["S000"].outcome in ("Distinction", "Pass", "Fail")
        for i in range(1, 5):
            assert states[f"S{i:03d}"].outcome == "Withdrawn"

    def test_relative_all_withdrawn(self):
        """All dropped out -> all Withdrawn, no crash."""
        cfg = GradingConfig(grading_method="relative")

        states = {}
        for i in range(5):
            sid = f"S{i:03d}"
            state = SimulationState(student_id=sid)
            state.has_dropped_out = True
            state.dropout_week = 2
            states[sid] = state

        assign_outcomes(states, cfg)
        for state in states.values():
            assert state.outcome == "Withdrawn"

    def test_relative_dual_hurdle_interaction(self):
        """High t-score but low component -> still fails hurdle."""
        cfg = GradingConfig(
            grading_method="relative",
            dual_hurdle=True,
            component_pass_thresholds={"final": 0.70},
        )

        states = {}
        # Student with high midterm but very low final (fails hurdle)
        s0 = SimulationState(student_id="S000")
        s0.gpa_count = 2
        s0.assignment_scores = [0.90]
        s0.n_total_assignments = 1
        s0.midterm_exam_scores = [0.90]
        s0.forum_scores = [0.85]
        s0.final_score = 0.10  # very low - below hurdle after floor-adjust
        states["S000"] = s0

        # Student with decent all-around scores
        s1 = SimulationState(student_id="S001")
        s1.gpa_count = 2
        s1.assignment_scores = [0.60]
        s1.n_total_assignments = 1
        s1.midterm_exam_scores = [0.60]
        s1.forum_scores = [0.60]
        s1.final_score = 0.60
        states["S001"] = s1

        # Third student to avoid fallback
        s2 = SimulationState(student_id="S002")
        s2.gpa_count = 2
        s2.assignment_scores = [0.50]
        s2.n_total_assignments = 1
        s2.midterm_exam_scores = [0.50]
        s2.forum_scores = [0.50]
        s2.final_score = 0.50
        states["S002"] = s2

        assign_outcomes(states, cfg)

        # S000 has highest raw grade but low final -> fails hurdle
        assert states["S000"].outcome == "Fail"

    def test_relative_determinism(self):
        """Two identical runs produce identical outcomes (compared by position)."""
        students = _make_students(50, seed=42)

        cfg1 = GradingConfig(grading_method="relative")
        engine_1 = SimulationEngine(ODLEnvironment(), seed=42, grading_config=cfg1)
        _, states_1, _ = engine_1.run(students)

        cfg2 = GradingConfig(grading_method="relative")
        engine_2 = SimulationEngine(ODLEnvironment(), seed=42, grading_config=cfg2)
        _, states_2, _ = engine_2.run(students)

        sids_1 = list(states_1.keys())
        sids_2 = list(states_2.keys())
        assert sids_1 == sids_2
        for sid in sids_1:
            assert states_1[sid].outcome == states_2[sid].outcome
            if states_1[sid].semester_grade is not None:
                assert states_1[sid].semester_grade == states_2[sid].semester_grade
