"""Tests for Sobol sensitivity analysis."""

from __future__ import annotations

import numpy as np
import pytest

from synthed.analysis.sobol_sensitivity import (
    SOBOL_PARAMETER_SPACE,
    SobolAnalyzer,
    SobolParameter,
    SobolResult,
)
from synthed.analysis._sim_runner import run_simulation_with_overrides


# ─────────────────────────────────────────────
# Parameter space definition tests
# ─────────────────────────────────────────────

class TestParameterSpace:
    def test_parameter_count(self):
        """Space has a meaningful number of parameters."""
        assert len(SOBOL_PARAMETER_SPACE) >= 30

    def test_unique_names(self):
        names = [p.name for p in SOBOL_PARAMETER_SPACE]
        assert len(names) == len(set(names)), "Duplicate parameter names found"

    def test_bounds_valid(self):
        """Every parameter has lower < upper."""
        for p in SOBOL_PARAMETER_SPACE:
            assert p.lower < p.upper, f"{p.name}: lower ({p.lower}) >= upper ({p.upper})"

    def test_prefix_convention(self):
        """All parameters use a known prefix."""
        known_prefixes = {
            "config", "engine", "tinto", "bean", "kember",
            "baulke", "sdt", "rovai", "garrison", "gonzalez",
            "moore", "epstein", "inst", "grading",
        }
        for p in SOBOL_PARAMETER_SPACE:
            prefix = p.name.split(".")[0]
            assert prefix in known_prefixes, f"Unknown prefix '{prefix}' in {p.name}"

    def test_config_params_are_valid_persona_fields(self):
        """config.* parameters correspond to actual PersonaConfig fields."""
        from synthed.agents.persona import PersonaConfig
        from dataclasses import fields

        config_fields = {f.name for f in fields(PersonaConfig)}
        for p in SOBOL_PARAMETER_SPACE:
            if p.name.startswith("config."):
                attr = p.name.split(".", 1)[1]
                assert attr in config_fields, f"{attr} not in PersonaConfig"

    def test_descriptions_not_empty(self):
        for p in SOBOL_PARAMETER_SPACE:
            assert len(p.description) > 0, f"{p.name} has empty description"

    def test_invalid_bounds_raises(self):
        """SobolParameter rejects lower >= upper."""
        with pytest.raises(ValueError, match="must be < upper"):
            SobolParameter("bad", 0.5, 0.5, "equal bounds")
        with pytest.raises(ValueError, match="must be < upper"):
            SobolParameter("bad", 0.8, 0.3, "reversed bounds")


# ─────────────────────────────────────────────
# SALib problem builder tests
# ─────────────────────────────────────────────

class TestParameterValidation:
    def test_invalid_config_field_raises(self):
        bad = (SobolParameter("config.nonexistent_field", 0.1, 0.9, "test"),)
        with pytest.raises(ValueError, match="Unknown PersonaConfig field"):
            SobolAnalyzer(n_students=10, parameters=bad)

    def test_invalid_engine_attr_raises(self):
        bad = (SobolParameter("engine._NONEXISTENT_WEIGHT", 0.1, 0.9, "test"),)
        with pytest.raises(ValueError, match="Unknown EngineConfig field"):
            SobolAnalyzer(n_students=10, parameters=bad)

    def test_invalid_theory_attr_raises(self):
        bad = (SobolParameter("bean._NONEXISTENT_PENALTY", 0.1, 0.9, "test"),)
        with pytest.raises(ValueError, match="Unknown attribute"):
            SobolAnalyzer(n_students=10, parameters=bad)

    def test_invalid_prefix_raises(self):
        bad = (SobolParameter("unknown_module.some_attr", 0.1, 0.9, "test"),)
        with pytest.raises(ValueError, match="Unknown parameter prefix"):
            SobolAnalyzer(n_students=10, parameters=bad)

    def test_default_space_passes_validation(self):
        """Full SOBOL_PARAMETER_SPACE validates without error."""
        analyzer = SobolAnalyzer(n_students=10, seed=42)
        assert len(analyzer.parameters) == len(SOBOL_PARAMETER_SPACE)


class TestProblemBuilder:
    def test_build_problem_structure(self):
        analyzer = SobolAnalyzer(n_students=10, seed=42)
        problem = analyzer._problem
        assert "num_vars" in problem
        assert "names" in problem
        assert "bounds" in problem
        assert problem["num_vars"] == len(SOBOL_PARAMETER_SPACE)
        assert len(problem["names"]) == problem["num_vars"]
        assert len(problem["bounds"]) == problem["num_vars"]

    def test_custom_parameter_subset(self):
        """Analyzer accepts a custom parameter subset."""
        subset = (
            SobolParameter("config.employment_rate", 0.4, 0.9, "test"),
            SobolParameter("config.dropout_base_rate", 0.5, 0.9, "test"),
        )
        analyzer = SobolAnalyzer(n_students=10, parameters=subset)
        assert analyzer._problem["num_vars"] == 2

    def test_bounds_match_parameters(self):
        analyzer = SobolAnalyzer(n_students=10)
        for i, p in enumerate(SOBOL_PARAMETER_SPACE):
            assert analyzer._problem["bounds"][i] == [p.lower, p.upper]


# ─────────────────────────────────────────────
# Sample generation tests
# ─────────────────────────────────────────────

class TestSampleGeneration:
    def test_sample_shape(self):
        """Sobol sampler generates n*(D+2) rows (no second-order)."""
        subset = (
            SobolParameter("config.employment_rate", 0.4, 0.9, "test"),
            SobolParameter("config.dropout_base_rate", 0.5, 0.9, "test"),
        )
        analyzer = SobolAnalyzer(n_students=10, parameters=subset)
        samples = analyzer.generate_samples(n_samples=8)
        d = 2
        expected_rows = 8 * (d + 2)  # 8 * 4 = 32
        assert samples.shape == (expected_rows, d)

    def test_samples_within_bounds(self):
        subset = (
            SobolParameter("config.employment_rate", 0.4, 0.9, "test"),
            SobolParameter("config.dropout_base_rate", 0.5, 0.9, "test"),
        )
        analyzer = SobolAnalyzer(n_students=10, parameters=subset)
        samples = analyzer.generate_samples(n_samples=8)
        assert np.all(samples[:, 0] >= 0.4)
        assert np.all(samples[:, 0] <= 0.9)
        assert np.all(samples[:, 1] >= 0.5)
        assert np.all(samples[:, 1] <= 0.9)


# ─────────────────────────────────────────────
# Override application tests
# ─────────────────────────────────────────────

class TestOverrides:
    def test_config_override_builds_valid_config(self):
        from synthed.analysis._sim_runner import _build_config
        from synthed.agents.persona import PersonaConfig
        config = _build_config(PersonaConfig(), {"employment_rate": 0.55})
        assert config.employment_rate == 0.55
        assert config.dropout_base_rate == 0.80

    def test_engine_override_applies(self, tmp_path):
        """Engine-level constants can be overridden via EngineConfig replace."""
        from synthed.pipeline import SynthEdPipeline
        from synthed.analysis._sim_runner import _apply_engine_overrides
        from synthed.simulation.engine_config import EngineConfig
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        original = pipeline.engine.cfg._TINTO_ACADEMIC_WEIGHT
        _apply_engine_overrides(
            pipeline,
            {"_TINTO_ACADEMIC_WEIGHT": 0.999},
            {},
        )
        assert pipeline.engine.cfg._TINTO_ACADEMIC_WEIGHT == 0.999
        assert EngineConfig()._TINTO_ACADEMIC_WEIGHT == original

    def test_theory_override_applies(self, tmp_path):
        """Theory module constants can be overridden."""
        from synthed.pipeline import SynthEdPipeline
        from synthed.analysis._sim_runner import _apply_engine_overrides
        pipeline = SynthEdPipeline(output_dir=str(tmp_path), seed=42)
        _apply_engine_overrides(
            pipeline,
            {},
            {"bean": {"_OVERWORK_PENALTY": 0.999}},
        )
        assert pipeline.engine.bean_metzner._OVERWORK_PENALTY == 0.999


# ─────────────────────────────────────────────
# Ranking tests
# ─────────────────────────────────────────────

class TestRanking:
    def test_rank_sorts_by_st_descending(self):
        result = SobolResult(
            metric="dropout_rate",
            parameter_names=("a", "b", "c"),
            s1=(0.1, 0.5, 0.3),
            s1_conf=(0.01, 0.01, 0.01),
            st=(0.15, 0.6, 0.35),
            st_conf=(0.01, 0.01, 0.01),
            n_simulations=100,
        )
        analyzer = SobolAnalyzer(n_students=10)
        rankings = analyzer.rank(result)
        assert rankings[0].parameter == "b"
        assert rankings[0].rank == 1
        assert rankings[1].parameter == "c"
        assert rankings[2].parameter == "a"

    def test_rank_top_n(self):
        result = SobolResult(
            metric="dropout_rate",
            parameter_names=("a", "b", "c"),
            s1=(0.1, 0.5, 0.3),
            s1_conf=(0.01, 0.01, 0.01),
            st=(0.15, 0.6, 0.35),
            st_conf=(0.01, 0.01, 0.01),
            n_simulations=100,
        )
        analyzer = SobolAnalyzer(n_students=10)
        rankings = analyzer.rank(result, top_n=2)
        assert len(rankings) == 2
        assert rankings[0].parameter == "b"

    def test_rank_interaction_computed(self):
        result = SobolResult(
            metric="dropout_rate",
            parameter_names=("a",),
            s1=(0.2,),
            s1_conf=(0.01,),
            st=(0.5,),
            st_conf=(0.01,),
            n_simulations=100,
        )
        analyzer = SobolAnalyzer(n_students=10)
        rankings = analyzer.rank(result)
        assert rankings[0].interaction == round(0.5 - 0.2, 4)

    def test_negative_indices_clipped_to_zero(self):
        """Negative Sobol indices (numerical noise) are clipped to 0."""
        result = SobolResult(
            metric="dropout_rate",
            parameter_names=("a",),
            s1=(-0.05,),
            s1_conf=(0.1,),
            st=(-0.02,),
            st_conf=(0.1,),
            n_simulations=100,
        )
        analyzer = SobolAnalyzer(n_students=10)
        rankings = analyzer.rank(result)
        assert rankings[0].s1 == 0.0
        assert rankings[0].st == 0.0
        assert rankings[0].interaction == 0.0


# ─────────────────────────────────────────────
# Integration test (small-scale)
# ─────────────────────────────────────────────

class TestSobolIntegration:
    @pytest.mark.slow
    def test_full_run_with_minimal_params(self):
        """
        End-to-end Sobol with 2 parameters, N=8, n_students=15.

        This is a smoke test — Sobol indices with so few samples are
        not statistically meaningful, but the pipeline must complete
        without errors and return valid structure.
        """
        subset = (
            SobolParameter("config.dropout_base_rate", 0.50, 0.90, "Dropout scaling"),
            SobolParameter("config.employment_rate", 0.40, 0.90, "Employment rate"),
        )
        analyzer = SobolAnalyzer(n_students=15, seed=42, parameters=subset)
        results = analyzer.run(n_samples=8)

        # Should produce 3 results (dropout_rate, mean_engagement, mean_gpa)
        assert len(results) == 3
        assert results[0].metric == "dropout_rate"
        assert results[1].metric == "mean_engagement"
        assert results[2].metric == "mean_gpa"

        # Each result has correct shape
        for r in results:
            assert len(r.s1) == 2
            assert len(r.st) == 2
            assert r.n_simulations == 8 * (2 + 2)  # 32

        # Rankings work
        rankings = analyzer.rank(results[0])
        assert len(rankings) == 2
        assert rankings[0].rank == 1
        assert rankings[1].rank == 2

    @pytest.mark.slow
    def test_engine_and_theory_overrides_in_run(self):
        """
        Verify that engine/theory overrides actually change simulation output.

        Run two simulations with the same seed but extreme parameter values:
        one with very low dropout risk multiplier, one with very high.
        """
        from synthed.agents.persona import PersonaConfig
        default_config = PersonaConfig()

        result_low = run_simulation_with_overrides(
            {"baulke._DECISION_RISK_MULTIPLIER": 0.05},
            n_students=20, seed=42, default_config=default_config,
        )
        result_high = run_simulation_with_overrides(
            {"baulke._DECISION_RISK_MULTIPLIER": 0.90},
            n_students=20, seed=42, default_config=default_config,
        )

        # Higher risk multiplier should produce more dropouts
        assert result_high["dropout_rate"] >= result_low["dropout_rate"]
