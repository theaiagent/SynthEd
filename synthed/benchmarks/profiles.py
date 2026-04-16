"""
Pre-defined benchmark profiles for different ODL contexts.

Each profile represents a typical institutional setting with calibrated
parameters. Profiles can be used to generate reproducible benchmark
datasets for research comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..agents.persona import PersonaConfig
from ..simulation.environment import ODLEnvironment
from ..simulation.grading import GradingConfig
from ..simulation.institutional import InstitutionalConfig
from ..validation import ReferenceStatistics


@dataclass(frozen=True)
class BenchmarkProfile:
    """An immutable benchmark configuration."""
    name: str
    description: str
    persona_config: PersonaConfig
    institutional_config: InstitutionalConfig
    environment: ODLEnvironment
    reference_stats: ReferenceStatistics
    n_students: int
    seed: int
    expected_dropout_range: tuple[float, float]
    grading_config: GradingConfig = GradingConfig()


PROFILES: dict[str, BenchmarkProfile] = {
    "default": BenchmarkProfile(
        name="default",
        description="Default ODL profile: large-scale, diverse student population",
        persona_config=PersonaConfig(
            age_range=(18, 60),
            employment_rate=0.69,
            has_family_rate=0.55,
            financial_stress_mean=0.55,
            digital_literacy_mean=0.45,
            self_regulation_mean=0.40,
            dropout_base_rate=0.46,
        ),
        institutional_config=InstitutionalConfig(
            instructional_design_quality=0.50,
            teaching_presence_baseline=0.45,
            support_services_quality=0.40,
            technology_quality=0.60,
            curriculum_flexibility=0.40,
        ),
        grading_config=GradingConfig(
            distribution="beta", dist_alpha=3.0, dist_beta=3.0,
            midterm_weight=0.30, final_weight=0.70,
            midterm_components={"exam": 0.60, "assignment": 0.40},
            pass_threshold=0.65, distinction_threshold=0.73,
        ),
        environment=ODLEnvironment(total_weeks=14),
        reference_stats=ReferenceStatistics(
            dropout_rate=0.312, gpa_mean=3.03, gpa_std=0.75, age_mean=30.0, age_std=10.0
        ),
        n_students=1000,
        seed=42,
        expected_dropout_range=(0.20, 0.45),
    ),
}
