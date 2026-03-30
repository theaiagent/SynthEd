"""Tests for SyntheticDataValidator."""

from synthed.validation.validator import SyntheticDataValidator, ReferenceStatistics


class TestSyntheticDataValidator:
    def test_validate_all_returns_report_structure(self):
        validator = SyntheticDataValidator()
        students = [
            {"student_id": f"s{i}", "age": 25 + i, "gender": "female",
             "is_employed": i % 2 == 0, "prior_gpa": 2.5,
             "socioeconomic_level": "middle"}
            for i in range(30)
        ]
        outcomes = [
            {"student_id": f"s{i}", "has_dropped_out": i < 10,
             "dropout_week": 5 if i < 10 else None,
             "final_dropout_phase": 5 if i < 10 else 0,
             "final_engagement": 0.3 if i < 10 else 0.7}
            for i in range(30)
        ]
        report = validator.validate_all(students, outcomes)
        assert "summary" in report
        assert "results" in report
        assert "total_tests" in report["summary"]
        assert "passed" in report["summary"]
        assert "overall_quality" in report["summary"]

    def test_proportion_z_test_symmetric(self):
        z1, p1 = SyntheticDataValidator._proportion_z_test(0.55, 0.50, 100)
        z2, p2 = SyntheticDataValidator._proportion_z_test(0.45, 0.50, 100)
        assert abs(abs(z1) - abs(z2)) < 1e-6
        assert abs(p1 - p2) < 1e-6

    def test_quality_grade_thresholds(self):
        assert "A" in SyntheticDataValidator._quality_grade(0.95)
        assert "B" in SyntheticDataValidator._quality_grade(0.80)
        assert "C" in SyntheticDataValidator._quality_grade(0.65)
        assert "D" in SyntheticDataValidator._quality_grade(0.45)
        assert "F" in SyntheticDataValidator._quality_grade(0.20)
