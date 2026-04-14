"""Integration tests for the SynthEdPipeline."""

import logging
import warnings

import pytest

from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig


class TestPipelineIntegration:
    def test_full_pipeline_run(self, tmp_path):
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        report = pipeline.run(n_students=20)
        assert "pipeline" in report
        assert "simulation_summary" in report
        assert "validation" in report
        assert report["simulation_summary"]["total_students"] == 20

    def test_pipeline_creates_output_files(self, tmp_path):
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        pipeline.run(n_students=20)
        expected_files = ["students.csv", "interactions.csv",
                          "outcomes.csv", "weekly_engagement.csv"]
        for fname in expected_files:
            assert (tmp_path / fname).exists(), f"{fname} not created"

    def test_pipeline_validation_has_results(self, tmp_path):
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        report = pipeline.run(n_students=20)
        validation = report["validation"]
        assert validation["summary"]["total_tests"] > 0

    def test_pipeline_rejects_zero_students(self, tmp_path):
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        with pytest.raises(ValueError):
            pipeline.run(n_students=0)


class TestPipelineCalibration:
    """Tests for _apply_calibration and target_dropout_range (lines 71, 95-113)."""

    def test_target_dropout_range_triggers_calibration(self, tmp_path):
        """Pipeline with target_dropout_range applies calibration (line 71)."""
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            target_dropout_range=(0.35, 0.55),
        )
        # Calibration should have updated persona_config
        assert pipeline._calibration_estimate is not None
        assert pipeline._calibration_estimate.confidence in ("high", "low")
        assert pipeline.persona_config.dropout_base_rate != 0.46  # changed from default

    def test_calibration_updates_reference_stats(self, tmp_path):
        """_apply_calibration updates reference_stats with target range (lines 95-113)."""
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            target_dropout_range=(0.35, 0.55),
        )
        # Midpoint of (0.35, 0.55) = 0.45
        assert abs(pipeline.reference.dropout_rate - 0.45) < 1e-10
        assert pipeline.reference.dropout_range == (0.35, 0.55)

    def test_calibration_report_includes_dropout_targeting(self, tmp_path):
        """Pipeline report includes dropout_targeting when calibrated (lines 185-186)."""
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            target_dropout_range=(0.35, 0.55),
        )
        report = pipeline.run(n_students=20)
        assert "dropout_targeting" in report
        dt = report["dropout_targeting"]
        assert dt["target_range"] == (0.35, 0.55)
        assert "estimated_base_rate" in dt
        assert "confidence" in dt


class TestPipelineFromProfile:
    """Tests for SynthEdPipeline.from_profile classmethod (lines 133-142)."""

    def test_from_profile_valid(self, tmp_path):
        """from_profile with a valid profile creates a properly configured pipeline."""
        pipeline = SynthEdPipeline.from_profile(
            "default",
            output_dir=str(tmp_path),
        )
        assert pipeline._calibration_estimate is not None
        assert pipeline.target_dropout_range == (0.20, 0.45)
        # Run to ensure it works end-to-end
        report = pipeline.run(n_students=20)
        assert "simulation_summary" in report

    def test_from_profile_invalid(self):
        """from_profile with unknown profile name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown profile"):
            SynthEdPipeline.from_profile("nonexistent_profile")


class TestPipelineMultiSemesterInterim:
    """Tests for multi-semester interim reports (line 224)."""

    def test_multi_semester_with_target_range_has_interim_reports(self, tmp_path):
        """Multi-semester pipeline with target_dropout_range includes interim_reports."""
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            n_semesters=2,
            target_dropout_range=(0.35, 0.85),
        )
        report = pipeline.run(n_students=20)
        assert "interim_reports" in report
        assert len(report["interim_reports"]) == 2
        for ir in report["interim_reports"]:
            assert "semester" in ir
            assert "cumulative_dropout_rate" in ir
            assert "target_range" in ir
            assert ir["status"] in ("on_track", "below_target", "above_target")

    def test_multi_semester_without_target_range_no_interim(self, tmp_path):
        """Multi-semester pipeline without target_dropout_range has no interim_reports."""
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path),
            seed=42,
            n_semesters=2,
        )
        report = pipeline.run(n_students=20)
        # No target_dropout_range => no interim reports
        assert "interim_reports" not in report


class TestSmallNWarning:
    """Tests for small n_students warning (P8)."""

    def test_small_n_emits_warning(self, tmp_path, caplog):
        """Running with n_students < 100 must emit a warning via the pipeline logger."""
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        with caplog.at_level(logging.WARNING, logger="synthed.pipeline"):
            pipeline.run(n_students=30)
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("n_students=30" in msg and "small" in msg for msg in warning_messages)

    def test_no_warning_for_large_n(self, tmp_path, caplog):
        """Running with n_students >= 100 must NOT emit a small-n warning."""
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        with caplog.at_level(logging.WARNING, logger="synthed.pipeline"):
            pipeline.run(n_students=100)
        small_n_warnings = [
            r for r in caplog.records
            if "small" in r.getMessage() and "n_students" in r.getMessage()
        ]
        assert len(small_n_warnings) == 0


class TestPipelineConfigBridge:
    """Tests for the PipelineConfig deprecation bridge."""

    def test_new_style_config(self, tmp_path):
        """SynthEdPipeline(config=PipelineConfig()) works."""
        config = PipelineConfig(output_dir=str(tmp_path), seed=42)
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.config.seed == 42

    def test_legacy_kwargs_emit_warning(self, tmp_path):
        """Legacy kwargs emit DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SynthEdPipeline(output_dir=str(tmp_path), seed=42)
            dep_warns = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warns) >= 1
            assert "PipelineConfig" in str(dep_warns[0].message)

    def test_mixed_args_raises(self, tmp_path):
        """config= plus legacy kwargs raises TypeError."""
        config = PipelineConfig(output_dir=str(tmp_path))
        with pytest.raises(TypeError, match="Cannot pass both"):
            SynthEdPipeline(config=config, seed=42)

    def test_unknown_kwarg_raises(self):
        """Unknown legacy kwargs raise TypeError."""
        with pytest.raises(TypeError, match="Unknown keyword"):
            SynthEdPipeline(bad_param=1)

    def test_new_style_full_run(self, tmp_path):
        """Full pipeline run with PipelineConfig."""
        config = PipelineConfig(output_dir=str(tmp_path), seed=42)
        pipeline = SynthEdPipeline(config=config)
        report = pipeline.run(n_students=20)
        assert "simulation_summary" in report


class TestPropertyDelegation:
    """Verify @property delegates to self.config."""

    def test_persona_config_delegates(self, tmp_path):
        config = PipelineConfig(output_dir=str(tmp_path))
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.persona_config is pipeline.config.persona_config

    def test_environment_delegates(self, tmp_path):
        config = PipelineConfig(output_dir=str(tmp_path))
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.environment is pipeline.config.environment

    def test_reference_delegates(self, tmp_path):
        config = PipelineConfig(output_dir=str(tmp_path))
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.reference is pipeline.config.reference_stats

    def test_seed_delegates(self, tmp_path):
        config = PipelineConfig(output_dir=str(tmp_path), seed=99)
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.seed == 99

    def test_target_dropout_range_delegates(self, tmp_path):
        config = PipelineConfig(
            output_dir=str(tmp_path),
            target_dropout_range=(0.30, 0.50),
        )
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.target_dropout_range == (0.30, 0.50)

    def test_engine_config_forwarded(self, tmp_path):
        """engine_config correctly forwarded to SimulationEngine."""
        from dataclasses import replace as dc_replace
        from synthed.simulation.engine_config import EngineConfig
        custom_cfg = dc_replace(EngineConfig(), _LOGIN_ENG_MULTIPLIER=9.9)
        config = PipelineConfig(
            output_dir=str(tmp_path),
            engine_config=custom_cfg,
        )
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.engine.cfg._LOGIN_ENG_MULTIPLIER == 9.9
        assert pipeline.engine.cfg == custom_cfg

    def test_calibration_updates_config(self, tmp_path):
        """Post-calibration persona_config differs from default."""
        config = PipelineConfig(
            output_dir=str(tmp_path),
            target_dropout_range=(0.35, 0.55),
        )
        default_rate = PipelineConfig().persona_config.dropout_base_rate
        pipeline = SynthEdPipeline(config=config)
        assert pipeline.config.persona_config.dropout_base_rate != default_rate
