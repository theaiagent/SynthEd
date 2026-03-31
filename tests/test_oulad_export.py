"""Tests for OULAD-compatible export."""

import csv
from pathlib import Path

import pytest

from synthed.agents.factory import StudentFactory
from synthed.simulation.engine import SimulationEngine
from synthed.simulation.environment import ODLEnvironment
from synthed.data_output.oulad_exporter import OuladExporter
from synthed.data_output.oulad_mappings import (
    semester_to_presentation, age_to_band, gender_to_oulad,
    education_to_oulad, map_final_result, map_activity_type,
    click_heuristic, student_id_to_int,
    COURSES_COLUMNS, ASSESSMENTS_COLUMNS,
    STUDENT_INFO_COLUMNS, STUDENT_VLE_COLUMNS,
)


# ─────────────────────────────────────────────
# Mapping function tests
# ─────────────────────────────────────────────

class TestSemesterToPresentation:
    def test_fall_to_j(self):
        assert semester_to_presentation("Fall 2026") == "2026J"

    def test_spring_to_b(self):
        assert semester_to_presentation("Spring 2026") == "2026B"

    def test_summer_to_b(self):
        assert semester_to_presentation("Summer 2026") == "2026B"


class TestAgeToBand:
    def test_young(self):
        assert age_to_band(20) == "0-35"

    def test_middle(self):
        assert age_to_band(40) == "35-55"

    def test_older(self):
        assert age_to_band(60) == "55<="

    def test_boundary_35(self):
        assert age_to_band(34) == "0-35"
        assert age_to_band(35) == "35-55"


class TestGenderMapping:
    def test_male(self):
        assert gender_to_oulad("male") == "M"

    def test_female(self):
        assert gender_to_oulad("female") == "F"


class TestEducationMapping:
    def test_all_levels(self):
        assert education_to_oulad("high_school") == "A Level or Equivalent"
        assert education_to_oulad("associate") == "Lower Than A Level"
        assert education_to_oulad("bachelor") == "HE Qualification"


class TestFinalResult:
    def test_withdrawn(self):
        assert map_final_result(True, None, 3.0, 5) == "Withdrawn"

    def test_withdrawn_reason(self):
        assert map_final_result(False, "serious_illness", 3.0, 5) == "Withdrawn"

    def test_distinction(self):
        assert map_final_result(False, None, 3.5, 5) == "Distinction"

    def test_pass(self):
        assert map_final_result(False, None, 2.5, 5) == "Pass"

    def test_fail(self):
        assert map_final_result(False, None, 1.0, 5) == "Fail"

    def test_no_grades_defaults_pass(self):
        assert map_final_result(False, None, 0.0, 0) == "Pass"


class TestActivityTypeMapping:
    def test_graded_returns_none(self):
        assert map_activity_type("assignment_submit") is None
        assert map_activity_type("exam") is None

    def test_login(self):
        assert map_activity_type("lms_login") == "homepage"

    def test_forum(self):
        assert map_activity_type("forum_read") == "forumng"
        assert map_activity_type("forum_post") == "forumng"


class TestClickHeuristic:
    def test_login_is_one(self):
        assert click_heuristic("lms_login", 0, {}) == 1

    def test_forum_post_scales(self):
        assert click_heuristic("forum_post", 0, {"post_length": 100}) == 5

    def test_minimum_one(self):
        assert click_heuristic("forum_read", 0, {}) >= 1


class TestStudentIdToInt:
    def test_standard_format(self):
        assert student_id_to_int("S-0001") == 1
        assert student_id_to_int("S-0042") == 42

    def test_invalid_returns_zero(self):
        assert student_id_to_int("") == 0


# ─────────────────────────────────────────────
# Integration tests
# ─────────────────────────────────────────────

class TestOuladExportIntegration:
    """Full pipeline OULAD export tests."""

    @pytest.fixture
    def oulad_output(self, tmp_path):
        """Run a small pipeline and export OULAD tables."""
        env = ODLEnvironment()
        factory = StudentFactory(seed=42)
        students = factory.generate_population(n=15)
        engine = SimulationEngine(environment=env, seed=42)
        records, states, network = engine.run(students)

        exporter = OuladExporter(str(tmp_path), seed=42)
        paths = exporter.export_all(students, records, states, env)
        return tmp_path / "oulad", paths, students, states, env

    def test_produces_7_files(self, oulad_output):
        oulad_dir, paths, _, _, _ = oulad_output
        assert len(paths) == 7
        for name in ["courses", "assessments", "vle", "studentInfo",
                      "studentRegistration", "studentAssessment", "studentVle"]:
            assert name in paths
            assert Path(paths[name]).exists()

    def test_courses_header(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "courses.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == COURSES_COLUMNS

    def test_assessments_header(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "assessments.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == ASSESSMENTS_COLUMNS

    def test_student_info_header(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "studentInfo.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == STUDENT_INFO_COLUMNS

    def test_student_vle_header(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "studentVle.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames) == STUDENT_VLE_COLUMNS

    def test_student_info_row_count(self, oulad_output):
        """Each student has one row per course in studentInfo."""
        oulad_dir, _, students, _, env = oulad_output
        with open(oulad_dir / "studentInfo.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        # students * courses (some may be missing if state is None)
        assert len(rows) > 0
        assert len(rows) <= len(students) * len(env.courses)

    def test_final_result_vocabulary(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "studentInfo.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        valid = {"Pass", "Fail", "Withdrawn", "Distinction"}
        for row in rows:
            assert row["final_result"] in valid

    def test_score_range(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "studentAssessment.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            score = int(row["score"])
            assert 0 <= score <= 100

    def test_disability_column_values(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "studentInfo.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            assert row["disability"] in ("Y", "N")

    def test_gender_values(self, oulad_output):
        oulad_dir, _, _, _, _ = oulad_output
        with open(oulad_dir / "studentInfo.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            assert row["gender"] in ("M", "F")

    def test_deterministic_output(self, tmp_path):
        """Same seed produces identical output."""
        env = ODLEnvironment()
        factory = StudentFactory(seed=42)
        students = factory.generate_population(n=10)
        engine = SimulationEngine(environment=env, seed=42)
        records, states, _ = engine.run(students)

        dir1 = tmp_path / "run1"
        dir2 = tmp_path / "run2"
        OuladExporter(str(dir1), seed=42).export_all(students, records, states, env)
        OuladExporter(str(dir2), seed=42).export_all(students, records, states, env)

        for fname in ["courses.csv", "assessments.csv", "studentAssessment.csv"]:
            content1 = (dir1 / "oulad" / fname).read_text()
            content2 = (dir2 / "oulad" / fname).read_text()
            assert content1 == content2, f"{fname} differs between runs"
