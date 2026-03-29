"""
StudentPersona: TinyTroupe-inspired persona model for ODL student agents.

Each persona encapsulates Big Five personality traits, demographic attributes,
academic background, motivation factors, and behavioral tendencies that
drive realistic simulation of student interactions in distance learning.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class BigFiveTraits:
    """Big Five personality model (OCEAN). Each dimension is 0.0-1.0."""
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
        """Convert traits to natural language for LLM prompting."""
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


@dataclass
class PersonaConfig:
    """Configuration for population-level persona generation."""
    age_range: tuple[int, int] = (18, 55)
    gender_distribution: dict[str, float] = field(
        default_factory=lambda: {"male": 0.45, "female": 0.50, "other": 0.05}
    )
    employment_rate: float = 0.65  # ODL students often work
    has_family_rate: float = 0.40
    prior_gpa_mean: float = 2.5
    prior_gpa_std: float = 0.7
    digital_literacy_mean: float = 0.6  # 0-1 scale
    digital_literacy_std: float = 0.2
    motivation_levels: dict[str, float] = field(
        default_factory=lambda: {"intrinsic": 0.35, "extrinsic": 0.45, "amotivation": 0.20}
    )
    dropout_base_rate: float = 0.35  # Target population dropout rate


@dataclass
class StudentPersona:
    """
    A fully specified student persona for ODL simulation.

    Inspired by TinyTroupe's TinyPerson abstraction, extended with
    educational attributes relevant to distance learning research.
    """
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    age: int = 25
    gender: str = "female"

    # Big Five Personality
    personality: BigFiveTraits = field(default_factory=BigFiveTraits)

    # Socioeconomic Context
    is_employed: bool = True
    weekly_work_hours: int = 40
    has_family_responsibilities: bool = False
    socioeconomic_level: str = "middle"  # low, middle, high

    # Academic Background
    prior_gpa: float = 2.5  # 0.0-4.0
    prior_education_level: str = "high_school"  # high_school, associate, bachelor
    years_since_last_education: int = 3
    enrolled_courses: int = 4

    # Digital & Learning
    digital_literacy: float = 0.6  # 0-1
    preferred_learning_style: str = "visual"  # visual, auditory, reading, kinesthetic
    has_reliable_internet: bool = True
    device_type: str = "laptop"  # laptop, desktop, mobile, tablet

    # Motivation (Self-Determination Theory)
    motivation_type: str = "extrinsic"  # intrinsic, extrinsic, amotivation
    goal_orientation: str = "mastery"  # mastery, performance, avoidance
    self_efficacy: float = 0.6  # 0-1

    # Behavioral Tendencies (derived, used in simulation)
    base_engagement_probability: float = 0.0  # Calculated post-init
    base_dropout_risk: float = 0.0  # Calculated post-init

    # Memory (temporal state, updated during simulation)
    memory: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self._calculate_derived_attributes()

    def _calculate_derived_attributes(self):
        """Derive behavioral probabilities from persona attributes."""
        # Engagement probability: driven by conscientiousness, motivation, self-efficacy
        engagement_factors = [
            self.personality.conscientiousness * 0.30,
            (1.0 if self.motivation_type == "intrinsic" else
             0.6 if self.motivation_type == "extrinsic" else 0.2) * 0.25,
            self.self_efficacy * 0.20,
            self.digital_literacy * 0.15,
            (1.0 if self.has_reliable_internet else 0.4) * 0.10,
        ]
        self.base_engagement_probability = min(max(sum(engagement_factors), 0.05), 0.95)

        # Dropout risk: inverse relationship with protective factors
        risk_factors = [
            (1 - self.personality.conscientiousness) * 0.20,
            (1 - self.self_efficacy) * 0.20,
            (0.8 if self.motivation_type == "amotivation" else
             0.3 if self.motivation_type == "extrinsic" else 0.1) * 0.20,
            min(self.weekly_work_hours / 50, 1.0) * 0.15,
            (0.7 if self.has_family_responsibilities else 0.2) * 0.10,
            self.personality.neuroticism * 0.10,
            (1 - self.digital_literacy) * 0.05,
        ]
        self.base_dropout_risk = min(max(sum(risk_factors), 0.02), 0.90)

    def to_prompt_description(self) -> str:
        """Generate a natural language description for LLM-based simulation."""
        personality_desc = self.personality.to_description()
        return (
            f"{self.name} is a {self.age}-year-old {self.gender} student enrolled in "
            f"{self.enrolled_courses} courses in an open and distance learning program. "
            f"Education level: {self.prior_education_level} (GPA: {self.prior_gpa:.1f}/4.0). "
            f"{'Currently employed' if self.is_employed else 'Not currently employed'}"
            f"{f', working {self.weekly_work_hours} hours/week' if self.is_employed else ''}. "
            f"{'Has family responsibilities. ' if self.has_family_responsibilities else ''}"
            f"Digital literacy: {'high' if self.digital_literacy > 0.7 else 'moderate' if self.digital_literacy > 0.4 else 'low'}. "
            f"Accesses courses via {self.device_type}"
            f"{'' if self.has_reliable_internet else ' with unreliable internet'}. "
            f"Motivation: primarily {self.motivation_type}. "
            f"Self-efficacy: {'high' if self.self_efficacy > 0.7 else 'moderate' if self.self_efficacy > 0.4 else 'low'}. "
            f"Personality: {personality_desc}."
        )

    def add_memory(self, week: int, event_type: str, details: str, impact: float = 0.0):
        """Add a temporal memory entry (MiroFish-inspired)."""
        self.memory.append({
            "week": week,
            "event_type": event_type,
            "details": details,
            "impact": impact,  # -1.0 (negative) to 1.0 (positive)
        })

    def recent_memory_summary(self, last_n: int = 5) -> str:
        """Summarize recent memories for LLM context."""
        if not self.memory:
            return "No prior interactions recorded."
        recent = self.memory[-last_n:]
        lines = [f"Week {m['week']}: {m['details']} (impact: {m['impact']:+.1f})" for m in recent]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize persona to dictionary."""
        d = asdict(self)
        d["personality"] = asdict(self.personality)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> StudentPersona:
        """Deserialize persona from dictionary."""
        personality_data = data.pop("personality", {})
        data["personality"] = BigFiveTraits(**personality_data)
        return cls(**data)
