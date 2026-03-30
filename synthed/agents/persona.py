"""
StudentPersona: Theory-grounded persona model for ODL student agents.

Attribute structure is organized around nine established theoretical anchors
from the ODL dropout literature:

1. Tinto (1975) — Academic & social integration
2. Bean & Metzner (1985) — Environmental factors for non-traditional students
3. Kember (1989) — Cost-benefit analysis in distance education
4. Rovai (2003) — Accessibility & digital skills in online learning
5. Bäulke et al. — Phase-oriented view of dropout
6. Economic rationality — Cost-benefit decision-making
7. Moore (1993) — Transactional distance (structure, dialogue, autonomy)
8. Garrison et al. (2000) — Community of Inquiry (social, cognitive, teaching presence)
9. Epstein & Axtell (1996) — Agent-based social simulation (peer influence)

Factor clusters follow Rovai's (2003) composite persistence model:
- Internal factors (academic/social integration, course design, accessibility)
- External factors (finances, family, employment)
- Student characteristics (personality, goal commitment, beliefs about ODE)
- Student skills (digital literacy, self-regulation, time management)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict


# ─────────────────────────────────────────────
# Personality: Big Five (Costa & McCrae, 1992)
# ─────────────────────────────────────────────

@dataclass
class BigFiveTraits:
    """Big Five personality model (OCEAN). Each dimension is 0.0–1.0."""
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5

    def __post_init__(self):
        for trait_name in ["openness", "conscientiousness", "extraversion",
                           "agreeableness", "neuroticism"]:
            val = getattr(self, trait_name)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{trait_name} must be between 0.0 and 1.0, got {val}")

    def to_description(self) -> str:
        descriptions = []
        trait_map = {
            "openness": ("curious and open to new ideas", "prefers routine and familiar approaches"),
            "conscientiousness": ("organized, disciplined, and goal-oriented", "spontaneous and flexible with deadlines"),
            "extraversion": ("socially active and enjoys group work", "prefers independent study and solitude"),
            "agreeableness": ("cooperative and supportive of peers", "competitive and assertive"),
            "neuroticism": ("prone to stress and anxiety about performance", "emotionally stable and calm under pressure"),
        }
        for trait_name, (high_desc, low_desc) in trait_map.items():
            val = getattr(self, trait_name)
            if val >= 0.7:
                descriptions.append(high_desc)
            elif val <= 0.3:
                descriptions.append(low_desc)
        return "; ".join(descriptions) if descriptions else "balanced personality"


# ─────────────────────────────────────────────
# Population Configuration
# ─────────────────────────────────────────────

# The dropout_base_rate at which _calculate_derived_attributes() was calibrated.
# Referenced by factory.py to compute scaling factors.
_CALIBRATED_DROPOUT_BASE_RATE: float = 0.80

@dataclass
class PersonaConfig:
    """Configuration for population-level persona generation."""
    # Demographics
    age_range: tuple[int, int] = (18, 55)
    gender_distribution: dict[str, float] = field(
        default_factory=lambda: {"male": 0.48, "female": 0.52}
    )

    # Bean & Metzner: External/environmental factors
    # ODL students are predominantly non-traditional: higher employment,
    # more family responsibilities, greater financial pressure
    employment_rate: float = 0.78
    has_family_rate: float = 0.52
    financial_stress_mean: float = 0.55  # 0-1 scale

    # Academic background
    prior_gpa_mean: float = 2.3
    prior_gpa_std: float = 0.8

    # Rovai: Student skills
    # ODL students tend to have lower self-regulation and digital skills
    digital_literacy_mean: float = 0.50
    digital_literacy_std: float = 0.22
    self_regulation_mean: float = 0.42
    self_regulation_std: float = 0.20

    # Bäulke et al.: Motivation (SDT)
    # Higher amotivation rate in ODL (many enroll without strong intrinsic drive)
    motivation_levels: dict[str, float] = field(
        default_factory=lambda: {"intrinsic": 0.25, "extrinsic": 0.45, "amotivation": 0.30}
    )

    # Population distributions for categorical attributes
    socioeconomic_distribution: dict[str, float] = field(
        default_factory=lambda: {"low": 0.30, "middle": 0.50, "high": 0.20}
    )
    prior_education_distribution: dict[str, float] = field(
        default_factory=lambda: {"high_school": 0.50, "associate": 0.30, "bachelor": 0.20}
    )
    device_distribution: dict[str, float] = field(
        default_factory=lambda: {"laptop": 0.40, "desktop": 0.15, "mobile": 0.35, "tablet": 0.10}
    )
    goal_orientation_distribution: dict[str, float] = field(
        default_factory=lambda: {"mastery": 0.35, "performance": 0.40, "avoidance": 0.25}
    )
    learning_style_distribution: dict[str, float] = field(
        default_factory=lambda: {"visual": 0.35, "auditory": 0.20, "reading": 0.30, "kinesthetic": 0.15}
    )

    # Target outcome — ODL dropout rates range 40-90% in literature
    # (Bağrıacık Yılmaz & Karataş, 2022; Shaikh & Asif, 2022)
    dropout_base_rate: float = _CALIBRATED_DROPOUT_BASE_RATE

    def __post_init__(self):
        from ..utils.validation import validate_range, validate_probability_distribution
        validate_range(self.employment_rate, 0.0, 1.0, "employment_rate")
        validate_range(self.has_family_rate, 0.0, 1.0, "has_family_rate")
        validate_range(self.financial_stress_mean, 0.0, 1.0, "financial_stress_mean")
        validate_range(self.prior_gpa_mean, 0.0, 4.0, "prior_gpa_mean")
        validate_range(self.digital_literacy_mean, 0.0, 1.0, "digital_literacy_mean")
        validate_range(self.self_regulation_mean, 0.0, 1.0, "self_regulation_mean")
        validate_range(self.dropout_base_rate, 0.01, 1.0, "dropout_base_rate")
        validate_probability_distribution(self.gender_distribution, "gender_distribution")
        validate_probability_distribution(self.motivation_levels, "motivation_levels")
        validate_probability_distribution(self.socioeconomic_distribution, "socioeconomic_distribution")
        validate_probability_distribution(self.prior_education_distribution, "prior_education_distribution")
        validate_probability_distribution(self.device_distribution, "device_distribution")
        validate_probability_distribution(self.goal_orientation_distribution, "goal_orientation_distribution")
        validate_probability_distribution(self.learning_style_distribution, "learning_style_distribution")


# ─────────────────────────────────────────────
# StudentPersona
# ─────────────────────────────────────────────

@dataclass
class StudentPersona:
    """
    A fully specified ODL student persona grounded in dropout theory.

    Attributes are organized into four factor clusters (Rovai, 2003):

    CLUSTER 1 — Student Characteristics (Tinto, Kember)
        personality, age, gender, prior_education_level, prior_gpa,
        goal_commitment, ode_beliefs, years_since_last_education

    CLUSTER 2 — Student Skills (Rovai)
        digital_literacy, self_regulation, time_management,
        academic_reading_writing, has_reliable_internet, device_type

    CLUSTER 3 — External Factors (Bean & Metzner, Economic Rationality)
        is_employed, weekly_work_hours, has_family_responsibilities,
        financial_stress, socioeconomic_level, perceived_cost_benefit

    CLUSTER 4 — Internal Factors (Tinto, Rovai)
        academic_integration, social_integration, institutional_support_access,
        self_efficacy, motivation_type, goal_orientation

    PROCESS MODEL (Bäulke et al. — Phase-Oriented Dropout Model)
        dropout_phase: tracks the student's position in the dropout process
        (0=baseline, 1=non_fit_perception, 2=thoughts_of_quitting, 3=deliberation, 4=info_search, 5=decided)
    """

    # ── Identity ──
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    age: int = 25
    gender: str = "female"

    # ── CLUSTER 1: Student Characteristics (Tinto, Kember) ──
    personality: BigFiveTraits = field(default_factory=BigFiveTraits)
    prior_gpa: float = 2.5  # 0.0–4.0
    prior_education_level: str = "high_school"  # high_school, associate, bachelor
    years_since_last_education: int = 3
    enrolled_courses: int = 4
    goal_commitment: float = 0.6  # 0-1; Tinto: strength of degree completion goal
    ode_beliefs: float = 0.5  # 0-1; belief that ODE can deliver quality education

    # ── CLUSTER 2: Student Skills (Rovai, Moore) ──
    digital_literacy: float = 0.6  # 0-1; Rovai: ability to use LMS & digital tools
    self_regulation: float = 0.5  # 0-1; Rovai/Bäulke: autonomous learning ability
    time_management: float = 0.5  # 0-1; distinct from self-regulation
    academic_reading_writing: float = 0.6  # 0-1; readiness for academic work
    learner_autonomy: float = 0.5  # 0-1; Moore (1993): self-direction in learning
    has_reliable_internet: bool = True
    device_type: str = "laptop"  # laptop, desktop, mobile, tablet
    preferred_learning_style: str = "visual"

    # ── CLUSTER 3: External Factors (Bean & Metzner, Economic Rationality) ──
    is_employed: bool = True
    weekly_work_hours: int = 40
    has_family_responsibilities: bool = False
    financial_stress: float = 0.3  # 0-1; Bean & Metzner: financial pressure
    socioeconomic_level: str = "middle"  # low, middle, high
    perceived_cost_benefit: float = 0.6  # 0-1; Kember/Economic: "is this worth it?"

    # ── CLUSTER 4: Internal Factors (Tinto, Rovai) ──
    academic_integration: float = 0.5  # 0-1; Tinto: intellectual connection to program
    social_integration: float = 0.3  # 0-1; Tinto: peer/community bonds (lower in ODE)
    institutional_support_access: float = 0.5  # 0-1; Rovai: ability to reach support
    self_efficacy: float = 0.6  # 0-1; Bandura: belief in own academic capability
    motivation_type: str = "extrinsic"  # SDT: intrinsic, extrinsic, amotivation
    goal_orientation: str = "mastery"  # mastery, performance, avoidance

    # ── PROCESS MODEL: Dropout Phase (Bäulke et al. — Phase-Oriented) ──
    # 0=baseline, 1=non_fit_perception, 2=thoughts_of_quitting, 3=deliberation, 4=info_search, 5=decided
    dropout_phase: int = 0

    # ── Derived Behavioral Probabilities ──
    base_engagement_probability: float = 0.0
    base_dropout_risk: float = 0.0
    _dropout_risk_scale: float = 1.0  # population-level calibration factor

    # ── LLM-generated backstory (optional) ──
    backstory: str = ""

    def __post_init__(self):
        self._calculate_derived_attributes()

    def _calculate_derived_attributes(self):
        """
        Derive behavioral probabilities from persona attributes.

        Engagement formula weights reflect theoretical importance:
        - Internal factors (Tinto/Rovai): 40% of engagement
        - Student skills (Rovai): 25% of engagement
        - Student characteristics: 20% of engagement
        - External factors (Bean & Metzner): 15% of engagement
          (Note: in ODE, external factors affect dropout MORE than engagement)

        Dropout risk formula:
        - External factors (Bean & Metzner): 30% — dominant in ODE
        - Internal factors (Tinto): 25%
        - Student characteristics: 20%
        - Student skills (Rovai): 15%
        - Economic rationality (Kember): 10%
        """

        # ── Engagement Probability ──
        # Internal factors (Tinto/Rovai) — 40%
        internal = (
            self.self_efficacy * 0.12
            + self.academic_integration * 0.10
            + (1.0 if self.motivation_type == "intrinsic" else
               0.5 if self.motivation_type == "extrinsic" else 0.1) * 0.10
            + self.social_integration * 0.04
            + self.institutional_support_access * 0.04
        )

        # Student skills (Rovai, Moore) — 25%
        skills = (
            self.self_regulation * 0.08
            + self.digital_literacy * 0.06
            + self.time_management * 0.04
            + self.learner_autonomy * 0.04  # Moore (1993)
            + (1.0 if self.has_reliable_internet else 0.3) * 0.03
        )

        # Student characteristics — 20%
        characteristics = (
            self.personality.conscientiousness * 0.10
            + self.goal_commitment * 0.06
            + self.ode_beliefs * 0.04
        )

        # External factors (Bean & Metzner) — 15%
        external = (
            (1 - min(self.weekly_work_hours / 50, 1.0)) * 0.06
            + (0.3 if self.has_family_responsibilities else 0.7) * 0.05
            + (1 - self.financial_stress) * 0.04
        )

        self.base_engagement_probability = min(max(
            internal + skills + characteristics + external, 0.05
        ), 0.95)

        # ── Dropout Risk ──
        # External factors (Bean & Metzner) — 30% (DOMINANT in ODE)
        ext_risk = (
            min(self.weekly_work_hours / 50, 1.0) * 0.10
            + (0.8 if self.has_family_responsibilities else 0.2) * 0.08
            + self.financial_stress * 0.07
            + (0.6 if not self.has_reliable_internet else 0.1) * 0.05
        )

        # Internal factors (Tinto) — 25%
        int_risk = (
            (1 - self.self_efficacy) * 0.08
            + (1 - self.academic_integration) * 0.07
            + (0.8 if self.motivation_type == "amotivation" else
               0.3 if self.motivation_type == "extrinsic" else 0.05) * 0.06
            + (1 - self.social_integration) * 0.04
        )

        # Student characteristics — 20%
        char_risk = (
            (1 - self.personality.conscientiousness) * 0.08
            + (1 - self.goal_commitment) * 0.07
            + self.personality.neuroticism * 0.05
        )

        # Student skills (Rovai, Moore) — 15%
        skill_risk = (
            (1 - self.self_regulation) * 0.05
            + (1 - self.digital_literacy) * 0.04
            + (1 - self.time_management) * 0.03
            + (1 - self.learner_autonomy) * 0.03  # Moore (1993)
        )

        # Economic rationality (Kember) — 10%
        econ_risk = (1 - self.perceived_cost_benefit) * 0.10

        raw_risk = ext_risk + int_risk + char_risk + skill_risk + econ_risk
        self.base_dropout_risk = min(max(
            raw_risk * self._dropout_risk_scale, 0.02
        ), 0.90)

    @staticmethod
    def _level(value: float) -> str:
        """Map a 0-1 float to a human-readable level."""
        if value > 0.7:
            return "high"
        if value > 0.4:
            return "moderate"
        return "low"

    def to_prompt_description(self) -> str:
        """Generate a structured description for LLM-based simulation.

        Used as agent context in LLM-augmented mode. Designed to be
        token-efficient and injection-safe (no raw user strings).
        """
        lv = self._level
        return (
            f"Student ID: {self.id}. "
            f"Age: {int(self.age)}, Gender: {str(self.gender)[:10]}, "
            f"Courses: {self.enrolled_courses}, "
            f"Education: {str(self.prior_education_level)[:20]} (GPA {self.prior_gpa:.1f}/4.0), "
            f"{self.years_since_last_education}y since last education. "
            f"Employment: {'employed ' + str(self.weekly_work_hours) + 'h/wk' if self.is_employed else 'unemployed'}. "
            f"Family responsibilities: {'yes' if self.has_family_responsibilities else 'no'}. "
            f"Financial stress: {lv(self.financial_stress)}, "
            f"Self-regulation: {lv(self.self_regulation)}, "
            f"Digital literacy: {lv(self.digital_literacy)}, "
            f"Learner autonomy: {lv(self.learner_autonomy)}, "
            f"Goal commitment: {lv(self.goal_commitment)}. "
            f"Motivation: {str(self.motivation_type)[:15]}. "
            f"Cost-benefit perception: {lv(self.perceived_cost_benefit)}. "
            f"Personality: {self.personality.to_description()}."
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["personality"] = asdict(self.personality)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> StudentPersona:
        clean = {k: v for k, v in data.items() if k != "personality"}
        personality_data = data.get("personality", {})
        clean["personality"] = BigFiveTraits(**personality_data)
        return cls(**clean)
