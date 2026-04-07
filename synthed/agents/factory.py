"""
StudentFactory: Population-level persona generation calibrated to target distributions.

Generates student populations whose aggregate statistics match configurable
target distributions. Each persona attribute is mapped to its theoretical
origin (Tinto, Bean & Metzner, Kember, Rovai, Bäulke et al.).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from dataclasses import replace

from .persona import StudentPersona, BigFiveTraits, PersonaConfig, _CALIBRATED_DROPOUT_BASE_RATE
from .backstory_templates import (
    select_template, select_life_event, select_regional_context,
    build_enrichment_prompt,
)
from .name_pools import select_name, select_country_context
from ..utils.llm import LLMClient, LLMError, LLMResponseError

logger = logging.getLogger(__name__)


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
        # Isolated RNG for name generation — spawned from SeedSequence so the
        # name stream is cryptographically independent from self.rng without
        # any magic-number offset or collision risk.
        self._name_rng = np.random.default_rng(
            np.random.SeedSequence(seed).spawn(1)[0]
        )

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

        scaled = self._apply_dropout_scaling(personas)
        return self._assign_display_ids(scaled)

    def _apply_dropout_scaling(
        self, personas: list[StudentPersona],
    ) -> list[StudentPersona]:
        """Scale base_dropout_risk proportionally to dropout_base_rate.

        Uses _dropout_risk_scale field on StudentPersona so that
        dataclasses.replace() preserves the scaling through __post_init__.
        """
        scale = self.config.dropout_base_rate / _CALIBRATED_DROPOUT_BASE_RATE
        if abs(scale - 1.0) < 1e-9:
            return personas
        return [replace(p, _dropout_risk_scale=scale) for p in personas]

    @staticmethod
    def _assign_display_ids(personas: list[StudentPersona]) -> list[StudentPersona]:
        """Assign sequential human-readable display IDs (S-0001, S-0002, ...)."""
        return [
            replace(p, display_id=f"S-{i:04d}")
            for i, p in enumerate(personas, start=1)
        ]

    def _generate_single(self, index: int) -> StudentPersona:
        cfg = self.config

        # ── Identity ──
        gender = self.rng.choice(
            list(cfg.gender_distribution.keys()),
            p=list(cfg.gender_distribution.values()),
        )
        if cfg.generate_names:
            country_ctx = select_country_context(self._name_rng)
            first, last = select_name(self._name_rng, gender, country_ctx)
            name = f"{first} {last}"
        else:
            name = ""
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
            list(cfg.socioeconomic_distribution.keys()),
            p=list(cfg.socioeconomic_distribution.values()),
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
            list(cfg.prior_education_distribution.keys()),
            p=list(cfg.prior_education_distribution.values()),
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
            list(cfg.goal_orientation_distribution.keys()),
            p=list(cfg.goal_orientation_distribution.values()),
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
            list(cfg.device_distribution.keys()),
            p=list(cfg.device_distribution.values()),
        )
        learning_style = self.rng.choice(
            list(cfg.learning_style_distribution.keys()),
            p=list(cfg.learning_style_distribution.values()),
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

        persona = StudentPersona(
            name=name,
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

        # Disability severity — drawn AFTER all other attributes (Option B: RNG isolation)
        if self.rng.random() < cfg.disability_rate:
            severity = float(np.clip(self.rng.beta(2, 5), 0.05, 0.95))
            new_dl = round(float(np.clip(
                persona.digital_literacy - severity * 0.15, 0.05, 0.95
            )), 2)
            new_tm = round(float(np.clip(
                persona.time_management - severity * 0.10, 0.05, 0.95
            )), 2)
            persona = replace(persona, disability_severity=round(severity, 2),
                              digital_literacy=new_dl, time_management=new_tm)

        return persona

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

    _MIN_BACKSTORY_LENGTH = 20

    def _enrich_with_llm(self, persona: StudentPersona) -> StudentPersona:
        """Enrich a persona with an LLM-generated backstory.

        Uses the template system to produce diverse narrative prompts.
        Validates the LLM response for expected keys and content quality.
        On any failure, logs a warning and returns the persona unchanged
        (empty backstory) so the pipeline continues without crashing.
        """
        template = select_template(self.rng)
        life_event = select_life_event(self.rng)
        regional_ctx = select_regional_context(self.rng)
        messages = build_enrichment_prompt(persona, template, life_event, regional_ctx)

        try:
            result = self.llm.chat_json(messages, temperature=0.7)
        except (LLMError, LLMResponseError) as exc:
            logger.warning("LLM enrichment failed for %s: %s", persona.id, exc)
            return persona
        except Exception as exc:
            logger.warning("Unexpected LLM error for %s: %s", persona.id, exc)
            return persona

        # Validate response contains expected key
        if not isinstance(result, dict):
            logger.warning(
                "LLM returned non-dict for %s: %s", persona.id, type(result).__name__
            )
            return persona

        backstory = result.get("backstory")
        if not isinstance(backstory, str) or not backstory.strip():
            logger.warning(
                "LLM returned missing/empty backstory for %s", persona.id
            )
            return persona

        backstory = backstory.strip()

        # Validate backstory is not garbage (too short or placeholder)
        if len(backstory) < self._MIN_BACKSTORY_LENGTH:
            logger.warning(
                "LLM backstory too short for %s (%d chars): %s",
                persona.id, len(backstory), backstory,
            )
            return persona

        return replace(persona, backstory=backstory)

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
            # Disability (Rovai, 2003: accessibility)
            "disability_rate": sum(1 for p in personas if p.disability_severity > 0) / n,
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

