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
from ..validation.validator import ReferenceStatistics


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
    "high_dropout_developing": BenchmarkProfile(
        name="high_dropout_developing",
        description="Developing country ODL: high dropout (55-75%), high employment, low digital literacy",
        persona_config=PersonaConfig(
            employment_rate=0.85,
            financial_stress_mean=0.65,
            digital_literacy_mean=0.35,
            self_regulation_mean=0.35,
            dropout_base_rate=0.92,
        ),
        institutional_config=InstitutionalConfig(
            instructional_design_quality=0.30,
            teaching_presence_baseline=0.35,
            support_services_quality=0.25,
            technology_quality=0.35,
            curriculum_flexibility=0.25,
        ),
        grading_config=GradingConfig(
            distribution="beta", dist_alpha=3.0, dist_beta=4.0,
            midterm_weight=0.30, final_weight=0.70,
            midterm_components={"exam": 0.60, "assignment": 0.40},
            exam_eligibility_threshold=0.30,
        ),
        environment=ODLEnvironment(total_weeks=14),
        reference_stats=ReferenceStatistics(dropout_rate=0.65),
        n_students=500,
        seed=42,
        expected_dropout_range=(0.55, 0.80),
    ),
    "moderate_dropout_western": BenchmarkProfile(
        name="moderate_dropout_western",
        description="Western university ODL: moderate dropout (15-35%), mixed employment",
        persona_config=PersonaConfig(
            employment_rate=0.55,
            financial_stress_mean=0.45,
            digital_literacy_mean=0.65,
            self_regulation_mean=0.45,
            dropout_base_rate=0.65,
        ),
        institutional_config=InstitutionalConfig(
            instructional_design_quality=0.65,
            teaching_presence_baseline=0.60,
            support_services_quality=0.65,
            technology_quality=0.75,
            curriculum_flexibility=0.60,
        ),
        grading_config=GradingConfig(
            distribution="beta", dist_alpha=6.0, dist_beta=2.0,
            midterm_weight=0.50, final_weight=0.50,
            midterm_components={"assignment": 1.0},
            dual_hurdle=True,
            component_pass_thresholds={"midterm": 0.40, "final": 0.40},
        ),
        environment=ODLEnvironment(total_weeks=14),
        reference_stats=ReferenceStatistics(dropout_rate=0.25, age_mean=26.0),
        n_students=500,
        seed=42,
        expected_dropout_range=(0.15, 0.35),
    ),
    "low_dropout_corporate": BenchmarkProfile(
        name="low_dropout_corporate",
        description="Corporate training ODL: low dropout (5-25%), employer-sponsored",
        persona_config=PersonaConfig(
            employment_rate=0.95,
            financial_stress_mean=0.20,
            digital_literacy_mean=0.75,
            self_regulation_mean=0.65,
            dropout_base_rate=0.25,
            has_family_rate=0.45,
        ),
        institutional_config=InstitutionalConfig(
            instructional_design_quality=0.85,
            teaching_presence_baseline=0.80,
            support_services_quality=0.90,
            technology_quality=0.90,
            curriculum_flexibility=0.80,
        ),
        grading_config=GradingConfig(
            assessment_mode="exam_only",
            midterm_weight=0.0, final_weight=1.0,
            midterm_components={},
            distribution="beta", dist_alpha=8.0, dist_beta=2.0,
            pass_threshold=0.85,
            distinction_threshold=0.97,
        ),
        environment=ODLEnvironment(total_weeks=14),
        reference_stats=ReferenceStatistics(
            dropout_rate=0.15, employment_rate=0.95, age_mean=32.0
        ),
        n_students=300,
        seed=42,
        expected_dropout_range=(0.01, 0.25),
    ),
    "mega_university": BenchmarkProfile(
        name="mega_university",
        description="Mega university: very high enrollment, elevated dropout (35-60%)",
        persona_config=PersonaConfig(
            age_range=(18, 60),
            employment_rate=0.80,
            has_family_rate=0.55,
            financial_stress_mean=0.55,
            digital_literacy_mean=0.45,
            self_regulation_mean=0.40,
            dropout_base_rate=0.90,
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
        ),
        environment=ODLEnvironment(total_weeks=14),
        reference_stats=ReferenceStatistics(
            dropout_rate=0.42, age_mean=30.0, age_std=10.0
        ),
        n_students=1000,
        seed=42,
        expected_dropout_range=(0.35, 0.60),
    ),
}
