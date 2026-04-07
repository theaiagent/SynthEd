"""Tests for EngineConfig frozen dataclass."""

from __future__ import annotations

import dataclasses

import pytest

from synthed.simulation.engine_config import EngineConfig


class TestEngineConfigDefaults:
    """Default construction and field access."""

    def test_default_construction(self):
        cfg = EngineConfig()
        assert isinstance(cfg, EngineConfig)

    def test_is_frozen(self):
        cfg = EngineConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg._LOGIN_ENG_MULTIPLIER = 99.0  # type: ignore[misc]

    def test_replace_returns_new_instance(self):
        cfg = EngineConfig()
        cfg2 = dataclasses.replace(cfg, _LOGIN_ENG_MULTIPLIER=10.0)
        assert cfg2._LOGIN_ENG_MULTIPLIER == 10.0
        assert cfg._LOGIN_ENG_MULTIPLIER == 5.0  # original unchanged

    def test_field_count(self):
        """Regression guard: adding/removing constants must update this test."""
        fields = dataclasses.fields(EngineConfig)
        assert len(fields) == 70

    def test_all_defaults_match_engine_originals(self):
        """Spot-check key defaults to ensure no copy-paste errors."""
        cfg = EngineConfig()
        assert cfg._LOGIN_ENG_MULTIPLIER == 5.0
        assert cfg._FORUM_POST_ENG_FACTOR == 0.25
        assert cfg._ASSIGN_GPA_WEIGHT == 0.25
        assert cfg._EXAM_NOISE_STD == 0.18
        assert cfg._DECAY_DAMPING_FACTOR == 0.5
        assert cfg._TINTO_ACADEMIC_WEIGHT == 0.06
        assert cfg._ENGAGEMENT_CLIP_LO == 0.01
        assert cfg._ENGAGEMENT_CLIP_HI == 0.99
        assert cfg._MISSED_STREAK_CAP == 3
        assert cfg._GPA_SCALE == 4.0
        assert cfg._NETWORK_DECAY_RATE == 0.02


class TestEngineConfigValidation:
    """__post_init__ validation rules."""

    def test_engagement_clip_order(self):
        with pytest.raises(ValueError, match="CLIP_LO.*CLIP_HI"):
            EngineConfig(_ENGAGEMENT_CLIP_LO=0.99, _ENGAGEMENT_CLIP_HI=0.01)

    def test_quality_threshold_order(self):
        with pytest.raises(ValueError, match="LOW.*HIGH"):
            EngineConfig(_LOW_QUALITY_THRESHOLD=0.8, _HIGH_QUALITY_THRESHOLD=0.2)

    def test_inst_scale_order(self):
        with pytest.raises(ValueError, match="SCALE_LOW.*SCALE_HIGH"):
            EngineConfig(_INST_QUALITY_SCALE_LOW=1.5, _INST_QUALITY_SCALE_HIGH=0.5)

    def test_missed_streak_cap_positive(self):
        with pytest.raises(ValueError, match="MISSED_STREAK_CAP"):
            EngineConfig(_MISSED_STREAK_CAP=0)

    def test_gpa_scale_positive(self):
        with pytest.raises(ValueError, match="GPA_SCALE"):
            EngineConfig(_GPA_SCALE=0.0)

    def test_negative_weight_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            EngineConfig(_TINTO_ACADEMIC_WEIGHT=-0.1)

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            EngineConfig(_LOGIN_DURATION_MIN=-5.0)

    def test_assignment_weight_sum_must_be_one(self):
        with pytest.raises(ValueError, match="Assignment quality weights"):
            EngineConfig(_ASSIGN_GPA_WEIGHT=0.50)  # sum > 1.0

    def test_exam_weight_sum_must_be_one(self):
        with pytest.raises(ValueError, match="Exam quality weights"):
            EngineConfig(_EXAM_GPA_WEIGHT=0.50)  # sum > 1.0

    def test_submit_weights_cap(self):
        with pytest.raises(ValueError, match="submit weights"):
            EngineConfig(_ASSIGN_SUBMIT_BASE=0.8)  # sum > 1.0

    def test_noise_std_positive(self):
        with pytest.raises(ValueError, match="NOISE_STD"):
            EngineConfig(_ASSIGN_NOISE_STD=0.0)

    def test_coi_baseline_offset_non_negative(self):
        with pytest.raises(ValueError, match="non-negative"):
            EngineConfig(_COI_BASELINE_OFFSET=-0.01)


class TestEngineConfigOverride:
    """Integration: override via _sim_runner pattern."""

    def test_replace_with_filtered_dict(self):
        overrides = {"_TINTO_ACADEMIC_WEIGHT": 0.10, "_TINTO_SOCIAL_WEIGHT": 0.05}
        cfg = EngineConfig()
        cfg2 = dataclasses.replace(cfg, **overrides)
        assert cfg2._TINTO_ACADEMIC_WEIGHT == 0.10
        assert cfg2._TINTO_SOCIAL_WEIGHT == 0.05
        # Other fields unchanged
        assert cfg2._DECAY_DAMPING_FACTOR == cfg._DECAY_DAMPING_FACTOR

    def test_invalid_field_in_replace_raises(self):
        with pytest.raises(TypeError):
            dataclasses.replace(EngineConfig(), _NONEXISTENT_FIELD=1.0)

