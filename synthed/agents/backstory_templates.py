"""
Backstory template system for diverse LLM-generated student narratives.

Provides templates with varied narrative angles, life events, and regional
contexts to produce richer, more diverse backstories for synthetic ODL students.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .persona import StudentPersona

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class LifeEvent:
    """A significant life event that may influence a student's ODL experience."""
    label: str
    description: str
    weight: float = 1.0


@dataclass(frozen=True)
class RegionalContext:
    """Geographic and infrastructure context for a student."""
    setting: str           # "rural" | "urban" | "suburban" | "peri-urban"
    country_context: str   # e.g., "developing_economy", "post_industrial"
    connectivity: str      # "reliable" | "intermittent" | "limited"


@dataclass(frozen=True)
class BackstoryTemplate:
    """A narrative template for LLM backstory generation."""
    id: str
    system_prompt: str
    user_prompt_format: str


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

_LIFE_EVENTS: tuple[LifeEvent, ...] = (
    LifeEvent(
        label="job_loss",
        description="recently lost their job and is seeking new qualifications to re-enter the workforce",
        weight=1.2,
    ),
    LifeEvent(
        label="health_crisis",
        description="recovering from a significant health issue that limited their ability to attend in-person classes",
        weight=0.8,
    ),
    LifeEvent(
        label="relocation",
        description="recently relocated to a new area and chose distance learning for continuity",
        weight=1.0,
    ),
    LifeEvent(
        label="career_change",
        description="recently changed careers and is seeking new qualifications in a different field",
        weight=1.3,
    ),
    LifeEvent(
        label="divorce",
        description="going through a divorce and managing new responsibilities while pursuing education",
        weight=0.9,
    ),
    LifeEvent(
        label="new_baby",
        description="recently became a parent and needs the flexibility of distance learning",
        weight=1.1,
    ),
    LifeEvent(
        label="bereavement",
        description="coping with the loss of a close family member while continuing their education",
        weight=0.7,
    ),
    LifeEvent(
        label="military_return",
        description="recently returned from military service and transitioning to civilian education",
        weight=0.8,
    ),
    LifeEvent(
        label="immigration",
        description="recently immigrated and using distance education to build credentials in a new country",
        weight=1.0,
    ),
    LifeEvent(
        label="disability_onset",
        description="recently acquired a disability that makes traditional campus attendance difficult",
        weight=0.7,
    ),
    LifeEvent(
        label="retirement_transition",
        description="transitioning into retirement and pursuing lifelong learning goals",
        weight=0.6,
    ),
    LifeEvent(
        label="economic_hardship",
        description="facing economic hardship and chose distance learning as a more affordable path to a degree",
        weight=1.2,
    ),
)

_REGIONAL_CONTEXTS: tuple[RegionalContext, ...] = (
    RegionalContext(setting="urban", country_context="developed_economy", connectivity="reliable"),
    RegionalContext(setting="suburban", country_context="developed_economy", connectivity="reliable"),
    RegionalContext(setting="rural", country_context="developed_economy", connectivity="intermittent"),
    RegionalContext(setting="rural", country_context="developed_economy", connectivity="limited"),
    RegionalContext(setting="peri-urban", country_context="transitional_economy", connectivity="intermittent"),
    RegionalContext(setting="urban", country_context="developing_economy", connectivity="reliable"),
    RegionalContext(setting="rural", country_context="developing_economy", connectivity="limited"),
    RegionalContext(setting="suburban", country_context="post_industrial", connectivity="reliable"),
)

_CONTENT_GUARDRAILS = (
    "No violence, sexual content, discrimination, or illegal activities."
)
_JSON_INSTRUCTION = (
    'Respond with JSON: {"backstory": "<string>", "primary_challenge": "<string>"}'
)

_TEMPLATES: tuple[BackstoryTemplate, ...] = (
    BackstoryTemplate(
        id="why_odl",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL (Open and Distance Learning) student. "
            "Focus on WHY they specifically chose distance learning over traditional campus education. "
            "Explain the practical circumstances, personal motivations, and life situation that led to this choice. "
            "Keep the tone professional, empathetic, and grounded in realistic adult learner experiences. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create a backstory focused on why this student chose distance learning. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
    BackstoryTemplate(
        id="challenge_centered",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL student that leads with their primary obstacle. "
            "Describe the central challenge they face in pursuing distance education and how it shapes their daily experience. "
            "Show how they navigate this difficulty while maintaining their commitment to learning. "
            "Use a realistic, professional tone that reflects the complexity of adult learner situations. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create a challenge-centered backstory for this student. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
    BackstoryTemplate(
        id="turning_point",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL student framing their enrollment as a turning point. "
            "Describe a life transition or pivotal moment that motivated them to pursue distance education. "
            "Show how this decision represents a meaningful shift in their life trajectory. "
            "Maintain a professional, hopeful tone grounded in realistic circumstances. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create a turning-point backstory for this student. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
    BackstoryTemplate(
        id="day_in_life",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL student describing their typical daily routine. "
            "Show how they integrate study time around work, family, and other obligations. "
            "Illustrate the practical realities of balancing distance education with daily life. "
            "Use a descriptive, professional tone that conveys the texture of their everyday experience. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create a day-in-the-life backstory for this student. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
    BackstoryTemplate(
        id="aspiration_driven",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL student centered on their future goals and aspirations. "
            "Describe what they hope to achieve through distance education and how it connects to their career plans. "
            "Show the gap between their current situation and where they want to be. "
            "Maintain a forward-looking, professional tone that reflects genuine adult learner ambitions. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create an aspiration-driven backstory for this student. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
    BackstoryTemplate(
        id="community_perspective",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL student emphasizing family and community influence. "
            "Describe how their decision to pursue distance education was shaped by family expectations, peer support, or community norms. "
            "Show the social dynamics around their educational journey. "
            "Use a professional, culturally sensitive tone that reflects diverse family structures and community contexts. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create a community-perspective backstory for this student. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
    BackstoryTemplate(
        id="reflective",
        system_prompt=(
            "Generate a 5-6 sentence backstory for a synthetic ODL student reflecting on their educational gap. "
            "Describe the time since their last formal education and what prompted them to return to learning. "
            "Show their awareness of how the gap has affected their confidence and skills. "
            "Maintain a reflective, professional tone that captures the experience of returning to education after time away. "
            f"Keep content appropriate for academic research contexts. {_CONTENT_GUARDRAILS} "
            f"{_JSON_INSTRUCTION}"
        ),
        user_prompt_format=(
            "Create a reflective backstory for this student looking back on their educational gap. "
            "Student profile: Age {age}, {gender}, {employment_info}, {family_info}, "
            "financial stress {financial_stress}. Education: {education_info}. "
            "Motivation: {motivation}, goal commitment {goal_commitment}. "
            "Skills: self-regulation {self_regulation}, digital literacy {digital_literacy}. "
            "Life context: {life_event_context}. Region: {regional_context}."
        ),
    ),
)

_LIFE_EVENT_INJECTION_PROBABILITY: float = 0.4
_MAX_SANITIZED_LENGTH: int = 120


# ─────────────────────────────────────────────
# Public Functions
# ─────────────────────────────────────────────

def select_template(rng: np.random.Generator) -> BackstoryTemplate:
    """Select a template using RNG for reproducibility.

    Parameters
    ----------
    rng : np.random.Generator
        NumPy random generator for reproducible selection.

    Returns
    -------
    BackstoryTemplate
        A randomly selected backstory template.
    """
    idx = rng.integers(0, len(_TEMPLATES))
    return _TEMPLATES[idx]


def select_life_event(
    rng: np.random.Generator,
    injection_probability: float = _LIFE_EVENT_INJECTION_PROBABILITY,
) -> LifeEvent | None:
    """Randomly select a life event, or None if not injected.

    Parameters
    ----------
    rng : np.random.Generator
        NumPy random generator for reproducible selection.
    injection_probability : float
        Probability that a life event is assigned (default 0.4).

    Returns
    -------
    LifeEvent | None
        A weighted-random life event, or None if not injected.
    """
    if rng.random() > injection_probability:
        return None
    weights = np.array([e.weight for e in _LIFE_EVENTS])
    weights = weights / weights.sum()
    idx = rng.choice(len(_LIFE_EVENTS), p=weights)
    return _LIFE_EVENTS[idx]


def select_regional_context(rng: np.random.Generator) -> RegionalContext:
    """Select a regional context randomly.

    Parameters
    ----------
    rng : np.random.Generator
        NumPy random generator for reproducible selection.

    Returns
    -------
    RegionalContext
        A randomly selected regional context.
    """
    idx = rng.integers(0, len(_REGIONAL_CONTEXTS))
    return _REGIONAL_CONTEXTS[idx]


def build_enrichment_prompt(
    persona: StudentPersona,
    template: BackstoryTemplate,
    life_event: LifeEvent | None,
    regional_context: RegionalContext,
) -> list[dict[str, str]]:
    """Build the messages list for LLMClient.chat_json().

    Sanitizes persona attributes to prevent prompt injection and formats
    them into the template's user_prompt_format.

    Parameters
    ----------
    persona : StudentPersona
        The student persona to generate a backstory for.
    template : BackstoryTemplate
        The narrative template to use.
    life_event : LifeEvent | None
        Optional life event context.
    regional_context : RegionalContext
        Geographic and infrastructure context.

    Returns
    -------
    list[dict[str, str]]
        A two-element messages list (system + user) for the LLM.
    """
    def _sanitize(value: str, maxlen: int = _MAX_SANITIZED_LENGTH) -> str:
        return value.replace("\n", " ").replace("\r", " ")[:maxlen]

    # Sanitize persona attributes (prevent prompt injection)
    age = int(persona.age)
    gender = str(persona.gender)[:10]
    education = str(persona.prior_education_level)[:20]
    motivation = str(persona.motivation_type)[:15]

    employment_info = (
        f"employed {persona.weekly_work_hours}h/wk"
        if persona.is_employed else "unemployed"
    )
    family_info = "has dependents" if persona.has_family_responsibilities else "no dependents"
    life_event_context = _sanitize(life_event.description) if life_event else "no significant recent life changes"
    regional_ctx = (
        f"{_sanitize(regional_context.setting, 20)} area, "
        f"{_sanitize(regional_context.country_context, 30)} context, "
        f"{_sanitize(regional_context.connectivity, 20)} internet"
    )

    user_content = template.user_prompt_format.format(
        age=age,
        gender=gender,
        employment_info=employment_info,
        family_info=family_info,
        financial_stress=f"{persona.financial_stress:.0%}",
        education_info=f"{education} (GPA {persona.prior_gpa:.1f}), {persona.years_since_last_education}y gap",
        motivation=motivation,
        goal_commitment=f"{persona.goal_commitment:.0%}",
        self_regulation=f"{persona.self_regulation:.0%}",
        digital_literacy=f"{persona.digital_literacy:.0%}",
        life_event_context=life_event_context,
        regional_context=regional_ctx,
    )

    return [
        {"role": "system", "content": template.system_prompt},
        {"role": "user", "content": user_content},
    ]

