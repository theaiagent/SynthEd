"""Tests for SynthEd Dashboard config bridge, distribution normalization, and charts."""

from synthed.pipeline_config import PipelineConfig
from synthed.dashboard.config_bridge import (
    config_to_dict,
    dict_to_config,
    normalize_distribution,
    get_description,
    check_warning,
)
from synthed.dashboard.components.warnings import validate_config
from synthed.dashboard import charts


class TestConfigBridgeRoundTrip:
    """Config → dict → Config round-trip preserves values."""

    def test_default_config_round_trip(self):
        original = PipelineConfig()
        flat = config_to_dict(original)
        rebuilt = dict_to_config(flat)
        assert rebuilt.seed == original.seed
        assert rebuilt.n_semesters == original.n_semesters
        assert rebuilt.persona_config.employment_rate == original.persona_config.employment_rate
        assert rebuilt.persona_config.dropout_base_rate == original.persona_config.dropout_base_rate
        assert rebuilt.institutional_config.support_services_quality == original.institutional_config.support_services_quality
        assert rebuilt.grading_config.pass_threshold == original.grading_config.pass_threshold
        assert rebuilt.engine_config._ENGAGEMENT_CLIP_LO == original.engine_config._ENGAGEMENT_CLIP_LO

    def test_custom_config_round_trip(self):
        from synthed.agents.persona import PersonaConfig
        pc = PersonaConfig(employment_rate=0.9, dropout_base_rate=0.5)
        original = PipelineConfig(seed=99, n_semesters=3, persona_config=pc)
        flat = config_to_dict(original)
        rebuilt = dict_to_config(flat)
        assert rebuilt.seed == 99
        assert rebuilt.n_semesters == 3
        assert rebuilt.persona_config.employment_rate == 0.9
        assert rebuilt.persona_config.dropout_base_rate == 0.5

    def test_flat_dict_has_prefixed_keys(self):
        flat = config_to_dict(PipelineConfig())
        assert "persona_employment_rate" in flat
        assert "inst_support_services_quality" in flat
        assert "grading_pass_threshold" in flat
        assert "engine__ENGAGEMENT_CLIP_LO" in flat
        assert "seed" in flat

    def test_all_persona_fields_present(self):
        flat = config_to_dict(PipelineConfig())
        persona_keys = [k for k in flat if k.startswith("persona_")]
        assert len(persona_keys) == 21

    def test_all_engine_fields_present(self):
        flat = config_to_dict(PipelineConfig())
        engine_keys = [k for k in flat if k.startswith("engine_")]
        assert len(engine_keys) == 70


class TestDistributionNormalization:
    """Auto-normalize keeps sum = 1.0."""

    def test_normalize_basic(self):
        dist = {"a": 0.3, "b": 0.3, "c": 0.4}
        result = normalize_distribution(dist, "a")
        assert abs(sum(result.values()) - 1.0) < 1e-6
        assert result["a"] == 0.3

    def test_normalize_increase(self):
        dist = {"intrinsic": 0.25, "extrinsic": 0.45, "amotivation": 0.30}
        result = normalize_distribution(dist, "intrinsic")
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_normalize_to_zero(self):
        dist = {"a": 0.5, "b": 0.3, "c": 0.2}
        dist["a"] = 0.0
        result = normalize_distribution(dist, "a")
        assert result["a"] == 0.0
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_normalize_to_one(self):
        dist = {"a": 0.5, "b": 0.3, "c": 0.2}
        dist["a"] = 1.0
        result = normalize_distribution(dist, "a")
        assert result["a"] == 1.0
        assert abs(sum(result.values()) - 1.0) < 1e-6


class TestFieldDescriptions:
    """Tooltip descriptions work."""

    def test_known_field(self):
        desc = get_description("persona_dropout_base_rate")
        assert "dropout" in desc.lower()

    def test_unknown_field(self):
        assert get_description("nonexistent_xyz") == ""

    def test_institutional_field(self):
        desc = get_description("inst_support_services_quality")
        assert "support" in desc.lower()


class TestWarnings:
    """Field warnings and cross-field validation."""

    def test_high_dropout_warns(self):
        msg = check_warning("persona_dropout_base_rate", 0.95)
        assert msg is not None
        assert "dropout" in msg.lower()

    def test_normal_dropout_no_warning(self):
        assert check_warning("persona_dropout_base_rate", 0.5) is None

    def test_cross_field_threshold_error(self):
        vals = config_to_dict(PipelineConfig())
        vals["grading_pass_threshold"] = 0.8
        vals["grading_distinction_threshold"] = 0.7
        issues = validate_config(vals)
        errors = [i for i in issues if i["level"] == "error"]
        assert any("pass_threshold" in e["message"] for e in errors)

    def test_valid_config_no_errors(self):
        vals = config_to_dict(PipelineConfig())
        issues = validate_config(vals)
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 0


class TestChartBuilders:
    """Plotly chart functions return valid figures."""

    def test_dropout_timeline(self):
        fig = charts.dropout_timeline([5, 10, 8, 12, 6], 200)
        assert fig is not None
        assert len(fig.data) == 1

    def test_engagement_distribution(self):
        import numpy as np
        rng = np.random.default_rng(42)
        engagements = rng.uniform(0, 1, 100).tolist()
        fig = charts.engagement_distribution(engagements)
        assert fig is not None
        assert len(fig.data) == 1

    def test_gpa_distribution(self):
        import numpy as np
        rng = np.random.default_rng(42)
        gpas = rng.normal(2.5, 0.8, 100).tolist()
        fig = charts.gpa_distribution(gpas, 0.64, 0.73)
        assert fig is not None

    def test_validation_radar(self):
        scores = {"Demographics": 0.9, "Correlations": 0.8, "Temporal": 1.0,
                  "Privacy": 0.7, "Backstory": 0.5}
        fig = charts.validation_radar(scores)
        assert fig is not None
        assert len(fig.data) == 1
