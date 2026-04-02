"""Targeted tests to close remaining coverage gaps."""

from __future__ import annotations

from synthed.analysis.auto_bounds import auto_bounds, _compute_bounds


class TestAutoBoundsEdgeCases:
    def test_negative_default_bounds(self):
        """_compute_bounds handles negative defaults correctly."""
        lo, hi = _compute_bounds(-0.3, 0.5)
        assert lo < hi
        assert lo == -0.3 * 1.5  # -0.45
        assert hi == -0.3 * 0.5  # -0.15

    def test_zero_default_bounds(self):
        """_compute_bounds returns (0, 0) for zero default."""
        lo, hi = _compute_bounds(0.0, 0.5)
        assert lo == 0.0
        assert hi == 0.0

    def test_config_field_without_validation_range(self):
        """Config float fields without explicit validate_range still get bounds."""
        params = auto_bounds(include_engine=False, include_theories=False)
        names = {p.name for p in params}
        assert "config.prior_gpa_std" in names


class TestPipelineOuladExport:
    def test_pipeline_with_oulad_export(self, tmp_path):
        """Pipeline with export_oulad=True produces OULAD files."""
        from synthed.pipeline import SynthEdPipeline
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path), seed=42, export_oulad=True,
        )
        report = pipeline.run(n_students=15)
        assert "oulad" in report["exported_files"]
        oulad_paths = report["exported_files"]["oulad"]
        assert len(oulad_paths) == 7


class TestPipelineCostCheck:
    def test_cost_check_blocks_enrichment(self, tmp_path, monkeypatch):
        """Cost check blocks LLM enrichment when threshold exceeded."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-fake")
        from synthed.pipeline import SynthEdPipeline
        pipeline = SynthEdPipeline(
            output_dir=str(tmp_path), seed=42,
            use_llm=True, cost_threshold=0.0001,
        )
        # run with enrich_personas=True — should skip due to cost block
        report = pipeline.run(n_students=10, enrich_personas=True)
        assert report["simulation_summary"]["total_students"] == 10


class TestBaulkeEdgeCases:
    def test_phase_transition_with_low_gpa(self):
        """Baulke non-fit perception triggered by low GPA."""
        from synthed.agents.persona import StudentPersona, BigFiveTraits
        from synthed.simulation.engine import SimulationEngine, SimulationState
        from synthed.simulation.environment import ODLEnvironment

        env = ODLEnvironment()
        engine = SimulationEngine(environment=env, seed=42)

        student = StudentPersona(
            personality=BigFiveTraits(conscientiousness=0.2),
            goal_commitment=0.2, self_efficacy=0.2,
            self_regulation=0.2, motivation_type="amotivation",
        )
        state = SimulationState(
            student_id=student.id,
            current_engagement=0.15,
            cumulative_gpa=1.0,
            gpa_count=3,
            perceived_mastery_sum=0.0,
            perceived_mastery_count=3,
            dropout_phase=0,
        )

        engine.baulke.advance_phase(
            student, state, week=5, env=env,
            avg_td_fn=lambda s, st: 0.6,
            rng=engine.rng,
        )
        assert state.dropout_phase >= 1


class TestOuladTargetsEdgeCases:
    def test_scores_with_invalid_values(self, tmp_path):
        """Scores with non-numeric values are skipped."""
        import csv
        from synthed.analysis.oulad_targets import extract_targets

        with open(tmp_path / "studentInfo.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["code_module", "code_presentation", "id_student", "gender",
                         "region", "highest_education", "imd_band", "age_band",
                         "num_of_prev_attempts", "studied_credits", "disability", "final_result"])
            w.writerow(["AAA", "2024J", "1", "M", "R", "HE", "50%", "0-35", "0", "60", "N", "Pass"])

        with open(tmp_path / "studentAssessment.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id_assessment", "id_student", "date_submitted", "is_banked", "score"])
            w.writerow(["1", "1", "10", "0", ""])  # empty score
            w.writerow(["2", "1", "20", "0", "75"])  # valid

        with open(tmp_path / "studentVle.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"])
            w.writerow(["AAA", "2024J", "1", "1", "1", "10"])

        targets = extract_targets(tmp_path)
        assert targets.score_mean == 75.0


class TestLlmEdgeCases:
    def test_llm_http_warning_logged(self, monkeypatch):
        """HTTP base_url logs warning but doesn't raise."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-fake")
        from synthed.utils.llm import LLMClient
        # Should not raise — just logs a warning
        client = LLMClient(base_url="http://localhost:9999/v1")
        assert client.base_url == "http://localhost:9999/v1"
