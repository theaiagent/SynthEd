"""Shared fixtures for the SynthEd test suite."""

import pytest

from synthed.agents.persona import StudentPersona, BigFiveTraits
from synthed.agents.factory import StudentFactory
from synthed.simulation.environment import ODLEnvironment


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-k not slow')")


@pytest.fixture
def sample_persona():
    """A moderate-attribute StudentPersona for general tests."""
    return StudentPersona(
        name="Test Student",
        age=28,
        gender="female",
        personality=BigFiveTraits(
            openness=0.5, conscientiousness=0.5,
            extraversion=0.5, agreeableness=0.5, neuroticism=0.5,
        ),
        prior_gpa=2.5,
        goal_commitment=0.6,
        digital_literacy=0.6,
        self_regulation=0.5,
        time_management=0.5,
        learner_autonomy=0.5,
        employment_intensity=0.5,
        family_responsibility_level=0.0,
        financial_stress=0.3,
        self_efficacy=0.6,
        motivation_type="extrinsic",
        perceived_cost_benefit=0.6,
        academic_integration=0.5,
        social_integration=0.3,
    )


@pytest.fixture
def high_risk_persona():
    """High dropout risk: employed, family, high financial stress, amotivation."""
    return StudentPersona(
        name="High Risk",
        age=35,
        gender="male",
        personality=BigFiveTraits(conscientiousness=0.2, neuroticism=0.8),
        employment_intensity=0.83,
        family_responsibility_level=0.8,
        financial_stress=0.9,
        self_regulation=0.2,
        motivation_type="amotivation",
        goal_commitment=0.2,
        self_efficacy=0.2,
        perceived_cost_benefit=0.2,
        learner_autonomy=0.2,
        digital_literacy=0.3,
    )


@pytest.fixture
def low_risk_persona():
    """Low dropout risk: intrinsic motivation, high self-regulation, no family."""
    return StudentPersona(
        name="Low Risk",
        age=22,
        gender="female",
        personality=BigFiveTraits(conscientiousness=0.9, neuroticism=0.1),
        employment_intensity=0.0,
        family_responsibility_level=0.0,
        financial_stress=0.1,
        self_regulation=0.9,
        motivation_type="intrinsic",
        goal_commitment=0.9,
        self_efficacy=0.9,
        perceived_cost_benefit=0.9,
        learner_autonomy=0.8,
        digital_literacy=0.9,
    )


@pytest.fixture
def default_environment():
    """Default ODLEnvironment with 4 courses and 14 weeks."""
    return ODLEnvironment()


@pytest.fixture
def sample_population():
    """Factory-generated population of 20 students, seed=42."""
    factory = StudentFactory(seed=42)
    return factory.generate_population(n=20)
