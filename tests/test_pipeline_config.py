"""Tests for PipelineConfig frozen dataclass."""
from __future__ import annotations

import json

import pytest


def test_json_roundtrip_restores_event_weeks_and_custom_carry_over():
    """Loading a saved config must preserve calendars and typed carry-over."""
    from synthed.pipeline_config import PipelineConfig
    from synthed.simulation.semester import SemesterCarryOverConfig

    original = PipelineConfig(n_semesters=2, carry_over_config=SemesterCarryOverConfig(engagement_recovery=0.12))
    wire = json.loads(json.dumps(original.to_dict()))
    restored = PipelineConfig.from_dict(wire)
    assert restored == original
    assert restored.environment.scheduled_events.get(7) == original.environment.scheduled_events.get(7)
    assert isinstance(restored.carry_over_config, SemesterCarryOverConfig)
    assert restored.carry_over_config.engagement_recovery == 0.12


@pytest.mark.parametrize("field", ["scheduled_events", "positive_events"])
@pytest.mark.parametrize("bad_key", [True, False, 0, -1, "0", "-1", "7.0", "07"])
def test_invalid_event_week_is_rejected_with_field_context(field, bad_key):
    """Invalid calendar keys must fail before silently disappearing at runtime."""
    from synthed.pipeline_config import PipelineConfig

    with pytest.raises(ValueError, match=field):
        PipelineConfig.from_dict({"environment": {field: {bad_key: "exam_week"}}})


@pytest.mark.parametrize("field", ["scheduled_events", "positive_events"])
def test_event_week_normalization_rejects_collisions(field):
    """Distinct serialized keys must not silently overwrite the same week."""
    from synthed.pipeline_config import PipelineConfig

    with pytest.raises(ValueError, match=field):
        PipelineConfig.from_dict({"environment": {field: {7: "a", "7": "b"}}})


def test_loading_config_preserves_input_and_weeks_beyond_the_horizon():
    """Canonical keys normalize without mutating the caller's nested mapping."""
    import copy
    from synthed.pipeline_config import PipelineConfig

    wire = {"environment": {"scheduled_events": {"100": "exam_week"},
                            "positive_events": {"3": "support_boost"}}, "carry_over_config": None}
    unchanged = copy.deepcopy(wire)
    first = PipelineConfig.from_dict(wire)
    assert wire == unchanged
    assert PipelineConfig.from_dict(wire) == first
    assert first.environment.scheduled_events == {100: "exam_week"}
    assert first.environment.positive_events == {3: "support_boost"}
    assert first.carry_over_config is None


def test_unknown_carry_over_fields_are_not_silently_dropped():
    """A misspelled recovery setting must fail typed reconstruction."""
    from synthed.pipeline_config import PipelineConfig

    with pytest.raises(TypeError, match="unknown_recovery"):
        PipelineConfig.from_dict({"carry_over_config": {"unknown_recovery": 0.1}})


class TestPipelineConfigCreation:
    """Default construction and field count."""

    def test_default_construction(self):
        from synthed.pipeline_config import PipelineConfig
        config = PipelineConfig()
        assert config.seed == 42
        assert config.n_semesters == 1
        assert config.use_llm is False
        assert config.export_oulad is False
        assert config.output_dir == "./output"
        assert config.llm_model == "gpt-4o-mini"
        assert config.cost_threshold == 1.0

    def test_has_16_fields(self):
        """Contract test: PipelineConfig field count is part of the public API."""
        from dataclasses import fields
        from synthed.pipeline_config import PipelineConfig
        # Deliberate: adding/removing fields is a breaking change and must be reviewed
        assert len(fields(PipelineConfig)) == 16

    def test_frozen(self):
        from synthed.pipeline_config import PipelineConfig
        config = PipelineConfig()
        with pytest.raises(AttributeError):
            config.seed = 99


class TestPipelineConfigValidation:
    """__post_init__ validation."""

    def test_seed_zero_valid(self):
        from synthed.pipeline_config import PipelineConfig
        config = PipelineConfig(seed=0)
        assert config.seed == 0

    def test_seed_negative_raises(self):
        from synthed.pipeline_config import PipelineConfig
        with pytest.raises(ValueError, match="seed"):
            PipelineConfig(seed=-1)

    def test_n_semesters_zero_raises(self):
        from synthed.pipeline_config import PipelineConfig
        with pytest.raises(ValueError, match="n_semesters"):
            PipelineConfig(n_semesters=0)

    def test_cost_threshold_negative_raises(self):
        from synthed.pipeline_config import PipelineConfig
        with pytest.raises(ValueError, match="cost_threshold"):
            PipelineConfig(cost_threshold=-1.0)

    def test_target_dropout_range_ordered_valid(self):
        from synthed.pipeline_config import PipelineConfig
        cfg = PipelineConfig(target_dropout_range=(0.35, 0.55))
        assert cfg.target_dropout_range == (0.35, 0.55)

    def test_target_dropout_range_inverted_raises(self):
        from synthed.pipeline_config import PipelineConfig
        with pytest.raises(ValueError, match="lo <= hi"):
            PipelineConfig(target_dropout_range=(0.60, 0.35))

    def test_target_dropout_range_out_of_domain_raises(self):
        from synthed.pipeline_config import PipelineConfig
        with pytest.raises(ValueError, match="within \\[0, 1\\]"):
            PipelineConfig(target_dropout_range=(-0.1, 0.5))

    def test_target_dropout_range_wrong_length_raises(self):
        from synthed.pipeline_config import PipelineConfig
        with pytest.raises(ValueError, match="2-tuple"):
            PipelineConfig(target_dropout_range=(0.1, 0.3, 0.5))


class TestPipelineConfigReplace:
    """dataclasses.replace() produces new instance."""

    def test_replace_seed(self):
        from dataclasses import replace
        from synthed.pipeline_config import PipelineConfig
        original = PipelineConfig(seed=42)
        modified = replace(original, seed=99)
        assert modified.seed == 99
        assert original.seed == 42


class TestPipelineConfigSerialization:
    """to_dict / from_dict round-trip."""

    def test_to_dict_json_serializable(self):
        from synthed.pipeline_config import PipelineConfig
        config = PipelineConfig()
        d = config.to_dict()
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_round_trip(self):
        from synthed.pipeline_config import PipelineConfig
        config = PipelineConfig()
        restored = PipelineConfig.from_dict(config.to_dict())
        assert restored == config

    def test_round_trip_custom_values(self):
        from synthed.pipeline_config import PipelineConfig
        from synthed.simulation.grading import GradingConfig
        config = PipelineConfig(
            seed=123,
            n_semesters=2,
            use_llm=True,
            grading_config=GradingConfig(pass_threshold=0.55),
        )
        restored = PipelineConfig.from_dict(config.to_dict())
        assert restored == config
        assert restored.grading_config.pass_threshold == 0.55

    def test_round_trip_with_courses(self):
        """ODLEnvironment with Course list round-trips correctly."""
        from synthed.pipeline_config import PipelineConfig
        from synthed.simulation.environment import Course, ODLEnvironment
        env = ODLEnvironment(courses=[
            Course(id="TEST1", name="Test Course", difficulty=0.7),
        ])
        config = PipelineConfig(environment=env)
        restored = PipelineConfig.from_dict(config.to_dict())
        assert len(restored.environment.courses) == 1
        assert restored.environment.courses[0].id == "TEST1"
        assert restored.environment.courses[0].difficulty == 0.7

    def test_nested_fields_registry(self):
        from synthed.pipeline_config import _NESTED_FIELDS
        assert len(_NESTED_FIELDS) == 6


class TestPipelineConfigEquality:
    """Equality semantics."""

    def test_equal_configs(self):
        from synthed.pipeline_config import PipelineConfig
        assert PipelineConfig() == PipelineConfig()

    def test_unequal_configs(self):
        from synthed.pipeline_config import PipelineConfig
        assert PipelineConfig(seed=1) != PipelineConfig(seed=2)
