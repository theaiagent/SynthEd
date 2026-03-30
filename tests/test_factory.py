"""Tests for StudentFactory population generation."""

from synthed.agents.factory import StudentFactory


class TestStudentFactory:
    def test_generate_population_count(self):
        factory = StudentFactory(seed=42)
        pop = factory.generate_population(n=50)
        assert len(pop) == 50

    def test_deterministic_with_seed(self):
        pop1 = StudentFactory(seed=42).generate_population(n=10)
        pop2 = StudentFactory(seed=42).generate_population(n=10)
        for p1, p2 in zip(pop1, pop2):
            assert p1.name == p2.name
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
