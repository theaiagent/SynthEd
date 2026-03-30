"""
StudentFactory: Population-level persona generation calibrated to target distributions.

Generates student populations whose aggregate statistics match configurable
target distributions. Each persona attribute is mapped to its theoretical
origin (Tinto, Bean & Metzner, Kember, Rovai, Bäulke et al.).
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

import numpy as np

from .persona import StudentPersona, BigFiveTraits, PersonaConfig
from ..utils.llm import LLMClient


FIRST_NAMES = {
    "male": ["James", "Ahmed", "Carlos", "Wei", "Dmitri", "Kofi", "Raj", "Mehmet",
             "Lucas", "Omar", "Yuki", "Daniel", "Emre", "Kenji", "Ali"],
    "female": ["Sarah", "Fatima", "Maria", "Ling", "Olga", "Amara", "Priya", "Ayşe",
               "Emma", "Layla", "Sakura", "Sophie", "Elif", "Mina", "Ana"],
}
LAST_NAMES = [
    "Anderson", "Yılmaz", "Chen", "Müller", "Santos", "Okafor", "Sharma", "Petrov",
    "Nakamura", "Al-Farsi", "Kim", "García", "Nguyen", "Johansson", "Osei",
]


class StudentFactory:
    """
    Generates a calibrated population of StudentPersona instances.

    Attribute correlations reflect established theoretical relationships:
    - Conscientiousness ↔ self-regulation (r ≈ 0.5, Bidjerano & Dai, 2007)
    - Financial stress ↔ employment hours (positive)
    - Self-efficacy ↔ prior GPA + conscientiousness (Bandura, 1997)
    - Goal commitment ↔ motivation type (SDT; Deci & Ryan, 1985)
    - Perceived cost-benefit ↔ financial stress (inverse; Kember, 1989)
    """

    def __init__(
        self,
        config: PersonaConfig | None = None,
        llm_client: LLMClient | None = None,
        seed: int = 42,
    ):
        self.config = config or PersonaConfig()
        self.llm = llm_client
        self.rng = np.random.default_rng(seed)
        random.seed(seed)

    def generate_population(
        self,
        n: int = 100,
        enrich_with_llm: bool = False,
    ) -> list[StudentPersona]:
        personas = []
        for i in range(n):
            persona = self._generate_single(i)
            if enrich_with_llm and self.llm:
                persona = self._enrich_with_llm(persona)
            personas.append(persona)
        return personas

    def _generate_single(self, index: int) -> StudentPersona:
        cfg = self.config

        # ── Identity ──
        gender = self.rng.choice(
            list(cfg.gender_distribution.keys()),
            p=list(cfg.gender_distribution.values()),
        )
        first = random.choice(FIRST_NAMES[gender])
        last = random.choice(LAST_NAMES)
        age = int(self.rng.beta(2, 5) * (cfg.age_range[1] - cfg.age_range[0])
                  + cfg.age_range[0])

        # ── Big Five Personality ──
        big_five = self._sample_big_five()

        # ── CLUSTER 3: External Factors (Bean & Metzner) ──
        is_employed = self.rng.random() < cfg.employment_rate
        weekly_work_hours = int(self.rng.normal(35, 10)) if is_employed else 0
        weekly_work_hours = max(0, min(60, weekly_work_hours))
        has_family = self.rng.random() < cfg.has_family_rate

        socioeconomic_level = self.rng.choice(
            ["low", "middle", "high"], p=[0.30, 0.50, 0.20]
        )

        # Financial stress: correlated with SES and employment (Bean & Metzner)
        ses_offset = {"low": 0.25, "middle": 0.0, "high": -0.20}[socioeconomic_level]
        family_offset = 0.10 if has_family else 0.0
        financial_stress = float(np.clip(
            self.rng.normal(cfg.financial_stress_mean + ses_offset + family_offset, 0.18),
            0.0, 1.0
        ))

        # ── CLUSTER 1: Student Characteristics (Tinto, Kember) ──
        prior_gpa = float(np.clip(
            self.rng.normal(cfg.prior_gpa_mean, cfg.prior_gpa_std), 0.0, 4.0
        ))
        prior_education = self.rng.choice(
            ["high_school", "associate", "bachelor"], p=[0.50, 0.30, 0.20]
        )
        years_since = max(0, int(self.rng.exponential(4)))
        enrolled_courses = max(1, min(6, int(self.rng.normal(3.5, 1.2))))

        # Motivation (SDT — Deci & Ryan, 1985)
        motivation_type = self.rng.choice(
            list(cfg.motivation_levels.keys()),
            p=list(cfg.motivation_levels.values()),
        )

        # Goal commitment: correlated with motivation (Tinto)
        motivation_boost = {"intrinsic": 0.15, "extrinsic": 0.0, "amotivation": -0.20}[motivation_type]
        goal_commitment = float(np.clip(
            self.rng.normal(0.55 + motivation_boost, 0.15), 0.05, 0.95
        ))

        # ODE beliefs: slightly correlated with prior ODE experience / age
        ode_beliefs = float(np.clip(
            self.rng.normal(0.5, 0.18) + (0.05 if age > 30 else 0.0), 0.05, 0.95
        ))

        goal_orientation = self.rng.choice(
            ["mastery", "performance", "avoidance"],
            p=[0.35, 0.40, 0.25],
        )

        # ── CLUSTER 2: Student Skills (Rovai) ──
        digital_literacy = float(np.clip(
            self.rng.normal(cfg.digital_literacy_mean, cfg.digital_literacy_std), 0.0, 1.0
        ))

        # Self-regulation: correlated with conscientiousness (r ≈ 0.5)
        self_regulation = float(np.clip(
            0.5 * big_five.conscientiousness
            + 0.5 * self.rng.normal(cfg.self_regulation_mean, cfg.self_regulation_std),
            0.05, 0.95
        ))

        # Time management: correlated with self-regulation and conscientiousness
        time_management = float(np.clip(
            0.4 * self_regulation
            + 0.3 * big_five.conscientiousness
            + 0.3 * self.rng.normal(0.5, 0.15),
            0.05, 0.95
        ))

        # Learner autonomy (Moore, 1993): correlated with self-regulation, openness, age
        age_factor = 0.05 if age > 30 else 0.0
        learner_autonomy = float(np.clip(
            0.4 * self_regulation
            + 0.2 * big_five.openness
            + 0.4 * self.rng.normal(0.5, 0.15)
            + age_factor,
            0.05, 0.95
        ))

        # Academic reading/writing: correlated with prior education
        edu_boost = {"high_school": 0.0, "associate": 0.08, "bachelor": 0.15}[prior_education]
        academic_rw = float(np.clip(
            self.rng.normal(0.55 + edu_boost, 0.15), 0.1, 0.95
        ))

        has_internet = self.rng.random() < (0.95 if socioeconomic_level != "low" else 0.75)
        device = self.rng.choice(
            ["laptop", "desktop", "mobile", "tablet"],
            p=[0.40, 0.15, 0.35, 0.10],
        )
        learning_style = self.rng.choice(
            ["visual", "auditory", "reading", "kinesthetic"],
            p=[0.35, 0.20, 0.30, 0.15],
        )

        # ── CLUSTER 4: Internal Factors (Tinto, Rovai) ──
        # Self-efficacy: correlated with conscientiousness + prior GPA (Bandura, 1997)
        self_efficacy = float(np.clip(
            0.3 * big_five.conscientiousness
            + 0.3 * (prior_gpa / 4.0)
            + 0.4 * self.rng.normal(0.5, 0.15),
            0.05, 0.95
        ))

        # Academic integration: starts moderate, shaped by prior experience (Tinto)
        academic_integration = float(np.clip(
            self.rng.normal(0.45, 0.15)
            + 0.1 * (prior_gpa / 4.0)
            - 0.02 * min(years_since, 10),
            0.05, 0.95
        ))

        # Social integration: generally LOW in ODE (Bean & Metzner's key insight)
        social_integration = float(np.clip(
            self.rng.normal(0.30, 0.15)
            + big_five.extraversion * 0.10,
            0.05, 0.80  # Capped — ODE has limited social integration pathways
        ))

        # Institutional support access (Rovai): correlates with digital literacy
        inst_support = float(np.clip(
            self.rng.normal(0.5, 0.15)
            + digital_literacy * 0.1,
            0.1, 0.95
        ))

        # Perceived cost-benefit (Kember, Economic Rationality):
        # Inversely related to financial stress, positively to goal commitment
        perceived_cb = float(np.clip(
            0.3 * goal_commitment
            + 0.3 * (1 - financial_stress)
            + 0.2 * ode_beliefs
            + 0.2 * self.rng.normal(0.5, 0.12),
            0.05, 0.95
        ))

        return StudentPersona(
            name=f"{first} {last}",
            age=age,
            gender=gender,
            personality=big_five,
            prior_gpa=round(prior_gpa, 2),
            prior_education_level=prior_education,
            years_since_last_education=years_since,
            enrolled_courses=enrolled_courses,
            goal_commitment=round(goal_commitment, 2),
            ode_beliefs=round(ode_beliefs, 2),
            digital_literacy=round(digital_literacy, 2),
            self_regulation=round(self_regulation, 2),
            time_management=round(time_management, 2),
            learner_autonomy=round(learner_autonomy, 2),
            academic_reading_writing=round(academic_rw, 2),
            has_reliable_internet=has_internet,
            device_type=device,
            preferred_learning_style=learning_style,
            is_employed=is_employed,
            weekly_work_hours=weekly_work_hours,
            has_family_responsibilities=has_family,
            financial_stress=round(financial_stress, 2),
            socioeconomic_level=socioeconomic_level,
            perceived_cost_benefit=round(perceived_cb, 2),
            academic_integration=round(academic_integration, 2),
            social_integration=round(social_integration, 2),
            institutional_support_access=round(inst_support, 2),
            self_efficacy=round(self_efficacy, 2),
            motivation_type=motivation_type,
            goal_orientation=goal_orientation,
        )

    def _sample_big_five(self) -> BigFiveTraits:
        base = self.rng.normal(0.5, 0.15, size=5)
        o, c, e, a, n = base
        n = n - 0.3 * (c - 0.5)  # C–N negative correlation
        a = a + 0.2 * (e - 0.5)  # E–A positive correlation
        return BigFiveTraits(
            openness=float(np.clip(o, 0.05, 0.95)),
            conscientiousness=float(np.clip(c, 0.05, 0.95)),
            extraversion=float(np.clip(e, 0.05, 0.95)),
            agreeableness=float(np.clip(a, 0.05, 0.95)),
            neuroticism=float(np.clip(n, 0.05, 0.95)),
        )

    def _enrich_with_llm(self, persona: StudentPersona) -> StudentPersona:
        prompt = f"""You are generating a backstory for a synthetic ODL student persona.
Based on these attributes, write 2-3 sentences explaining WHY this student
chose distance learning and what challenges they face.

Profile:
- {persona.name}, {persona.age}yo, {persona.gender}
- Employment: {'Employed ' + str(persona.weekly_work_hours) + 'h/wk' if persona.is_employed else 'Unemployed'}
- Family: {'Has family responsibilities' if persona.has_family_responsibilities else 'No family duties'}
- Financial stress: {persona.financial_stress:.0%}
- Prior: {persona.prior_education_level} (GPA {persona.prior_gpa:.1f}), {persona.years_since_last_education}y gap
- Motivation: {persona.motivation_type}, Goal commitment: {persona.goal_commitment:.0%}
- Self-regulation: {persona.self_regulation:.0%}, Digital literacy: {persona.digital_literacy:.0%}
- Personality: {persona.personality.to_description()}

Return JSON: {{"backstory": "...", "primary_challenge": "..."}}
"""
        try:
            result = self.llm.chat_json([
                {"role": "system", "content": "Synthetic persona generator for educational research. Return valid JSON."},
                {"role": "user", "content": prompt},
            ], temperature=0.9)
            persona.backstory = result.get("backstory", "")
        except Exception as e:
            logger.warning("LLM enrichment failed for %s: %s", persona.name, e)
        return persona

    def population_summary(self, personas: list[StudentPersona]) -> dict[str, Any]:
        n = len(personas)
        return {
            "total_students": n,
            # Demographics
            "age_mean": float(np.mean([p.age for p in personas])),
            "age_std": float(np.std([p.age for p in personas])),
            "gender_distribution": {
                g: sum(1 for p in personas if p.gender == g) / n
                for g in set(p.gender for p in personas)
            },
            # External factors (Bean & Metzner)
            "employment_rate": sum(1 for p in personas if p.is_employed) / n,
            "family_responsibility_rate": sum(1 for p in personas if p.has_family_responsibilities) / n,
            "financial_stress_mean": float(np.mean([p.financial_stress for p in personas])),
            # Student characteristics (Tinto)
            "gpa_mean": float(np.mean([p.prior_gpa for p in personas])),
            "gpa_std": float(np.std([p.prior_gpa for p in personas])),
            "goal_commitment_mean": float(np.mean([p.goal_commitment for p in personas])),
            "motivation_distribution": {
                m: sum(1 for p in personas if p.motivation_type == m) / n
                for m in set(p.motivation_type for p in personas)
            },
            # Student skills (Rovai)
            "digital_literacy_mean": float(np.mean([p.digital_literacy for p in personas])),
            "self_regulation_mean": float(np.mean([p.self_regulation for p in personas])),
            "learner_autonomy_mean": float(np.mean([p.learner_autonomy for p in personas])),
            # Internal factors
            "academic_integration_mean": float(np.mean([p.academic_integration for p in personas])),
            "social_integration_mean": float(np.mean([p.social_integration for p in personas])),
            "self_efficacy_mean": float(np.mean([p.self_efficacy for p in personas])),
            # Derived
            "base_engagement_mean": float(np.mean([p.base_engagement_probability for p in personas])),
            "base_dropout_risk_mean": float(np.mean([p.base_dropout_risk for p in personas])),
        }
