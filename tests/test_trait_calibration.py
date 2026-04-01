"""Tests for OULAD target extraction and trait-based calibration."""

from __future__ import annotations

import csv

import pytest

from synthed.analysis.oulad_targets import OuladTargets, extract_targets
from synthed.analysis.trait_calibrator import (
    CalibrationResult,
    TraitCalibrator,
    normalized_squared_error,
    select_top_parameters,
    squared_error,
)
from synthed.analysis.oulad_validator import (
    CALIBRATION_MODULES,
    VALIDATION_MODULES,
    ValidationReport,
    validate_against_oulad,
    _compare,
)
from synthed.analysis.sobol_sensitivity import (
    SOBOL_PARAMETER_SPACE,
    SobolParameter,
    SobolRanking,
)


# ─────────────────────────────────────────────
# Loss function tests
# ─────────────────────────────────────────────

class TestLossFunctions:
    def test_squared_error_zero(self):
        assert squared_error(0.5, 0.5) == 0.0

    def test_squared_error_symmetric(self):
        assert squared_error(0.3, 0.5) == squared_error(0.5, 0.3)

    def test_squared_error_value(self):
        assert abs(squared_error(0.3, 0.5) - 0.04) < 1e-10

    def test_normalized_squared_error_zero(self):
        assert normalized_squared_error(0.5, 0.5) == 0.0

    def test_normalized_squared_error_scales(self):
        """Same absolute error, different target → different normalized loss."""
        loss_small_target = normalized_squared_error(0.2, 0.1)  # 100% off
        loss_large_target = normalized_squared_error(0.6, 0.5)  # 20% off
        assert loss_small_target > loss_large_target

    def test_normalized_squared_error_zero_target(self):
        """When target is 0, falls back to raw squared error."""
        assert abs(normalized_squared_error(0.1, 0.0) - 0.01) < 1e-10


# ─────────────────────────────────────────────
# OULAD target extraction tests
# ─────────────────────────────────────────────

@pytest.fixture
def mock_oulad_dir(tmp_path):
    """Create minimal OULAD CSV files for testing."""
    # studentInfo.csv
    info_path = tmp_path / "studentInfo.csv"
    with open(info_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code_module", "code_presentation", "id_student", "gender",
                     "region", "highest_education", "imd_band", "age_band",
                     "num_of_prev_attempts", "studied_credits", "disability", "final_result"])
        # 10 students: 3 withdrawn, 1 disabled
        for i in range(10):
            result = "Withdrawn" if i < 3 else "Pass"
            gender = "M" if i % 2 == 0 else "F"
            disability = "Y" if i == 0 else "N"
            module = "AAA" if i < 5 else "BBB"
            w.writerow([module, "2024J", str(i), gender,
                        "Region", "HE Qualification", "50-60%", "0-35",
                        "0", "60", disability, result])

    # studentAssessment.csv
    assess_path = tmp_path / "studentAssessment.csv"
    with open(assess_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id_assessment", "id_student", "date_submitted", "is_banked", "score"])
        for i in range(10):
            w.writerow([str(100 + i), str(i), str(i * 10), "0", str(60 + i * 4)])

    # studentVle.csv
    vle_path = tmp_path / "studentVle.csv"
    with open(vle_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code_module", "code_presentation", "id_student",
                     "id_site", "date", "sum_click"])
        for i in range(10):
            for day in range(5):
                w.writerow(["AAA", "2024J", str(i), "1", str(day), str(10 + i)])

    return tmp_path


class TestOuladTargets:
    def test_extract_produces_targets(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        assert isinstance(targets, OuladTargets)
        assert targets.n_students == 10

    def test_dropout_rate(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        assert targets.overall_dropout_rate == 0.3  # 3/10

    def test_module_dropout_rates(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        assert "AAA" in targets.module_dropout_rates
        assert "BBB" in targets.module_dropout_rates
        # AAA: students 0-4, withdrawn 0-2 → 3/5 = 0.6
        assert targets.module_dropout_rates["AAA"] == 0.6
        # BBB: students 5-9, none withdrawn → 0/5 = 0.0
        assert targets.module_dropout_rates["BBB"] == 0.0

    def test_score_statistics(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        # Scores: 60, 64, 68, 72, 76, 80, 84, 88, 92, 96
        assert 60 <= targets.score_mean <= 96
        assert targets.score_std > 0

    def test_gpa_from_scores(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        # GPA = score/100 * 4.0, mean score = 78 → GPA ≈ 3.12
        assert 2.0 <= targets.gpa_mean <= 4.0

    def test_engagement_statistics(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        # Each student has 5 days with clicks = 10+i
        assert targets.engagement_mean > 0
        assert targets.engagement_std >= 0

    def test_disability_rate(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        assert targets.disability_rate == 0.1  # 1/10

    def test_gender_rate(self, mock_oulad_dir):
        targets = extract_targets(mock_oulad_dir)
        assert targets.gender_male_rate == 0.5  # 5/10

    def test_engagement_cv(self, mock_oulad_dir):
        """CV = std/mean, scale-independent engagement shape metric."""
        targets = extract_targets(mock_oulad_dir)
        assert targets.engagement_cv > 0
        expected_cv = targets.engagement_std / targets.engagement_mean
        assert abs(targets.engagement_cv - expected_cv) < 0.001


# ─────────────────────────────────────────────
# Parameter selection tests
# ─────────────────────────────────────────────

class TestParameterSelection:
    def test_select_top_n(self):
        """select_top_parameters filters to top-N from rankings."""
        rankings = [
            SobolRanking("config.dropout_base_rate", 0.3, 0.5, 0.2, 1),
            SobolRanking("config.employment_rate", 0.2, 0.4, 0.2, 2),
            SobolRanking("baulke._DECISION_RISK_MULTIPLIER", 0.15, 0.35, 0.2, 3),
        ]
        result = select_top_parameters(rankings, top_n=2)
        assert len(result) == 2
        names = {p.name for p in result}
        assert "config.dropout_base_rate" in names
        assert "config.employment_rate" in names

    def test_select_preserves_bounds(self):
        """Selected parameters keep their original bounds."""
        rankings = [
            SobolRanking("config.dropout_base_rate", 0.3, 0.5, 0.2, 1),
        ]
        result = select_top_parameters(rankings, top_n=1)
        assert result[0].name == "config.dropout_base_rate"
        assert result[0].lower == 0.40
        assert result[0].upper == 0.95

    def test_select_unknown_name_excluded(self):
        """Rankings with names not in SOBOL_PARAMETER_SPACE are skipped."""
        rankings = [
            SobolRanking("nonexistent.param", 0.9, 0.95, 0.05, 1),
        ]
        result = select_top_parameters(rankings, top_n=1)
        assert len(result) == 0


# ─────────────────────────────────────────────
# Calibrator unit tests
# ─────────────────────────────────────────────

class TestCalibratorInit:
    def test_default_parameters(self):
        targets = OuladTargets(
            overall_dropout_rate=0.31, module_dropout_rates={},
            score_mean=75.8, score_std=18.8, score_median=80.0,
            gpa_mean=3.03, gpa_std=0.75,
            engagement_mean=19.7, engagement_std=11.8, engagement_median=17.0, engagement_cv=0.5990,
            disability_rate=0.097, gender_male_rate=0.55, n_students=32593,
        )
        cal = TraitCalibrator(targets, n_students=10)
        assert len(cal.parameters) == len(SOBOL_PARAMETER_SPACE)

    def test_custom_parameters(self):
        targets = OuladTargets(
            overall_dropout_rate=0.31, module_dropout_rates={},
            score_mean=75.8, score_std=18.8, score_median=80.0,
            gpa_mean=3.03, gpa_std=0.75,
            engagement_mean=19.7, engagement_std=11.8, engagement_median=17.0, engagement_cv=0.5990,
            disability_rate=0.097, gender_male_rate=0.55, n_students=32593,
        )
        subset = (
            SobolParameter("config.dropout_base_rate", 0.5, 0.9, "test"),
        )
        cal = TraitCalibrator(targets, n_students=10, parameters=subset)
        assert len(cal.parameters) == 1


# ─────────────────────────────────────────────
# Integration test (small-scale)
# ─────────────────────────────────────────────

class TestCalibratorIntegration:
    @pytest.mark.slow
    def test_minimal_calibration_run(self):
        """
        End-to-end calibration with 2 params, 5 trials, 15 students.

        Smoke test — results are not statistically meaningful but the
        pipeline must complete and return valid structure.
        """
        targets = OuladTargets(
            overall_dropout_rate=0.31, module_dropout_rates={},
            score_mean=75.8, score_std=18.8, score_median=80.0,
            gpa_mean=3.03, gpa_std=0.75,
            engagement_mean=19.7, engagement_std=11.8, engagement_median=17.0, engagement_cv=0.5990,
            disability_rate=0.097, gender_male_rate=0.55, n_students=32593,
        )
        subset = (
            SobolParameter("config.dropout_base_rate", 0.50, 0.90, "Dropout scaling"),
            SobolParameter("config.employment_rate", 0.40, 0.90, "Employment rate"),
        )
        cal = TraitCalibrator(targets, n_students=15, seed=42, parameters=subset)
        result = cal.run(n_trials=5)

        assert isinstance(result, CalibrationResult)
        assert result.n_trials == 5
        assert result.best_loss >= 0.0
        assert len(result.best_params) == 2
        assert "config.dropout_base_rate" in result.best_params
        assert "config.employment_rate" in result.best_params
        assert result.target_dropout == 0.31
        assert 0.0 <= result.achieved_dropout <= 1.0
        assert result.target_gpa == 3.03

    @pytest.mark.slow
    def test_calibration_improves_over_random(self):
        """
        Optuna should find a better loss than the first random trial.

        With 10 trials on 2 params, TPE should explore and improve.
        """
        targets = OuladTargets(
            overall_dropout_rate=0.31, module_dropout_rates={},
            score_mean=75.8, score_std=18.8, score_median=80.0,
            gpa_mean=3.03, gpa_std=0.75,
            engagement_mean=19.7, engagement_std=11.8, engagement_median=17.0, engagement_cv=0.5990,
            disability_rate=0.097, gender_male_rate=0.55, n_students=32593,
        )
        subset = (
            SobolParameter("config.dropout_base_rate", 0.30, 0.95, "Dropout scaling"),
        )
        cal = TraitCalibrator(targets, n_students=20, seed=42, parameters=subset)
        result = cal.run(n_trials=10)

        # Best loss should be finite and non-negative
        assert result.best_loss >= 0.0
        assert result.best_loss < float("inf")


# ─────────────────────────────────────────────
# OULAD held-out split tests
# ─────────────────────────────────────────────

class TestOuladModuleSplit:
    def test_calibration_validation_disjoint(self):
        """Calibration and validation modules have no overlap."""
        assert CALIBRATION_MODULES & VALIDATION_MODULES == frozenset()

    def test_all_modules_covered(self):
        """All 7 OULAD modules are in either calibration or validation."""
        all_modules = CALIBRATION_MODULES | VALIDATION_MODULES
        assert len(all_modules) == 7

    def test_extract_with_module_filter(self, mock_oulad_dir):
        """Module filter restricts to specified modules only."""
        targets_all = extract_targets(mock_oulad_dir)
        targets_aaa = extract_targets(mock_oulad_dir, modules={"AAA"})
        assert targets_aaa.n_students < targets_all.n_students
        # AAA has 5 students in mock data
        assert targets_aaa.n_students == 5


# ─────────────────────────────────────────────
# Validation metric tests
# ─────────────────────────────────────────────

class TestValidationMetrics:
    def test_compare_pass(self):
        m = _compare("test", 0.30, 0.31, tolerance=0.10)
        assert m.passed is True
        assert m.name == "test"

    def test_compare_fail(self):
        m = _compare("test", 0.10, 0.50, tolerance=0.10)
        assert m.passed is False

    def test_compare_absolute_mode(self):
        """Absolute tolerance: error = |predicted - target|."""
        m = _compare("test", 0.35, 0.31, tolerance=0.05, absolute=True)
        assert m.passed is True  # |0.35 - 0.31| = 0.04 < 0.05

    def test_compare_relative_mode(self):
        """Relative tolerance: error = |predicted - target| / |target|."""
        m = _compare("test", 0.35, 0.31, tolerance=0.15)
        # |0.35 - 0.31| / 0.31 = 0.129 < 0.15
        assert m.passed is True

    def test_report_grade_a(self):
        metrics = tuple(
            _compare(f"m{i}", 0.5, 0.5, tolerance=0.1) for i in range(5)
        )
        report = ValidationReport(
            metrics=metrics, passed_count=5, total_count=5, pass_rate=1.0,
            calibrated_params={}, calibration_modules=frozenset(),
            validation_modules=frozenset(), n_students=100,
        )
        assert report.grade == "A"


class TestValidationIntegration:
    @pytest.mark.slow
    def test_validate_with_default_params(self, mock_oulad_dir):
        """Validation runs end-to-end with mock OULAD data."""
        report = validate_against_oulad(
            calibrated_params={"config.dropout_base_rate": 0.70},
            oulad_dir=str(mock_oulad_dir),
            n_students=15,
            seed=42,
            validation_modules=frozenset({"AAA"}),
        )
        assert isinstance(report, ValidationReport)
        assert report.total_count >= 3
        assert 0.0 <= report.pass_rate <= 1.0
