"""Integration tests for the SynthEdPipeline."""

import pytest

from synthed.pipeline import SynthEdPipeline


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
        assert pipeline.persona_config.dropout_base_rate != 0.80  # changed from default

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
            "low_dropout_corporate",
            output_dir=str(tmp_path),
        )
        assert pipeline._calibration_estimate is not None
        assert pipeline.target_dropout_range == (0.05, 0.25)
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
