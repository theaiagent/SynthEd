from __future__ import annotations

import pytest

from synthed.analysis.nsga2_calibrator import (
    NSGAIICalibrationError,
    NSGAIICalibrator,
    select_nsga2_parameters,
)
from synthed.analysis.pareto_utils import ParetoResult, ParetoSolution
from synthed.analysis.sobol_sensitivity import SobolRanking


class TestSelectNsga2Parameters:
    def _make_rankings(self) -> list[SobolRanking]:
        return [
            SobolRanking(parameter="grading.grade_floor", s1=0.2, st=0.3, interaction=0.1, rank=1),
            SobolRanking(parameter="config.employment_rate", s1=0.15, st=0.25, interaction=0.1, rank=2),
            SobolRanking(parameter="inst.technology_quality", s1=0.1, st=0.2, interaction=0.1, rank=3),
            SobolRanking(parameter="kember._QUALITY_FACTOR", s1=0.08, st=0.15, interaction=0.07, rank=4),
            SobolRanking(parameter="baulke._RECOVERY_1_TO_0", s1=0.05, st=0.10, interaction=0.05, rank=5),
            SobolRanking(parameter="gonzalez._RECOVERY_BASE", s1=0.04, st=0.08, interaction=0.04, rank=6),
        ]

    def test_excludes_config_and_inst_prefixes(self):
        rankings = self._make_rankings()
        result = select_nsga2_parameters(rankings, top_n=10)
        names = [p.name for p in result]
        assert not any(n.startswith("config.") for n in names)
        assert not any(n.startswith("inst.") for n in names)

    def test_returns_top_n_engine_theory_params(self):
        rankings = self._make_rankings()
        result = select_nsga2_parameters(rankings, top_n=3)
        names = [p.name for p in result]
        assert "grading.grade_floor" in names

    def test_returns_tuple_of_sobol_parameters(self):
        rankings = self._make_rankings()
        result = select_nsga2_parameters(rankings, top_n=3)
        assert isinstance(result, tuple)

    def test_empty_rankings_returns_empty(self):
        result = select_nsga2_parameters([], top_n=5)
        assert result == ()

    def test_force_include_adds_params(self):
        rankings = self._make_rankings()
        result = select_nsga2_parameters(
            rankings, top_n=5,
            force_include=frozenset({"grading.grade_floor"}),
        )
        names = [p.name for p in result]
        assert "grading.grade_floor" in names

    def test_force_include_respects_total(self):
        rankings = self._make_rankings()
        result = select_nsga2_parameters(
            rankings, top_n=5,
            force_include=frozenset({"grading.grade_floor", "grading.pass_threshold"}),
        )
        # 2 forced + 3 from ranking = 5 total
        assert len(result) <= 5

    def test_force_include_unknown_name_raises(self):
        rankings = self._make_rankings()
        with pytest.raises(ValueError, match="Unknown force_include"):
            select_nsga2_parameters(
                rankings, top_n=5,
                force_include=frozenset({"grading.__does_not_exist__"}),
            )

    def test_force_include_fixed_prefix_raises(self):
        rankings = self._make_rankings()
        with pytest.raises(ValueError, match="cannot contain fixed-prefix"):
            select_nsga2_parameters(
                rankings, top_n=5,
                force_include=frozenset({"config.employment_rate"}),
            )


class TestNSGAIICalibrationError:
    def test_is_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise NSGAIICalibrationError("test")


class TestNSGAIICalibrator:
    def test_init_stores_params(self):
        cal = NSGAIICalibrator(n_students=50, seed=99, n_workers=2)
        assert cal._n_students == 50
        assert cal._seed == 99
        assert cal._n_workers == 2

    def test_build_fixed_overrides_includes_float_fields(self):
        from synthed.benchmarks.profiles import PROFILES
        cal = NSGAIICalibrator()
        profile = PROFILES["default"]
        overrides = cal._build_fixed_overrides(profile)
        assert "config.employment_rate" in overrides
        assert "inst.technology_quality" in overrides
        assert overrides["inst.technology_quality"] == 0.60

    def test_build_fixed_overrides_excludes_bool_fields(self):
        from synthed.benchmarks.profiles import PROFILES
        cal = NSGAIICalibrator()
        profile = PROFILES["default"]
        overrides = cal._build_fixed_overrides(profile)
        assert "config.generate_names" not in overrides

    def test_build_fixed_overrides_all_values_are_float(self):
        from synthed.benchmarks.profiles import PROFILES
        cal = NSGAIICalibrator()
        profile = PROFILES["default"]
        overrides = cal._build_fixed_overrides(profile)
        for key, val in overrides.items():
            assert isinstance(val, float), f"{key} is not float: {type(val)}"

    def test_unknown_profile_raises(self):
        cal = NSGAIICalibrator()
        with pytest.raises(NSGAIICalibrationError, match="Unknown profile"):
            cal.run("nonexistent_profile", n_trials=10)


class TestHVTracking:
    @pytest.mark.slow
    def test_run_populates_hv_history(self, monkeypatch):
        import random
        rng = random.Random(42)

        def _mock_sim(**kwargs):
            return {
                "dropout_rate": 0.20 + rng.random() * 0.25,
                "mean_gpa": 2.0 + rng.random() * 1.5,
                "mean_engagement": 0.3 + rng.random() * 0.4,
            }

        monkeypatch.setattr(
            "synthed.analysis.nsga2_calibrator.run_simulation_with_overrides",
            _mock_sim,
        )

        rankings = [
            SobolRanking(parameter="grading.grade_floor", s1=0.2, st=0.3, interaction=0.1, rank=1),
            SobolRanking(parameter="kember._QUALITY_FACTOR", s1=0.15, st=0.25, interaction=0.1, rank=2),
            SobolRanking(parameter="gonzalez._RECOVERY_BASE", s1=0.1, st=0.2, interaction=0.1, rank=3),
        ]

        cal = NSGAIICalibrator(n_students=30, seed=42)
        result = cal.run(
            profile="default",
            pop_size=5,
            n_trials=20,
            sobol_rankings=rankings,
            sobol_top_n=3,
        )

        assert len(result.hv_history) > 0
        assert all(hv >= 0 for hv in result.hv_history)


class TestNSGAIIIntegration:
    """Integration test with a very small NSGA-II run."""

    @pytest.mark.slow
    def test_small_nsga2_produces_pareto_result(self, monkeypatch):
        """Minimal run: pop=5, n_trials=20, n_students=30.

        Mocks the simulation runner to return controllable values that
        satisfy all constraints (engagement >= 0.3, dropout in range).
        This tests the NSGA-II machinery end-to-end without depending
        on full simulation behavior with tiny populations.
        """
        import random

        rng = random.Random(42)

        def _mock_sim(**kwargs):
            return {
                "dropout_rate": 0.20 + rng.random() * 0.25,  # 0.20-0.45
                "mean_gpa": 2.0 + rng.random() * 1.5,        # 2.0-3.5
                "mean_engagement": 0.3 + rng.random() * 0.4,  # 0.3-0.7
            }

        monkeypatch.setattr(
            "synthed.analysis.nsga2_calibrator.run_simulation_with_overrides",
            _mock_sim,
        )

        rankings = [
            SobolRanking(parameter="grading.grade_floor", s1=0.2, st=0.3, interaction=0.1, rank=1),
            SobolRanking(parameter="kember._QUALITY_FACTOR", s1=0.15, st=0.25, interaction=0.1, rank=2),
            SobolRanking(parameter="gonzalez._RECOVERY_BASE", s1=0.1, st=0.2, interaction=0.1, rank=3),
            SobolRanking(parameter="baulke._DECISION_RISK_MULTIPLIER", s1=0.08, st=0.15, interaction=0.07, rank=4),
            SobolRanking(parameter="engine._TINTO_ACADEMIC_WEIGHT", s1=0.05, st=0.10, interaction=0.05, rank=5),
        ]

        cal = NSGAIICalibrator(n_students=30, seed=42)
        result = cal.run(
            profile="default",
            pop_size=5,
            n_trials=20,
            sobol_rankings=rankings,
            sobol_top_n=5,
        )

        assert isinstance(result, ParetoResult)
        assert result.profile_name == "default"
        assert len(result.pareto_front) > 0
        assert result.knee_point is not None
        assert result.n_evaluations == 20
        assert len(result.parameter_names) == 5

    @pytest.mark.slow
    def test_validate_solution_returns_stats(self):
        """Test validate_solution returns (dropout_mean, dropout_std, gpa_mean, gpa_std)."""
        cal = NSGAIICalibrator(n_students=30, seed=42)
        solution = ParetoSolution(
            params={"grading.grade_floor": 0.45},
            dropout_error=0.05,
            gpa_error=0.1,
            engagement_error=0.05,
            achieved_dropout=0.30,
            achieved_gpa=2.5,
            achieved_engagement=0.5,
        )
        d_mean, d_std, g_mean, g_std = cal.validate_solution(
            solution,
            profile="default",
            n_students=30,
            seeds=(42, 123),
        )
        assert 0.0 <= d_mean <= 1.0
        assert d_std >= 0.0
        assert 0.0 <= g_mean <= 4.0
        assert g_std >= 0.0


class TestReevaluatePareto:
    @pytest.mark.slow
    def test_reevaluate_returns_new_pareto_result(self):
        cal = NSGAIICalibrator(n_students=30, seed=42)
        s1 = ParetoSolution(
            params={"grading.grade_floor": 0.45},
            dropout_error=0.05, gpa_error=0.1, engagement_error=0.05,
            achieved_dropout=0.37, achieved_gpa=2.5, achieved_engagement=0.5,
        )
        s2 = ParetoSolution(
            params={"grading.grade_floor": 0.50},
            dropout_error=0.08, gpa_error=0.05, engagement_error=0.03,
            achieved_dropout=0.34, achieved_gpa=2.7, achieved_engagement=0.47,
        )
        front = (s1, s2)
        result = cal.reevaluate_pareto_front(
            pareto_front=front,
            profile="default",
            n_students=30,
            seeds=(42, 123),
        )
        assert isinstance(result, ParetoResult)
        assert len(result.pareto_front) <= 2
        assert result.knee_point is not None
        assert result.profile_name == "default"
