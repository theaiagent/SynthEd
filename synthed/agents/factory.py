"""
StudentFactory: Population-level persona generation calibrated to target distributions.

Inspired by TinyTroupe's TinyPersonFactory, this module generates
student populations whose aggregate statistics match configurable
target distributions (age, gender, GPA, motivation, etc.).
"""

from __future__ import annotations

import json
import random
from typing import Any

import numpy as np

from .persona import StudentPersona, BigFiveTraits, PersonaConfig
from ..utils.llm import LLMClient


# Common names pool for synthetic personas
FIRST_NAMES = {
    "male": ["James", "Ahmed", "Carlos", "Wei", "Dmitri", "Kofi", "Raj", "Mehmet",
             "Lucas", "Omar", "Yuki", "Daniel", "Emre", "Kenji", "Ali"],
    "female": ["Sarah", "Fatima", "Maria", "Ling", "Olga", "Amara", "Priya", "Ayşe",
               "Emma", "Layla", "Sakura", "Sophie", "Elif", "Mina", "Ana"],
    "other": ["Alex", "Jordan", "Sam", "Robin", "Taylor", "Morgan", "Avery", "Riley"],
}

LAST_NAMES = [
    "Anderson", "Yılmaz", "Chen", "Müller", "Santos", "Okafor", "Sharma", "Petrov",
    "Nakamura", "Al-Farsi", "Kim", "García", "Nguyen", "Johansson", "Osei",
]


class StudentFactory:
    """
    Generates a calibrated population of StudentPersona instances.

    Uses statistical sampling to match target distributions, with optional
    LLM enrichment for generating narrative backstories and behavioral nuance.
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
        """
        Generate n student personas calibrated to config distributions.

        Args:
            n: Number of students to generate.
            enrich_with_llm: If True, use LLM to add narrative depth (slower, costs API).

        Returns:
            List of StudentPersona instances.
        """
        personas = []
        for i in range(n):
            persona = self._generate_single(i)
            if enrich_with_llm and self.llm:
                persona = self._enrich_with_llm(persona)
            personas.append(persona)
        return personas

    def _generate_single(self, index: int) -> StudentPersona:
        """Generate a single persona using statistical sampling."""
        # Gender
        gender = self.rng.choice(
            list(self.config.gender_distribution.keys()),
            p=list(self.config.gender_distribution.values()),
        )

        # Name
        first = random.choice(FIRST_NAMES.get(gender, FIRST_NAMES["other"]))
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"

        # Age (skewed distribution typical of ODL)
        age = int(self.rng.beta(2, 5) * (self.config.age_range[1] - self.config.age_range[0])
                  + self.config.age_range[0])

        # Big Five (normal distributions with slight correlations)
        big_five = self._sample_big_five()

        # Employment
        is_employed = self.rng.random() < self.config.employment_rate
        weekly_work_hours = int(self.rng.normal(35, 10)) if is_employed else 0
        weekly_work_hours = max(0, min(60, weekly_work_hours))

        # Family
        has_family = self.rng.random() < self.config.has_family_rate

        # Socioeconomic level
        socioeconomic_level = self.rng.choice(
            ["low", "middle", "high"], p=[0.30, 0.50, 0.20]
        )

        # Academic background
        prior_gpa = float(np.clip(
            self.rng.normal(self.config.prior_gpa_mean, self.config.prior_gpa_std),
            0.0, 4.0
        ))
        prior_education = self.rng.choice(
            ["high_school", "associate", "bachelor"], p=[0.50, 0.30, 0.20]
        )
        years_since = max(0, int(self.rng.exponential(4)))

        # Digital literacy
        digital_literacy = float(np.clip(
            self.rng.normal(self.config.digital_literacy_mean, self.config.digital_literacy_std),
            0.0, 1.0
        ))

        # Learning preferences
        learning_style = self.rng.choice(
            ["visual", "auditory", "reading", "kinesthetic"],
            p=[0.35, 0.20, 0.30, 0.15],
        )
        has_internet = self.rng.random() < (0.95 if socioeconomic_level != "low" else 0.75)
        device = self.rng.choice(
            ["laptop", "desktop", "mobile", "tablet"],
            p=[0.40, 0.15, 0.35, 0.10],
        )

        # Motivation (Self-Determination Theory)
        motivation_type = self.rng.choice(
            list(self.config.motivation_levels.keys()),
            p=list(self.config.motivation_levels.values()),
        )
        goal_orientation = self.rng.choice(
            ["mastery", "performance", "avoidance"],
            p=[0.35, 0.40, 0.25],
        )

        # Self-efficacy (correlated with conscientiousness and prior GPA)
        self_efficacy = float(np.clip(
            0.3 * big_five.conscientiousness
            + 0.3 * (prior_gpa / 4.0)
            + 0.4 * self.rng.normal(0.5, 0.15),
            0.0, 1.0
        ))

        # Enrolled courses (ODL students often take fewer)
        enrolled_courses = max(1, min(6, int(self.rng.normal(3.5, 1.2))))

        return StudentPersona(
            name=name,
            age=age,
            gender=gender,
            personality=big_five,
            is_employed=is_employed,
            weekly_work_hours=weekly_work_hours,
            has_family_responsibilities=has_family,
            socioeconomic_level=socioeconomic_level,
            prior_gpa=round(prior_gpa, 2),
            prior_education_level=prior_education,
            years_since_last_education=years_since,
            enrolled_courses=enrolled_courses,
            digital_literacy=round(digital_literacy, 2),
            preferred_learning_style=learning_style,
            has_reliable_internet=has_internet,
            device_type=device,
            motivation_type=motivation_type,
            goal_orientation=goal_orientation,
            self_efficacy=round(self_efficacy, 2),
        )

    def _sample_big_five(self) -> BigFiveTraits:
        """Sample Big Five traits with realistic inter-trait correlations."""
        # Approximate correlation structure from personality psychology literature
        # C and N are negatively correlated; A and E are positively correlated
        base = self.rng.normal(0.5, 0.15, size=5)
        o, c, e, a, n = base

        # Apply soft correlations
        n = n - 0.3 * (c - 0.5)  # High C → lower N
        a = a + 0.2 * (e - 0.5)  # High E → slightly higher A

        return BigFiveTraits(
            openness=float(np.clip(o, 0.05, 0.95)),
            conscientiousness=float(np.clip(c, 0.05, 0.95)),
            extraversion=float(np.clip(e, 0.05, 0.95)),
            agreeableness=float(np.clip(a, 0.05, 0.95)),
            neuroticism=float(np.clip(n, 0.05, 0.95)),
        )

    def _enrich_with_llm(self, persona: StudentPersona) -> StudentPersona:
        """Use LLM to add narrative backstory and behavioral nuance."""
        prompt = f"""You are generating a detailed backstory for a synthetic student persona
in an Open and Distance Learning (ODL) program. Based on the following attributes,
create a brief (2-3 sentence) backstory that explains WHY this student chose distance
learning and what challenges they face.

Student Profile:
- Name: {persona.name}, Age: {persona.age}, Gender: {persona.gender}
- Employment: {'Employed, ' + str(persona.weekly_work_hours) + 'h/week' if persona.is_employed else 'Unemployed'}
- Family: {'Has family responsibilities' if persona.has_family_responsibilities else 'No family responsibilities'}
- Prior Education: {persona.prior_education_level} (GPA: {persona.prior_gpa:.1f})
- Motivation: {persona.motivation_type}
- Personality: {persona.personality.to_description()}

Return JSON with keys: "backstory" (string), "study_habit" (string: one of "regular", "cramming", "sporadic"), "risk_factor" (string: main challenge).
"""
        try:
            result = self.llm.chat_json([
                {"role": "system", "content": "You are a synthetic persona generator for educational research. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ], temperature=0.9)

            persona.add_memory(
                week=0,
                event_type="backstory",
                details=result.get("backstory", ""),
                impact=0.0,
            )
        except Exception:
            pass  # Graceful degradation: persona works without LLM enrichment

        return persona

    def population_summary(self, personas: list[StudentPersona]) -> dict[str, Any]:
        """Generate aggregate statistics for a population."""
        n = len(personas)
        return {
            "total_students": n,
            "age_mean": np.mean([p.age for p in personas]),
            "age_std": np.std([p.age for p in personas]),
            "gender_distribution": {
                g: sum(1 for p in personas if p.gender == g) / n
                for g in set(p.gender for p in personas)
            },
            "employment_rate": sum(1 for p in personas if p.is_employed) / n,
            "family_responsibility_rate": sum(1 for p in personas if p.has_family_responsibilities) / n,
            "gpa_mean": np.mean([p.prior_gpa for p in personas]),
            "gpa_std": np.std([p.prior_gpa for p in personas]),
            "digital_literacy_mean": np.mean([p.digital_literacy for p in personas]),
            "motivation_distribution": {
                m: sum(1 for p in personas if p.motivation_type == m) / n
                for m in set(p.motivation_type for p in personas)
            },
            "base_engagement_mean": np.mean([p.base_engagement_probability for p in personas]),
            "base_dropout_risk_mean": np.mean([p.base_dropout_risk for p in personas]),
        }
