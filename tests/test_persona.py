"""Tests for StudentPersona and BigFiveTraits."""

import uuid

import pytest

from synthed.agents.persona import StudentPersona, BigFiveTraits, PersonaConfig


class TestBigFiveTraits:
    def test_defaults_valid(self):
        traits = BigFiveTraits()
        for name in ["openness", "conscientiousness", "extraversion",
                     "agreeableness", "neuroticism"]:
            val = getattr(traits, name)
            assert 0.0 <= val <= 1.0, f"{name}={val} out of range"

    def test_validation_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            BigFiveTraits(openness=1.5)

        with pytest.raises(ValueError):
            BigFiveTraits(neuroticism=-0.1)


class TestStudentPersona:
    def test_persona_defaults_valid_ranges(self):
        p = StudentPersona()
        assert 0.0 <= p.digital_literacy <= 1.0
        assert 0.0 <= p.self_regulation <= 1.0
        assert 0.0 <= p.financial_stress <= 1.0
        assert 0.0 <= p.self_efficacy <= 1.0
        assert 0.0 <= p.goal_commitment <= 1.0

    def test_derived_attributes_bounded(self):
        p = StudentPersona()
        assert 0.05 <= p.base_engagement_probability <= 0.95
        assert 0.02 <= p.base_dropout_risk <= 0.90

    def test_persona_to_dict_roundtrip(self, sample_persona):
        d = sample_persona.to_dict()
        restored = StudentPersona.from_dict(d)
        assert restored.name == sample_persona.name
        assert restored.age == sample_persona.age
        assert abs(restored.financial_stress - sample_persona.financial_stress) < 1e-9
        assert abs(restored.base_engagement_probability - sample_persona.base_engagement_probability) < 1e-9
        assert abs(restored.personality.conscientiousness - sample_persona.personality.conscientiousness) < 1e-9

    def test_intrinsic_higher_engagement_than_amotivation(self):
        intrinsic = StudentPersona(motivation_type="intrinsic")
        amotivation = StudentPersona(motivation_type="amotivation")
        assert intrinsic.base_engagement_probability > amotivation.base_engagement_probability

    def test_high_stress_higher_dropout_risk(self):
        high_stress = StudentPersona(financial_stress=0.9)
        low_stress = StudentPersona(financial_stress=0.1)
        assert high_stress.base_dropout_risk > low_stress.base_dropout_risk

    def test_derived_attributes_bounded_extremes(self):
        """Even extreme attribute combos stay within declared bounds."""
        low = StudentPersona(
            personality=BigFiveTraits(conscientiousness=0.05, neuroticism=0.95),
            self_regulation=0.05, goal_commitment=0.05, self_efficacy=0.05,
            motivation_type="amotivation", financial_stress=0.95,
            is_employed=True, weekly_work_hours=60,
            has_family_responsibilities=True, perceived_cost_benefit=0.05,
            learner_autonomy=0.05,
        )
        assert low.base_engagement_probability >= 0.05
        assert low.base_dropout_risk <= 0.90

        high = StudentPersona(
            personality=BigFiveTraits(conscientiousness=0.95, neuroticism=0.05),
            self_regulation=0.95, goal_commitment=0.95, self_efficacy=0.95,
            motivation_type="intrinsic", financial_stress=0.05,
            is_employed=False, weekly_work_hours=0,
            has_family_responsibilities=False, perceived_cost_benefit=0.95,
            learner_autonomy=0.95,
        )
        assert high.base_engagement_probability <= 0.95
        assert high.base_dropout_risk >= 0.02


class TestBigFiveToDescription:
    """Tests for BigFiveTraits.to_description() (lines 51-65)."""

    def test_high_traits_described(self):
        """Traits >= 0.7 produce high descriptions."""
        traits = BigFiveTraits(
            openness=0.8, conscientiousness=0.9, extraversion=0.75,
            agreeableness=0.85, neuroticism=0.7,
        )
        desc = traits.to_description()
        assert "curious" in desc
        assert "organized" in desc
        assert "socially active" in desc
        assert "cooperative" in desc
        assert "prone to stress" in desc

    def test_low_traits_described(self):
        """Traits <= 0.3 produce low descriptions."""
        traits = BigFiveTraits(
            openness=0.2, conscientiousness=0.1, extraversion=0.3,
            agreeableness=0.25, neuroticism=0.15,
        )
        desc = traits.to_description()
        assert "routine" in desc
        assert "spontaneous" in desc
        assert "independent study" in desc
        assert "competitive" in desc
        assert "emotionally stable" in desc

    def test_balanced_personality(self):
        """All traits in 0.31-0.69 returns 'balanced personality'."""
        traits = BigFiveTraits(
            openness=0.5, conscientiousness=0.5, extraversion=0.5,
            agreeableness=0.5, neuroticism=0.5,
        )
        desc = traits.to_description()
        assert desc == "balanced personality"

    def test_mixed_traits(self):
        """Some high, some low, some balanced produces partial descriptions."""
        traits = BigFiveTraits(
            openness=0.9, conscientiousness=0.5, extraversion=0.1,
            agreeableness=0.5, neuroticism=0.5,
        )
        desc = traits.to_description()
        assert "curious" in desc
        assert "independent study" in desc
        # Balanced traits should NOT appear
        assert "organized" not in desc
        assert "spontaneous" not in desc


class TestStudentPersonaLevel:
    """Tests for StudentPersona._level() and to_prompt_description() (lines 343-356)."""

    def test_level_high(self):
        assert StudentPersona._level(0.8) == "high"

    def test_level_moderate(self):
        assert StudentPersona._level(0.5) == "moderate"

    def test_level_low(self):
        assert StudentPersona._level(0.3) == "low"

    def test_level_boundary_high(self):
        assert StudentPersona._level(0.71) == "high"
        assert StudentPersona._level(0.7) == "moderate"

    def test_level_boundary_low(self):
        assert StudentPersona._level(0.41) == "moderate"
        assert StudentPersona._level(0.4) == "low"

    def test_to_prompt_description_content(self):
        """to_prompt_description() produces a structured string."""
        p = StudentPersona(
            name="Test",
            age=30,
            gender="female",
            is_employed=True,
            weekly_work_hours=40,
            has_family_responsibilities=True,
            financial_stress=0.8,
            self_regulation=0.3,
            digital_literacy=0.6,
            learner_autonomy=0.4,
            goal_commitment=0.9,
            motivation_type="intrinsic",
            perceived_cost_benefit=0.7,
            personality=BigFiveTraits(
                openness=0.9, conscientiousness=0.2,
                extraversion=0.5, agreeableness=0.5, neuroticism=0.5,
            ),
        )
        desc = p.to_prompt_description()
        assert "Student ID:" in desc
        assert "Age: 30" in desc
        assert "Gender: female" in desc
        assert "employed 40h/wk" in desc
        assert "Family responsibilities: yes" in desc
        assert "Financial stress: high" in desc
        assert "Self-regulation: low" in desc
        assert "Motivation: intrinsic" in desc

    def test_to_prompt_description_unemployed(self):
        """to_prompt_description() with unemployed student."""
        p = StudentPersona(is_employed=False)
        desc = p.to_prompt_description()
        assert "unemployed" in desc


class TestStudentID:
    """Tests for UUIDv7 student ID generation."""

    def test_id_is_valid_uuidv7(self):
        """Student IDs should be valid UUIDv7 (time-sortable, full 128-bit)."""
        p = StudentPersona()
        parsed = uuid.UUID(p.id)
        assert parsed.version == 7
        assert len(p.id) == 36

    def test_id_uniqueness(self):
        """Each StudentPersona should receive a unique ID."""
        ids = [StudentPersona().id for _ in range(100)]
        assert len(set(ids)) == 100

    def test_id_time_sortable(self):
        """UUIDv7 IDs generated in separate ms buckets sort chronologically."""
        import time
        batch_a = [StudentPersona().id for _ in range(5)]
        time.sleep(0.005)
        batch_b = [StudentPersona().id for _ in range(5)]
        assert max(batch_a) < min(batch_b)


class TestDisabilitySeverity:
    def test_disability_default_zero(self):
        assert StudentPersona().disability_severity == 0.0

    def test_disability_severity_accepted(self):
        p = StudentPersona(disability_severity=0.4)
        assert p.disability_severity == 0.4

    def test_disability_rate_config_default(self):
        assert PersonaConfig().disability_rate == 0.10

    def test_disability_rate_validation(self):
        import pytest
        with pytest.raises(ValueError):
            PersonaConfig(disability_rate=-0.1)
        with pytest.raises(ValueError):
            PersonaConfig(disability_rate=1.5)
