from __future__ import annotations

import pytest

from synthed.analysis.nsga2_calibrator import (
    NSGAIICalibrationError,
    NSGAIICalibrator,
    select_nsga2_parameters,
)
from synthed.analysis.sobol_sensitivity import SobolRanking


class TestSelectNsga2Parameters:
    def _make_rankings(self) -> list[SobolRanking]:
        return [
            SobolRanking(parameter="engine._GRADE_FLOOR", s1=0.2, st=0.3, interaction=0.1, rank=1),
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
        assert "engine._GRADE_FLOOR" in names

    def test_returns_tuple_of_sobol_parameters(self):
        rankings = self._make_rankings()
        result = select_nsga2_parameters(rankings, top_n=3)
        assert isinstance(result, tuple)

    def test_empty_rankings_returns_empty(self):
        result = select_nsga2_parameters([], top_n=5)
        assert result == ()


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
        profile = PROFILES["moderate_dropout_western"]
        overrides = cal._build_fixed_overrides(profile)
        assert "config.employment_rate" in overrides
        assert "inst.technology_quality" in overrides
        assert overrides["inst.technology_quality"] == 0.75

    def test_build_fixed_overrides_excludes_bool_fields(self):
        from synthed.benchmarks.profiles import PROFILES
        cal = NSGAIICalibrator()
        profile = PROFILES["moderate_dropout_western"]
        overrides = cal._build_fixed_overrides(profile)
        assert "config.generate_names" not in overrides

    def test_build_fixed_overrides_all_values_are_float(self):
        from synthed.benchmarks.profiles import PROFILES
        cal = NSGAIICalibrator()
        profile = PROFILES["moderate_dropout_western"]
        overrides = cal._build_fixed_overrides(profile)
        for key, val in overrides.items():
            assert isinstance(val, float), f"{key} is not float: {type(val)}"

    def test_unknown_profile_raises(self):
        cal = NSGAIICalibrator()
        with pytest.raises(NSGAIICalibrationError, match="Unknown profile"):
            cal.run("nonexistent_profile", n_trials=10)
