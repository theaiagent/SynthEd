"""Targeted tests to boost coverage from 93% to 95%+.

Covers uncovered lines in:
- validator.py: from_json, backstory validation, SDT/Bäulke branches
- pipeline.py: multi-semester branch, missing state branch, LLM cost report
- exporter.py: missing state branches
- environment.py: semester name branches (Summer, Spring)
- baulke.py: phase 2→3, phase 4 recovery, additional transitions
- positive_events.py: unknown event name
"""

import datetime
import json
from unittest.mock import patch, MagicMock

import numpy as np

from synthed.agents.persona import StudentPersona
from synthed.data_output.exporter import DataExporter
from synthed.pipeline import SynthEdPipeline
from synthed.simulation.engine import (
    SimulationState,
    CommunityOfInquiryState,
)
from synthed.simulation.environment import ODLEnvironment, _default_semester_name
from synthed.simulation.theories.baulke import BaulkeDropoutPhase
from synthed.simulation.theories.positive_events import PositiveEventHandler
from synthed.simulation.theories.academic_exhaustion import ExhaustionState
from synthed.validation.validator import (
    ReferenceStatistics,
    SyntheticDataValidator,
)


def _constant_td(s, st):
    """Helper returning constant transactional distance for Bäulke tests."""
    return 0.5


# ── ReferenceStatistics.from_json ──────────────────────────────────────


class TestReferenceStatisticsFromJson:
    def test_from_json_loads_custom_values(self, tmp_path):
        data = {"age_mean": 30.0, "age_std": 5.0, "dropout_rate": 0.40}
        filepath = tmp_path / "ref.json"
        filepath.write_text(json.dumps(data))
        ref = ReferenceStatistics.from_json(str(filepath))
        assert ref.age_mean == 30.0
        assert ref.age_std == 5.0
        assert ref.dropout_rate == 0.40
        # defaults preserved
        assert ref.employment_rate == 0.78


# ── Validator: backstory validation ────────────────────────────────────


class TestValidatorBackstories:
    def test_backstory_validation_with_backstories(self):
        validator = SyntheticDataValidator()
        students = [
            {
                "student_id": f"s{i}",
                "age": 25 + i,
                "gender": "female",
                "is_employed": True,
                "has_family_responsibilities": True,
                "prior_gpa": 2.5,
                "motivation_type": "intrinsic",
                "socioeconomic_level": "middle",
                "backstory": "She has passion for learning and works part-time at a job while caring for family."
                if i < 8
                else "A student enrolled in the program.",
            }
            for i in range(10)
        ]
        outcomes = [
            {
                "student_id": f"s{i}",
                "has_dropped_out": False,
                "final_engagement": 0.6,
                "final_dropout_phase": 0,
            }
            for i in range(10)
        ]
        report = validator.validate_all(students, outcomes)
        test_names = [r["test"] for r in report["results"]]
        assert "backstory_non_empty_rate" in test_names
        assert "backstory_attribute_relevance" in test_names

    def test_backstory_validation_skipped_when_no_backstories(self):
        validator = SyntheticDataValidator()
        students = [
            {
                "student_id": f"s{i}",
                "age": 25,
                "gender": "male",
                "is_employed": False,
                "prior_gpa": 2.5,
                "socioeconomic_level": "low",
            }
            for i in range(10)
        ]
        outcomes = [
            {
                "student_id": f"s{i}",
                "has_dropped_out": False,
                "final_engagement": 0.5,
                "final_dropout_phase": 0,
            }
            for i in range(10)
        ]
        report = validator.validate_all(students, outcomes)
        test_names = [r["test"] for r in report["results"]]
        assert "backstory_non_empty_rate" not in test_names

    def test_backstory_motivation_extrinsic_keywords(self):
        validator = SyntheticDataValidator()
        students = [
            {
                "student_id": f"s{i}",
                "age": 30,
                "gender": "male",
                "is_employed": False,
                "has_family_responsibilities": False,
                "prior_gpa": 3.0,
                "motivation_type": "extrinsic",
                "socioeconomic_level": "high",
                "backstory": "Looking for a career advancement and promotion opportunity.",
            }
            for i in range(10)
        ]
        outcomes = [
            {
                "student_id": f"s{i}",
                "has_dropped_out": False,
                "final_engagement": 0.7,
                "final_dropout_phase": 0,
            }
            for i in range(10)
        ]
        report = validator.validate_all(students, outcomes)
        test_names = [r["test"] for r in report["results"]]
        assert "backstory_attribute_relevance" in test_names

    def test_backstory_amotivation_keywords(self):
        validator = SyntheticDataValidator()
        students = [
            {
                "student_id": f"s{i}",
                "age": 25,
                "gender": "female",
                "is_employed": False,
                "has_family_responsibilities": False,
                "prior_gpa": 2.0,
                "motivation_type": "amotivation",
                "socioeconomic_level": "low",
                "backstory": "Enrolled under pressure from family expectations, uncertain about the degree.",
            }
            for i in range(10)
        ]
        outcomes = [
            {
                "student_id": f"s{i}",
                "has_dropped_out": False,
                "final_engagement": 0.4,
                "final_dropout_phase": 0,
            }
            for i in range(10)
        ]
        report = validator.validate_all(students, outcomes)
        relevance = next(
            r for r in report["results"] if r["test"] == "backstory_attribute_relevance"
        )
        assert relevance["passed"]


# ── Validator: SDT intrinsic vs amotivation branch ────────────────────


class TestValidatorSDTBranch:
    def test_sdt_intrinsic_vs_amotivation(self):
        validator = SyntheticDataValidator()
        students = []
        outcomes = []
        for i in range(20):
            mot = "intrinsic" if i < 10 else "amotivation"
            eng = 0.8 if i < 10 else 0.3
            students.append({
                "student_id": f"s{i}",
                "age": 25,
                "gender": "female",
                "is_employed": False,
                "prior_gpa": 2.5,
                "socioeconomic_level": "middle",
                "motivation_type": mot,
                "conscientiousness": 0.5,
                "self_efficacy": 0.5,
                "self_regulation": 0.5,
                "financial_stress": 0.3,
                "goal_commitment": 0.5,
                "learner_autonomy": 0.5,
            })
            outcomes.append({
                "student_id": f"s{i}",
                "has_dropped_out": i >= 15,
                "final_engagement": eng,
                "final_dropout_phase": 5 if i >= 15 else 0,
                "coi_composite": 0.5,
                "network_degree": 3,
                "perceived_cost_benefit": 0.5,
            })
        report = validator.validate_all(students, outcomes)
        test_names = [r["test"] for r in report["results"]]
        assert "sdt_intrinsic_vs_amotivation" in test_names

    def test_baulke_phase_distribution_in_validation(self):
        validator = SyntheticDataValidator()
        students = [
            {
                "student_id": f"s{i}",
                "age": 25,
                "gender": "female",
                "is_employed": False,
                "prior_gpa": 2.5,
                "socioeconomic_level": "middle",
            }
            for i in range(20)
        ]
        outcomes = [
            {
                "student_id": f"s{i}",
                "has_dropped_out": i < 5,
                "final_engagement": 0.3 if i < 5 else 0.7,
                "final_dropout_phase": 5 if i < 5 else 0,
            }
            for i in range(20)
        ]
        report = validator.validate_all(students, outcomes)
        test_names = [r["test"] for r in report["results"]]
        assert "baulke_phase_distribution" in test_names


# ── Validator: proportion z-test edge cases ────────────────────────────


class TestProportionZTestEdges:
    def test_zero_n(self):
        z, p = SyntheticDataValidator._proportion_z_test(0.5, 0.5, 0)
        assert z == 0.0
        assert p == 1.0

    def test_p_expected_zero(self):
        z, p = SyntheticDataValidator._proportion_z_test(0.5, 0.0, 100)
        assert z == 0.0
        assert p == 1.0

    def test_p_expected_one(self):
        z, p = SyntheticDataValidator._proportion_z_test(0.5, 1.0, 100)
        assert z == 0.0
        assert p == 1.0


# ── Environment: semester name branches ────────────────────────────────


class TestEnvironmentSemesterName:
    def test_spring_semester_name(self):
        with patch("synthed.simulation.environment.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 3, 15)
            name = _default_semester_name()
            assert "Spring" in name

    def test_summer_semester_name(self):
        with patch("synthed.simulation.environment.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 7, 1)
            name = _default_semester_name()
            assert "Summer" in name

    def test_fall_semester_name(self):
        with patch("synthed.simulation.environment.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2026, 9, 1)
            name = _default_semester_name()
            assert "Fall" in name

    def test_environment_with_custom_courses(self):
        """Cover the branch where courses are provided (no defaults)."""
        from synthed.simulation.environment import Course

        custom_course = Course(id="TEST101", name="Test", difficulty=0.5)
        env = ODLEnvironment(courses=[custom_course])
        assert len(env.courses) == 1
        assert env.courses[0].id == "TEST101"

    def test_environment_with_custom_events(self):
        """Cover the branch where scheduled_events are provided."""
        env = ODLEnvironment(
            scheduled_events={1: "custom_start"},
            positive_events={1: "custom_positive"},
        )
        assert env.scheduled_events == {1: "custom_start"}
        assert env.positive_events == {1: "custom_positive"}


# ── Bäulke: uncovered phase transitions ───────────────────────────────


class TestBaulkeUncoveredTransitions:
    def _make_state(self, **kwargs):
        defaults = dict(
            student_id="test",
            current_engagement=0.5,
            dropout_phase=0,
            weekly_engagement_history=[0.5],
            missed_assignments_streak=0,
            social_integration=0.3,
            perceived_cost_benefit=0.6,
            coi_state=CommunityOfInquiryState(),
            exhaustion=ExhaustionState(),
            memory=[],
        )
        defaults.update(kwargs)
        return SimulationState(**defaults)

    def _make_student(self, **kwargs):
        defaults = dict(
            name="Test",
            age=25,
            gender="female",
            financial_stress=0.3,
        )
        defaults.update(kwargs)
        return StudentPersona(**defaults)

    def test_phase_2_to_3_requires_sustained_decline(self):
        """Cover lines 118-119: phase 2 -> 3 transition."""
        baulke = BaulkeDropoutPhase()
        state = self._make_state(
            dropout_phase=2,
            current_engagement=0.30,
            weekly_engagement_history=[0.35, 0.32, 0.30],
        )
        student = self._make_student()
        env = ODLEnvironment()
        rng = np.random.default_rng(42)

        baulke.advance_phase(student, state, 5, env, _constant_td, rng)
        assert state.dropout_phase == 3

    def test_phase_2_recovery_to_1(self):
        """Cover lines 117-121: phase 2 recovery."""
        baulke = BaulkeDropoutPhase()
        state = self._make_state(
            dropout_phase=2,
            current_engagement=0.50,
        )
        student = self._make_student()
        env = ODLEnvironment()
        rng = np.random.default_rng(42)

        baulke.advance_phase(student, state, 5, env, _constant_td, rng)
        assert state.dropout_phase == 1

    def test_phase_3_to_4_transition(self):
        """Cover lines 132-133: phase 3 -> 4 transition."""
        baulke = BaulkeDropoutPhase()
        state = self._make_state(
            dropout_phase=3,
            current_engagement=0.20,
            perceived_cost_benefit=0.30,
        )
        student = self._make_student()
        env = ODLEnvironment()
        rng = np.random.default_rng(42)

        baulke.advance_phase(student, state, 5, env, _constant_td, rng)
        assert state.dropout_phase == 4

    def test_phase_4_recovery_to_3(self):
        """Cover line 147: phase 4 recovery back to 3."""
        baulke = BaulkeDropoutPhase()
        state = self._make_state(
            dropout_phase=4,
            current_engagement=0.40,
            perceived_cost_benefit=0.50,
        )
        student = self._make_student()
        env = ODLEnvironment()
        rng = np.random.default_rng(42)

        baulke.advance_phase(student, state, 5, env, _constant_td, rng)
        assert state.dropout_phase == 3

    def test_phase_3_recovery_to_2(self):
        """Cover phase 3 recovery."""
        baulke = BaulkeDropoutPhase()
        state = self._make_state(
            dropout_phase=3,
            current_engagement=0.45,
        )
        student = self._make_student()
        env = ODLEnvironment()
        rng = np.random.default_rng(42)

        baulke.advance_phase(student, state, 5, env, _constant_td, rng)
        assert state.dropout_phase == 2


# ── Exporter: missing state branches ──────────────────────────────────


class TestExporterMissingStates:
    def test_export_outcomes_skips_missing_state(self, tmp_path):
        exporter = DataExporter(output_dir=str(tmp_path))
        student = StudentPersona(name="Test", age=25, gender="male")
        # states dict does NOT contain this student
        exporter.export_outcomes([student], {}, network=None)
        content = (tmp_path / "outcomes.csv").read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1  # header only

    def test_export_weekly_engagement_skips_missing_state(self, tmp_path):
        exporter = DataExporter(output_dir=str(tmp_path))
        student = StudentPersona(name="Test", age=25, gender="male")
        exporter.export_weekly_engagement([student], {})
        content = (tmp_path / "weekly_engagement.csv").read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1  # header only


# ── Pipeline: multi-semester and LLM cost branches ────────────────────


class TestPipelineMultiSemester:
    def test_multi_semester_run(self, tmp_path):
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            n_semesters=2,
        )
        report = pipeline.run(n_students=20)
        assert "simulation_summary" in report
        assert report["config"]["n_students"] == 20

    def test_pipeline_with_llm_cost_report(self, tmp_path):
        """Cover line 222: LLM cost report branch."""
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            use_llm=False,
        )
        # Manually set a mock LLM to trigger cost report
        mock_llm = MagicMock()
        mock_llm.cost_report.return_value = {"total_cost": 0.0}
        pipeline.llm = mock_llm
        report = pipeline.run(n_students=20)
        assert "llm_costs" in report
        assert report["llm_costs"]["total_cost"] == 0.0


# ── Pipeline: missing state in validation data prep ───────────────────


class TestPipelineMissingStateInValidation:
    def test_pipeline_report_saved(self, tmp_path):
        """Cover line 217: report_path write."""
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        report = pipeline.run(n_students=20)
        assert "report_path" in report
        assert (tmp_path / "pipeline_report.json").exists()


# ── Positive events: unknown event name ───────────────────────────────


class TestPositiveEventUnknown:
    def test_unknown_event_returns_zero(self):
        handler = PositiveEventHandler()
        state = SimulationState(student_id="test")
        student = StudentPersona(name="Test", age=25, gender="male")
        boost = handler.apply("nonexistent_event", student, state)
        assert boost == 0.0


# ── __init__.py: setuptools_scm fallback (lines 16-17) ──────────────


class TestVersionFallback:
    def test_version_fallback_to_dev(self):
        """When both importlib.metadata and setuptools_scm fail, version is 0.0.0-dev (lines 16-17)."""
        import importlib
        import synthed

        def bad_version(name):
            raise Exception("no metadata")

        def bad_get_version(**kwargs):
            raise Exception("no setuptools_scm")

        with patch("importlib.metadata.version", side_effect=bad_version):
            with patch.dict("sys.modules", {"setuptools_scm": MagicMock(get_version=bad_get_version)}):
                importlib.reload(synthed)
                assert synthed.__version__ == "0.0.0-dev"

        # Reload to restore real version
        importlib.reload(synthed)

    def test_version_is_string(self):
        """__version__ should always be a string."""
        import synthed
        assert isinstance(synthed.__version__, str)
        assert len(synthed.__version__) > 0


# ── Exporter: short engagement history trend (line 185) ──────────────


class TestExporterShortHistory:
    def test_export_outcomes_short_history_unknown_trend(self, tmp_path):
        """Engagement history < 4 weeks produces 'unknown' trend (line 185)."""
        import csv

        exporter = DataExporter(output_dir=str(tmp_path))
        student = StudentPersona(name="Test", age=25, gender="male")
        state = SimulationState(
            student_id=student.id,
            weekly_engagement_history=[0.5, 0.6],  # only 2 weeks
        )
        states = {student.id: state}

        from synthed.simulation.social_network import SocialNetwork
        network = SocialNetwork()
        exporter.export_outcomes([student], states, network=network)

        with open(tmp_path / "outcomes.csv", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["engagement_trend"] == "unknown"


# ── Calibration: insufficient data (line 101) ───────────────────────


class TestCalibrationInsufficientData:
    def test_insufficient_calibration_data_raises(self):
        """CalibrationMap with < 2 points raises ValueError (line 101)."""
        import pytest
        from synthed.calibration import CalibrationMap, CalibrationPoint

        # Only 1 data point for n_semesters=1, and nothing else
        sparse_data = (
            CalibrationPoint(1, 0.50, 0.40, 100, 1),
        )
        cal = CalibrationMap(data=sparse_data)
        # n_semesters=3 has no data, falls back to 1-sem which has only 1 point
        with pytest.raises(ValueError, match="Insufficient calibration data"):
            cal.estimate(0.40, n_semesters=3)


# ── Academic exhaustion: dropout threshold (line 113) ────────────────


class TestExhaustionDropoutThreshold:
    def test_exhaustion_accelerates_dropout_true(self):
        """exhaustion_accelerates_dropout returns True when above threshold (line 113)."""
        from synthed.simulation.theories.academic_exhaustion import (
            GonzalezExhaustion,
        )

        exhaustion = GonzalezExhaustion()
        state = SimulationState(
            student_id="test",
            exhaustion=ExhaustionState(exhaustion_level=0.80),
        )
        assert exhaustion.exhaustion_accelerates_dropout(state) is True

    def test_exhaustion_does_not_accelerate_dropout_when_low(self):
        from synthed.simulation.theories.academic_exhaustion import (
            GonzalezExhaustion,
        )

        exhaustion = GonzalezExhaustion()
        state = SimulationState(
            student_id="test",
            exhaustion=ExhaustionState(exhaustion_level=0.30),
        )
        assert exhaustion.exhaustion_accelerates_dropout(state) is False


# ── Unavoidable withdrawal: edge cases (lines 57, 92) ───────────────


class TestUnavoidableWithdrawalEdgeCases:
    def test_event_weights_validation_error(self):
        """_EVENT_WEIGHTS sum != 1.0 would raise (line 57)."""
        import pytest
        from synthed.simulation.theories.unavoidable_withdrawal import (
            UnavoidableWithdrawal,
        )

        # Monkey-patch to test the validation
        original_weights = UnavoidableWithdrawal._EVENT_WEIGHTS.copy()
        try:
            UnavoidableWithdrawal._EVENT_WEIGHTS = {"event1": 0.5}  # doesn't sum to 1.0
            with pytest.raises(ValueError, match="sum to 1.0"):
                UnavoidableWithdrawal(per_semester_probability=0.1, total_weeks=14)
        finally:
            UnavoidableWithdrawal._EVENT_WEIGHTS = original_weights

    def test_already_dropped_out_returns_false(self):
        """check_withdrawal returns False if student already dropped out (line 92)."""
        from synthed.simulation.theories.unavoidable_withdrawal import (
            UnavoidableWithdrawal,
        )

        uw = UnavoidableWithdrawal(per_semester_probability=1.0, total_weeks=14)
        student = StudentPersona()
        rng = np.random.default_rng(42)
        state = SimulationState(
            student_id="test",
            has_dropped_out=True,
            dropout_week=3,
        )
        result = uw.check_withdrawal(student, state, 5, rng)
        assert result is False


# ── Validator: dropout_range validation (line 51) ────────────────────


class TestReferenceStatisticsDropoutRange:
    def test_invalid_dropout_range_raises(self):
        """dropout_range that doesn't satisfy 0 < lo < hi < 1 raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="dropout_range"):
            ReferenceStatistics(dropout_range=(0.5, 0.3))  # lo > hi

        with pytest.raises(ValueError, match="dropout_range"):
            ReferenceStatistics(dropout_range=(0.0, 0.5))  # lo must be > 0

        with pytest.raises(ValueError, match="dropout_range"):
            ReferenceStatistics(dropout_range=(0.5, 1.0))  # hi must be < 1


# ── Validator: CoI and network correlations (lines 396-397, 409-410) ─


class TestValidatorCorrelations:
    def test_coi_and_network_correlations(self):
        """Validate CoI composite and network degree correlations are computed."""
        validator = SyntheticDataValidator()
        students = []
        outcomes = []
        for i in range(30):
            # _get_pairs looks for attr_key in student dicts, outcome_key in outcome dicts
            # coi_composite and network_degree must be in student data for _get_pairs to find them
            students.append({
                "student_id": f"s{i}",
                "age": 25 + i % 10,
                "gender": "female" if i % 2 == 0 else "male",
                "is_employed": i % 3 == 0,
                "prior_gpa": 2.0 + (i % 10) * 0.2,
                "socioeconomic_level": "middle",
                "conscientiousness": 0.3 + (i / 30) * 0.4,
                "self_efficacy": 0.3 + (i / 30) * 0.4,
                "self_regulation": 0.3 + (i / 30) * 0.4,
                "financial_stress": 0.3,
                "goal_commitment": 0.5,
                "learner_autonomy": 0.3 + (i / 30) * 0.4,
                "coi_composite": 0.2 + (i / 30) * 0.6,
                "network_degree": 1 + i,
            })
            eng = 0.3 + (i / 30) * 0.5
            outcomes.append({
                "student_id": f"s{i}",
                "has_dropped_out": i < 5,
                "dropout_week": 3 if i < 5 else None,
                "final_engagement": eng,
                "final_dropout_phase": 5 if i < 5 else 0,
                "perceived_cost_benefit": 0.5,
            })
        report = validator.validate_all(students, outcomes)
        test_names = [r["test"] for r in report["results"]]
        # Lines 396-397: garrison_coi_engagement should be computed
        assert "garrison_coi_engagement" in test_names
        # Lines 409-410: epstein_network_degree_engagement should be computed
        assert "epstein_network_degree_engagement" in test_names


# ── Validator: _proportion_z_test se=0 edge case (line 646) ──────────


class TestProportionZTestSE0:
    def test_se_zero_returns_defaults(self):
        """When se=0 (defensive guard), return (0.0, 1.0) (line 646).

        This guard is unreachable under normal math (p*(1-p)/n > 0 when
        0 < p < 1 and n > 0), but exists for floating-point safety.
        We force it via monkeypatching np.sqrt to return 0.
        """
        import synthed.validation.validator as vmod
        original_sqrt = np.sqrt

        def zero_sqrt(x):
            return np.float64(0.0)

        vmod.np.sqrt = zero_sqrt
        try:
            z, p = SyntheticDataValidator._proportion_z_test(0.5, 0.5, 100)
            assert z == 0.0
            assert p == 1.0
        finally:
            vmod.np.sqrt = original_sqrt
