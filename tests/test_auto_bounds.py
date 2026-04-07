"""Tests for auto_bounds parameter generation."""

from __future__ import annotations

from synthed.agents.persona import PersonaConfig
from synthed.analysis.auto_bounds import auto_bounds, _NON_TUNEABLE
from synthed.analysis.sobol_sensitivity import SobolAnalyzer, SobolParameter


class TestAutoGeneration:
    def test_returns_non_empty(self):
        params = auto_bounds()
        assert len(params) > 0

    def test_all_bounds_valid(self):
        for p in auto_bounds():
            assert p.lower < p.upper, f"{p.name}: {p.lower} >= {p.upper}"

    def test_unique_names(self):
        params = auto_bounds()
        names = [p.name for p in params]
        assert len(names) == len(set(names)), f"Duplicates: {[n for n in names if names.count(n) > 1]}"

    def test_known_prefixes(self):
        known = {"config", "engine", "tinto", "bean", "kember",
                 "baulke", "sdt", "rovai", "garrison", "gonzalez",
                 "moore", "epstein"}
        for p in auto_bounds():
            prefix = p.name.split(".")[0]
            assert prefix in known, f"Unknown prefix '{prefix}' in {p.name}"

    def test_no_non_float_config_fields(self):
        """Bool, str, dict, tuple fields are excluded."""
        for p in auto_bounds():
            if p.name.startswith("config."):
                attr = p.name.split(".")[1]
                val = getattr(PersonaConfig(), attr)
                assert isinstance(val, float), f"{p.name} is {type(val)}"

    def test_descriptions_not_empty(self):
        for p in auto_bounds():
            assert len(p.description) > 0


class TestMarginAndClipping:
    def test_employment_rate_clipped_to_1(self):
        """Even with large margin, employment_rate upper <= 1.0."""
        params = auto_bounds(margin=0.9)
        emp = next(p for p in params if p.name == "config.employment_rate")
        assert emp.upper <= 1.0

    def test_prior_gpa_clipped_to_4(self):
        params = auto_bounds(margin=0.9)
        gpa = next(p for p in params if p.name == "config.prior_gpa_mean")
        assert gpa.upper <= 4.0

    def test_withdrawal_rate_clipped(self):
        params = auto_bounds(margin=0.9)
        wr = next(p for p in params if p.name == "config.unavoidable_withdrawal_rate")
        assert wr.upper <= 0.05

    def test_wider_margin_produces_wider_bounds(self):
        narrow = auto_bounds(margin=0.2)
        wide = auto_bounds(margin=0.8)
        narrow_emp = next(p for p in narrow if p.name == "config.employment_rate")
        wide_emp = next(p for p in wide if p.name == "config.employment_rate")
        assert (wide_emp.upper - wide_emp.lower) >= (narrow_emp.upper - narrow_emp.lower)


class TestFiltering:
    def test_include_config_false(self):
        params = auto_bounds(include_config=False)
        assert not any(p.name.startswith("config.") for p in params)
        assert len(params) > 0  # still has engine/theory

    def test_include_engine_false(self):
        params = auto_bounds(include_engine=False)
        assert not any(p.name.startswith("engine.") for p in params)

    def test_include_theories_false(self):
        theory_prefixes = {"tinto", "bean", "kember", "baulke", "sdt",
                          "rovai", "garrison", "gonzalez", "moore", "epstein"}
        params = auto_bounds(include_theories=False)
        for p in params:
            prefix = p.name.split(".")[0]
            assert prefix not in theory_prefixes

    def test_exclude_specific(self):
        params = auto_bounds(exclude=frozenset({"config.dropout_base_rate"}))
        names = {p.name for p in params}
        assert "config.dropout_base_rate" not in names

    def test_non_tuneable_excluded(self):
        params = auto_bounds()
        for p in params:
            attr = p.name.split(".")[1]
            assert attr not in _NON_TUNEABLE, f"{p.name} should be excluded"


class TestCustomConfig:
    def test_custom_config_changes_bounds(self):
        """auto_bounds uses provided config's defaults as center."""
        default_params = auto_bounds()
        custom_params = auto_bounds(config=PersonaConfig(employment_rate=0.95))

        default_emp = next(p for p in default_params if p.name == "config.employment_rate")
        custom_emp = next(p for p in custom_params if p.name == "config.employment_rate")

        # Custom has higher center → different bounds
        assert custom_emp.lower > default_emp.lower
        # But upper is clipped to 1.0 for both (0.95 * 1.5 > 1.0)
        assert custom_emp.upper <= 1.0


class TestCompatibility:
    def test_works_with_sobol_analyzer(self):
        """auto_bounds output passes SobolAnalyzer init-time validation."""
        params = auto_bounds()
        analyzer = SobolAnalyzer(n_students=10, seed=42, parameters=params)
        assert len(analyzer.parameters) == len(params)

    def test_sobol_parameter_type(self):
        for p in auto_bounds():
            assert isinstance(p, SobolParameter)


class TestEdgeCases:
    def test_margin_zero_returns_empty(self):
        """margin=0 produces lower==upper for all params, so all are skipped."""
        params = auto_bounds(margin=0.0)
        assert len(params) == 0

    def test_single_source_only(self):
        """Only config, no engine/theories."""
        params = auto_bounds(include_engine=False, include_theories=False)
        assert len(params) > 0
        assert all(p.name.startswith("config.") for p in params)

