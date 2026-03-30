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
