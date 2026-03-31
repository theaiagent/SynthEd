"""Tests for StudentFactory population generation."""

from dataclasses import replace

import numpy as np
import pytest

from synthed.agents.factory import StudentFactory
from synthed.agents.persona import PersonaConfig, StudentPersona


class TestStudentFactory:
    def test_generate_population_count(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=50)
        assert len(pop) == 50

    def test_deterministic_with_seed(self):
        """Same seed produces identical populations (names default to "")."""
        pop1 = StudentFactory(seed=42).generate_population(n=10)
        pop2 = StudentFactory(seed=42).generate_population(n=10)
        for p1, p2 in zip(pop1, pop2):
            assert p1.name == p2.name  # both "" with default config
            assert p1.age == p2.age
            assert abs(p1.financial_stress - p2.financial_stress) < 1e-9
            assert abs(p1.self_regulation - p2.self_regulation) < 1e-9

    def test_population_summary_has_expected_keys(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=20)
        summary = factory.population_summary(pop)
        expected_keys = [
            "total_students", "age_mean", "age_std",
            "gender_distribution", "employment_rate",
            "financial_stress_mean", "gpa_mean",
            "digital_literacy_mean", "self_regulation_mean",
            "base_engagement_mean", "base_dropout_risk_mean",
        ]
        for key in expected_keys:
            assert key in summary, f"Missing key: {key}"

    def test_all_personas_have_valid_ranges(self):
        factory = StudentFactory(seed=99)
        pop = factory.generate_population(n=100)
        for p in pop:
            assert 0.0 <= p.digital_literacy <= 1.0
            assert 0.0 <= p.self_regulation <= 1.0
            assert 0.0 <= p.financial_stress <= 1.0
            assert 0.0 <= p.self_efficacy <= 1.0
            assert 0.0 <= p.goal_commitment <= 1.0
            assert 0.05 <= p.base_engagement_probability <= 0.95
            assert 0.02 <= p.base_dropout_risk <= 0.90
            assert p.personality.openness >= 0.0
            assert p.personality.openness <= 1.0


class TestDropoutScaling:
    """Tests for dropout_base_rate → base_dropout_risk scaling."""

    def test_scaling_identity_at_default(self):
        """Default dropout_base_rate (0.80) produces scale=1.0, no change."""
        unscaled = StudentFactory(seed=42).generate_population(50)
        default = StudentFactory(PersonaConfig(dropout_base_rate=0.80), seed=42).generate_population(50)
        for u, d in zip(unscaled, default):
            assert abs(u.base_dropout_risk - d.base_dropout_risk) < 1e-10

    def test_scaling_increases_risk(self):
        """Higher dropout_base_rate produces higher mean risk."""
        default = StudentFactory(seed=42).generate_population(200)
        high = StudentFactory(PersonaConfig(dropout_base_rate=0.90), seed=42).generate_population(200)
        mean_default = np.mean([p.base_dropout_risk for p in default])
        mean_high = np.mean([p.base_dropout_risk for p in high])
        assert mean_high > mean_default

    def test_scaling_decreases_risk(self):
        """Lower dropout_base_rate produces lower mean risk."""
        default = StudentFactory(seed=42).generate_population(200)
        low = StudentFactory(PersonaConfig(dropout_base_rate=0.40), seed=42).generate_population(200)
        mean_default = np.mean([p.base_dropout_risk for p in default])
        mean_low = np.mean([p.base_dropout_risk for p in low])
        assert mean_low < mean_default

    def test_scaling_respects_bounds(self):
        """Scaled values stay within [0.02, 0.90] even at extreme rates."""
        high = StudentFactory(PersonaConfig(dropout_base_rate=0.95), seed=42).generate_population(200)
        low = StudentFactory(PersonaConfig(dropout_base_rate=0.10), seed=42).generate_population(200)
        for p in high + low:
            assert 0.02 <= p.base_dropout_risk <= 0.90

    def test_scaling_survives_replace(self):
        """Scale is preserved after dataclasses.replace() (e.g. LLM enrichment)."""
        factory = StudentFactory(PersonaConfig(dropout_base_rate=0.90), seed=42)
        personas = factory.generate_population(10)
        for p in personas:
            p2 = replace(p, backstory="test backstory")
            assert abs(p.base_dropout_risk - p2.base_dropout_risk) < 1e-10

    def test_dropout_base_rate_zero_rejected(self):
        """dropout_base_rate=0.0 raises ValueError at config construction."""
        with pytest.raises(ValueError):
            PersonaConfig(dropout_base_rate=0.0)


class TestDisplayId:
    def test_display_ids_assigned_sequentially(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=5)
        expected = ["S-0001", "S-0002", "S-0003", "S-0004", "S-0005"]
        assert [p.display_id for p in pop] == expected

    def test_display_ids_unique(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=100)
        assert len(set(p.display_id for p in pop)) == 100

    def test_display_id_format(self):
        import re
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=50)
        pattern = re.compile(r"^S-\d{4,}$")  # 4+ digits (handles n>9999)
        for p in pop:
            assert pattern.match(p.display_id)

    def test_display_id_survives_replace(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=3)
        for p in pop:
            assert replace(p, backstory="test").display_id == p.display_id

    def test_display_id_default_empty(self):
        assert StudentPersona(name="Manual").display_id == ""


class TestNameGeneration:
    def test_default_no_names(self):
        """Default PersonaConfig produces empty names for all personas."""
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=10)
        for p in pop:
            assert p.name == ""

    def test_generate_names_true(self):
        """generate_names=True produces non-empty names."""
        cfg = PersonaConfig(generate_names=True)
        factory = StudentFactory(config=cfg, seed=42)
        pop = factory.generate_population(n=10)
        for p in pop:
            assert p.name != ""
            assert " " in p.name  # first + last

    def test_names_deterministic(self):
        """Same seed + generate_names=True produces same names."""
        cfg = PersonaConfig(generate_names=True)
        pop1 = StudentFactory(config=cfg, seed=42).generate_population(n=10)
        pop2 = StudentFactory(config=cfg, seed=42).generate_population(n=10)
        for p1, p2 in zip(pop1, pop2):
            assert p1.name == p2.name

    def test_names_do_not_affect_attributes(self):
        """Toggling generate_names does not change any simulation attribute.

        This is the CRITICAL regression test proving RNG isolation.
        """
        pop_no_names = StudentFactory(seed=42).generate_population(n=50)
        cfg = PersonaConfig(generate_names=True)
        pop_with_names = StudentFactory(config=cfg, seed=42).generate_population(n=50)
        for p1, p2 in zip(pop_no_names, pop_with_names):
            assert p1.age == p2.age
            assert abs(p1.financial_stress - p2.financial_stress) < 1e-9
            assert abs(p1.self_regulation - p2.self_regulation) < 1e-9
            assert abs(p1.self_efficacy - p2.self_efficacy) < 1e-9
            assert abs(p1.base_dropout_risk - p2.base_dropout_risk) < 1e-9
            assert abs(p1.base_engagement_probability - p2.base_engagement_probability) < 1e-9
            assert p1.gender == p2.gender
            assert p1.motivation_type == p2.motivation_type

    def test_display_id_independent_of_names(self):
        """Display IDs are identical regardless of generate_names."""
        pop1 = StudentFactory(seed=42).generate_population(n=10)
        cfg = PersonaConfig(generate_names=True)
        pop2 = StudentFactory(config=cfg, seed=42).generate_population(n=10)
        for p1, p2 in zip(pop1, pop2):
            assert p1.display_id == p2.display_id


class TestDisabilitySeverityGeneration:
    def test_disability_rate_respected(self):
        """Population disability rate should be approximately disability_rate."""
        cfg = PersonaConfig(disability_rate=0.20)
        factory = StudentFactory(config=cfg, seed=42)
        pop = factory.generate_population(n=500)
        disabled_count = sum(1 for p in pop if p.disability_severity > 0)
        rate = disabled_count / len(pop)
        # Within reasonable range of 0.20 (allow ±0.08 for N=500)
        assert 0.10 < rate < 0.30

    def test_disability_severity_is_spectrum(self):
        """Disabled students should have varied severity, not all the same."""
        cfg = PersonaConfig(disability_rate=0.50)
        factory = StudentFactory(config=cfg, seed=42)
        pop = factory.generate_population(n=100)
        severities = [p.disability_severity for p in pop if p.disability_severity > 0]
        assert len(severities) > 10
        # Should have at least 3 unique severity values (spectrum, not binary)
        assert len(set(severities)) >= 3

    def test_disabled_students_lower_digital_literacy(self):
        """Disabled students should have lower mean digital_literacy."""
        import numpy as np
        cfg = PersonaConfig(disability_rate=0.50)
        factory = StudentFactory(config=cfg, seed=42)
        pop = factory.generate_population(n=200)
        disabled = [p for p in pop if p.disability_severity > 0]
        non_disabled = [p for p in pop if p.disability_severity == 0]
        assert len(disabled) > 20 and len(non_disabled) > 20
        mean_dis = np.mean([p.digital_literacy for p in disabled])
        mean_non = np.mean([p.digital_literacy for p in non_disabled])
        assert mean_dis < mean_non

    def test_disability_rate_zero_no_disabled(self):
        """disability_rate=0 produces no disabled students."""
        cfg = PersonaConfig(disability_rate=0.0)
        factory = StudentFactory(config=cfg, seed=42)
        pop = factory.generate_population(n=100)
        assert all(p.disability_severity == 0.0 for p in pop)

    def test_disability_deterministic(self):
        """Same seed produces same disability assignments."""
        cfg = PersonaConfig(disability_rate=0.15)
        pop1 = StudentFactory(config=cfg, seed=42).generate_population(n=50)
        pop2 = StudentFactory(config=cfg, seed=42).generate_population(n=50)
        for p1, p2 in zip(pop1, pop2):
            assert p1.disability_severity == p2.disability_severity

    def test_population_summary_includes_disability(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=50)
        summary = factory.population_summary(pop)
        assert "disability_rate" in summary
