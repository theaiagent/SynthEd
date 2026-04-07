"""Tests for sensitivity analysis module."""

from __future__ import annotations

import pytest

from synthed.analysis.sensitivity import SensitivityAnalyzer, SensitivityResult


class TestSensitivityAnalyzer:
    """OAT sensitivity sweep tests with minimal parameters for speed."""

    @pytest.mark.slow
    def test_oat_sweep_returns_results(self, tmp_path):
        """run_oat_sweep with tiny population returns non-empty result list."""
        analyzer = SensitivityAnalyzer(n_students=20, seed=42)
        # Sweep only one parameter with 2 steps for speed
        results = analyzer.run_oat_sweep(
            n_steps=2,
            params={"employment_rate": (0.3, 0.9)},
        )

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, SensitivityResult) for r in results)

        # Check result field structure
        r = results[0]
        assert hasattr(r, "parameter")
        assert hasattr(r, "base_value")
        assert hasattr(r, "perturbed_value")
        assert hasattr(r, "base_dropout_rate")
        assert hasattr(r, "perturbed_dropout_rate")
        assert hasattr(r, "delta")
        assert hasattr(r, "normalized_sensitivity")

    @pytest.mark.slow
    def test_tornado_chart_data(self, tmp_path):
        """tornado_chart_data returns dict with expected keys per parameter."""
        analyzer = SensitivityAnalyzer(n_students=20, seed=42)
        results = analyzer.run_oat_sweep(
            n_steps=2,
            params={"self_regulation_mean": (0.2, 0.7)},
        )

        tornado = analyzer.tornado_chart_data(results)

        assert isinstance(tornado, dict)
        assert "self_regulation_mean" in tornado
        entry = tornado["self_regulation_mean"]
        assert "min_dropout" in entry
        assert "max_dropout" in entry
        assert "base_dropout" in entry
        assert entry["min_dropout"] <= entry["max_dropout"]

