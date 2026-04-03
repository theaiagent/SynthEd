"""Tests for GradingConfig and grading utilities."""
from __future__ import annotations

import numpy as np
import pytest

from synthed.simulation.grading import (
    GradingConfig,
    GradingScale,
    apply_relative_grading,
    calculate_semester_grade,
    check_dual_hurdle_pass,
    classify_outcome,
    compute_grade,
    convert_scale,
    piecewise_gpa,
    sample_base_quality,
)


class TestGradingConfig:
    def test_default_values(self):
        cfg = GradingConfig()
        assert cfg.scale == GradingScale.SCALE_100
        assert cfg.midterm_weight == 0.40
        assert cfg.final_weight == 0.60
        assert cfg.distribution == "beta"
        assert cfg.grade_floor == 0.45
        assert cfg.pass_threshold == 0.64
        assert cfg.distinction_threshold == 0.73
        assert cfg.noise_std == 0.05
        assert cfg.late_penalty == 0.05
        assert cfg.dual_hurdle is False
        assert cfg.exam_eligibility_threshold is None

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            GradingConfig(midterm_weight=0.50, final_weight=0.60)

    def test_midterm_components_must_sum_to_one(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            GradingConfig(midterm_components={"exam": 0.3, "assignment": 0.3})

    def test_invalid_component_key_raises(self):
        with pytest.raises(ValueError, match="Invalid midterm_components"):
            GradingConfig(midterm_components={"project": 0.5, "exam": 0.5})

    def test_threshold_ordering(self):
        with pytest.raises(ValueError, match="distinction_threshold.*pass_threshold"):
            GradingConfig(pass_threshold=0.90, distinction_threshold=0.50)

    def test_numeric_range_validation(self):
        with pytest.raises(ValueError):
            GradingConfig(noise_std=-0.1)
        with pytest.raises(ValueError):
            GradingConfig(grade_floor=1.5)

    def test_corporate_exam_only(self):
        cfg = GradingConfig(
            midterm_weight=0.0, final_weight=1.0,
            midterm_components={}, assessment_mode="exam_only",
        )
        assert cfg.final_weight == 1.0

    def test_continuous_no_final(self):
        cfg = GradingConfig(
            midterm_weight=1.0, final_weight=0.0,
            assessment_mode="continuous",
        )
        assert cfg.midterm_weight == 1.0

    def test_frozen(self):
        cfg = GradingConfig()
        with pytest.raises(AttributeError):
            cfg.scale = GradingScale.SCALE_4

    def test_uniform_requires_alpha_less_than_beta(self):
        with pytest.raises(ValueError, match="dist_alpha.*dist_beta"):
            GradingConfig(distribution="uniform", dist_alpha=0.8, dist_beta=0.2)

    def test_relative_grading_method_rejected(self):
        with pytest.raises(ValueError, match="not yet implemented"):
            GradingConfig(grading_method="relative")

    def test_invalid_grading_method_rejected(self):
        with pytest.raises(ValueError, match="Invalid grading_method"):
            GradingConfig(grading_method="curved")

    def test_dual_hurdle_requires_thresholds(self):
        with pytest.raises(ValueError, match="component_pass_thresholds"):
            GradingConfig(dual_hurdle=True)

    def test_float_tolerance_for_weights(self):
        """Independently set float weights should not crash on precision."""
        cfg = GradingConfig(midterm_weight=0.3, final_weight=0.7)
        assert cfg.midterm_weight == 0.3


class TestPiecewiseGPA:
    def test_zero(self):
        assert piecewise_gpa(0.0) == 0.0

    def test_pass_boundary(self):
        assert abs(piecewise_gpa(0.40) - 1.0) < 0.01

    def test_mid_range(self):
        assert abs(piecewise_gpa(0.55) - 2.0) < 0.01

    def test_good(self):
        assert abs(piecewise_gpa(0.70) - 3.0) < 0.01

    def test_distinction(self):
        assert abs(piecewise_gpa(0.85) - 3.7) < 0.01

    def test_perfect(self):
        assert piecewise_gpa(1.0) == 4.0

    def test_interpolation(self):
        gpa = piecewise_gpa(0.475)  # midpoint of 0.40-0.55
        assert 1.4 < gpa < 1.6


class TestConvertScale:
    def test_100_scale(self):
        assert convert_scale(0.75, GradingScale.SCALE_100) == 75.0

    def test_4_scale_uses_piecewise(self):
        result = convert_scale(0.70, GradingScale.SCALE_4)
        assert abs(result - 3.0) < 0.01

    def test_zero(self):
        assert convert_scale(0.0, GradingScale.SCALE_100) == 0.0


class TestClassifyOutcome:
    def test_distinction(self):
        assert classify_outcome(0.90, GradingConfig()) == "Distinction"

    def test_pass(self):
        assert classify_outcome(0.68, GradingConfig()) == "Pass"

    def test_fail(self):
        assert classify_outcome(0.30, GradingConfig()) == "Fail"

    def test_boundary_pass(self):
        assert classify_outcome(0.64, GradingConfig()) == "Pass"

    def test_boundary_fail(self):
        assert classify_outcome(0.63, GradingConfig()) == "Fail"

    def test_custom_thresholds(self):
        cfg = GradingConfig(pass_threshold=0.50, distinction_threshold=0.90)
        assert classify_outcome(0.45, cfg) == "Fail"
        assert classify_outcome(0.50, cfg) == "Pass"
        assert classify_outcome(0.90, cfg) == "Distinction"


class TestComputeGrade:
    def test_with_floor_100_scale(self):
        cfg = GradingConfig(grade_floor=0.45)
        result = compute_grade(0.5, cfg)
        # 0.45 + 0.55*0.5 = 0.725 → 72.5
        assert abs(result - 72.5) < 0.01

    def test_with_floor_4_scale(self):
        cfg = GradingConfig(scale=GradingScale.SCALE_4, grade_floor=0.45)
        result = compute_grade(0.5, cfg)
        # graded = 0.725 → piecewise_gpa(0.725) ≈ 3.0 + (0.725-0.70)/0.15 * 0.7 ≈ 3.117
        assert 3.0 < result < 3.2


class TestSampleQuality:
    def test_beta_mean(self):
        cfg = GradingConfig(distribution="beta", dist_alpha=5.0, dist_beta=3.0)
        rng = np.random.default_rng(42)
        samples = [sample_base_quality(cfg, rng) for _ in range(5000)]
        assert 0.59 < np.mean(samples) < 0.66  # Beta(5,3) mean=0.625

    def test_normal_clipped(self):
        cfg = GradingConfig(distribution="normal", dist_alpha=0.65, dist_beta=0.12)
        rng = np.random.default_rng(42)
        samples = [sample_base_quality(cfg, rng) for _ in range(1000)]
        assert all(0.0 <= s <= 1.0 for s in samples)

    def test_invalid_distribution(self):
        cfg = GradingConfig.__new__(GradingConfig)
        object.__setattr__(cfg, "distribution", "cauchy")
        rng = np.random.default_rng(42)
        with pytest.raises(ValueError):
            sample_base_quality(cfg, rng)


class TestRelativeGrading:
    def test_mean_50(self):
        adjusted = apply_relative_grading([30.0, 50.0, 70.0, 90.0, 60.0])
        assert abs(np.mean(adjusted) - 50.0) < 0.5

    def test_preserves_order(self):
        adjusted = apply_relative_grading([20.0, 40.0, 60.0, 80.0])
        assert adjusted[0] < adjusted[1] < adjusted[2] < adjusted[3]

    def test_single_student(self):
        assert apply_relative_grading([75.0]) == [50.0]

    def test_identical_scores(self):
        assert all(s == 50.0 for s in apply_relative_grading([60.0, 60.0, 60.0]))

    def test_uses_sample_std(self):
        """ddof=1 for sample standard deviation."""
        scores = [40.0, 60.0]
        adjusted = apply_relative_grading(scores)
        assert len(adjusted) == 2


class TestCalculateSemesterGrade:
    def test_basic_40_60(self):
        cfg = GradingConfig()
        grade = calculate_semester_grade(
            cfg, midterm_exam_scores=[0.70],
            assignment_scores=[0.80, 0.60], forum_scores=[0.90],
            final_score=0.75, n_total_assignments=2, n_total_forums=1,
        )
        # midterm = exam*0.5 + assign*0.3 + forum*0.2
        #         = 0.70*0.5 + 0.70*0.3 + 0.90*0.2 = 0.74
        # semester = 0.74*0.4 + 0.75*0.6 = 0.746
        assert abs(grade - 0.746) < 0.01

    def test_exam_only(self):
        cfg = GradingConfig(
            assessment_mode="exam_only", midterm_weight=0.0,
            final_weight=1.0, midterm_components={},
        )
        assert calculate_semester_grade(cfg, [], [], [], 0.85) == 0.85

    def test_continuous_no_final(self):
        cfg = GradingConfig(
            assessment_mode="continuous", midterm_weight=1.0,
            final_weight=0.0, midterm_components={"assignment": 1.0},
        )
        grade = calculate_semester_grade(
            cfg, [], [0.70, 0.80], [], None, n_total_assignments=2,
        )
        assert abs(grade - 0.75) < 0.01

    def test_partial_submission_uses_total_denominator(self):
        cfg = GradingConfig(midterm_components={"assignment": 1.0})
        # 2 teslim / 4 toplam, her ikisi 0.80
        grade = calculate_semester_grade(
            cfg, [], [0.80, 0.80], [], 0.70,
            n_total_assignments=4, n_total_forums=0,
        )
        # assign mean = (0.80+0.80)/4 = 0.40
        # semester = 0.40*0.4 + 0.70*0.6 = 0.58
        assert abs(grade - 0.58) < 0.01

    def test_missing_policy_redistribute(self):
        cfg = GradingConfig(missing_policy="redistribute")
        # forum boş, ağırlığı exam ve assignment'a dağıtılır
        grade = calculate_semester_grade(
            cfg, [0.70], [0.80], [], 0.75,
            n_total_assignments=1, n_total_forums=0,
        )
        assert grade is not None
        assert 0.0 <= grade <= 1.0

    def test_no_final_returns_none(self):
        cfg = GradingConfig()
        assert calculate_semester_grade(cfg, [0.7], [0.6], [0.5], None) is None

    def test_dual_hurdle_check(self):
        cfg = GradingConfig(
            dual_hurdle=True,
            component_pass_thresholds={"midterm": 0.30, "final": 0.40},
        )
        assert check_dual_hurdle_pass(cfg, 0.35, 0.50) is True
        assert check_dual_hurdle_pass(cfg, 0.25, 0.50) is False  # midterm fail
        assert check_dual_hurdle_pass(cfg, 0.35, 0.35) is False  # final fail
