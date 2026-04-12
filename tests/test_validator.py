"""Tests for SyntheticDataValidator."""

from synthed.validation import SyntheticDataValidator, ReferenceStatistics


class TestSyntheticDataValidator:
    def setup_method(self):
        self.validator = SyntheticDataValidator()

    def test_validate_all_returns_report_structure(self):
        validator = SyntheticDataValidator()
        students = [
            {"student_id": f"s{i}", "age": 25 + i, "gender": "female",
             "employment_intensity": 0.67 if i % 2 == 0 else 0.0, "prior_gpa": 2.5,
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

    def test_effective_alpha_small_n_unchanged(self):
        assert self.validator._effective_alpha(200) == 0.05
        assert self.validator._effective_alpha(500) == 0.05

    def test_effective_alpha_large_n_decreases(self):
        alpha_10k = self.validator._effective_alpha(10000)
        assert alpha_10k < 0.05
        assert abs(alpha_10k - 0.01) < 0.005  # approximately 0.01

    def test_effective_alpha_minimum_bound(self):
        assert self.validator._effective_alpha(10_000_000) >= 0.001


class TestDropoutRangeValidation:
    """Tests for range-based dropout validation."""

    def _make_data(self, n=30, n_dropout=10):
        students = [
            {"student_id": f"s{i}", "age": 25 + i, "gender": "female",
             "employment_intensity": 0.67 if i % 2 == 0 else 0.0, "prior_gpa": 2.5,
             "socioeconomic_level": "middle"}
            for i in range(n)
        ]
        outcomes = [
            {"student_id": f"s{i}", "has_dropped_out": i < n_dropout,
             "dropout_week": 5 if i < n_dropout else None,
             "final_engagement": 0.3 if i < n_dropout else 0.7}
            for i in range(n)
        ]
        return students, outcomes

    def test_dropout_range_pass(self):
        """Observed dropout within range passes."""
        ref = ReferenceStatistics(dropout_range=(0.20, 0.50))
        v = SyntheticDataValidator(reference=ref)
        students, outcomes = self._make_data(n=30, n_dropout=10)  # ~33%
        report = v.validate_all(students, outcomes)
        dropout_result = next(
            r for r in report["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result["passed"] is True
        assert dropout_result["metric"] == "Range check"

    def test_dropout_range_fail(self):
        """Observed dropout outside range fails."""
        ref = ReferenceStatistics(dropout_range=(0.60, 0.80))
        v = SyntheticDataValidator(reference=ref)
        students, outcomes = self._make_data(n=30, n_dropout=10)  # ~33%
        report = v.validate_all(students, outcomes)
        dropout_result = next(
            r for r in report["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result["passed"] is False

    def test_dropout_range_backward_compat(self):
        """Default uses range check; explicit None uses z-test."""
        # Default now has dropout_range=(0.35, 0.55) → range check
        ref_default = ReferenceStatistics()
        v_default = SyntheticDataValidator(reference=ref_default)
        students, outcomes = self._make_data(n=30, n_dropout=10)
        report = v_default.validate_all(students, outcomes)
        dropout_result = next(
            r for r in report["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result["metric"] == "Range check"

        # Explicit dropout_range=None → z-test
        ref_ztest = ReferenceStatistics(dropout_range=None)
        v_ztest = SyntheticDataValidator(reference=ref_ztest)
        report2 = v_ztest.validate_all(students, outcomes)
        dropout_result2 = next(
            r for r in report2["results"] if r["test"] == "dropout_rate"
        )
        assert dropout_result2["metric"] == "Proportion Z-test"
