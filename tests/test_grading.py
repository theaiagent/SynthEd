"""Tests for GradingConfig and grading utilities."""
from __future__ import annotations

import math

import numpy as np
import pytest

from synthed.simulation.grading import (
    GradingConfig,
    GradingScale,
    classify_outcome,
    compute_grade,
    convert_scale,
    piecewise_gpa,
)


class TestGradingConfig:
    def test_default_values(self):
        cfg = GradingConfig()
        assert cfg.scale == GradingScale.SCALE_100
        assert cfg.midterm_weight == 0.40
        assert cfg.final_weight == 0.60
        assert cfg.distribution == "beta"
        assert cfg.grade_floor == 0.45
        assert cfg.pass_threshold == 0.40
        assert cfg.distinction_threshold == 0.85
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
