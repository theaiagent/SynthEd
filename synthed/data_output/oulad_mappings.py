"""
OULAD-compatible mapping constants and pure transformation functions.

Maps SynthEd's internal data model to the Open University Learning Analytics
Dataset (OULAD) schema. All functions are pure (no I/O, no side effects).
"""

from __future__ import annotations

import numpy as np


# ─────────────────────────────────────────────
# Column definitions (exact OULAD header order)
# ─────────────────────────────────────────────

COURSES_COLUMNS: tuple[str, ...] = (
    "code_module", "code_presentation", "module_presentation_length",
)

ASSESSMENTS_COLUMNS: tuple[str, ...] = (
    "code_module", "code_presentation", "id_assessment",
    "assessment_type", "date", "weight",
)

VLE_COLUMNS: tuple[str, ...] = (
    "id_site", "code_module", "code_presentation",
    "activity_type", "week_from", "week_to",
)

STUDENT_INFO_COLUMNS: tuple[str, ...] = (
    "code_module", "code_presentation", "id_student", "gender",
    "region", "highest_education", "imd_band", "age_band",
    "num_of_prev_attempts", "studied_credits", "disability", "final_result",
)

STUDENT_REGISTRATION_COLUMNS: tuple[str, ...] = (
    "code_module", "code_presentation", "id_student",
    "date_registration", "date_unregistration",
)

STUDENT_ASSESSMENT_COLUMNS: tuple[str, ...] = (
    "id_assessment", "id_student", "date_submitted", "is_banked", "score",
)

STUDENT_VLE_COLUMNS: tuple[str, ...] = (
    "code_module", "code_presentation", "id_student",
    "id_site", "date", "sum_click",
)


# ─────────────────────────────────────────────
# Mapping constants
# ─────────────────────────────────────────────

# OULAD regions (UK-based, weighted by OULAD observed distribution)
_OULAD_REGIONS: tuple[str, ...] = (
    "East Anglian Region", "East Midlands Region", "Ireland",
    "London Region", "North Region", "North Western Region",
    "Scotland", "South East Region", "South Region",
    "South West Region", "Wales", "West Midlands Region",
    "Yorkshire Region",
)

_REGION_WEIGHTS: tuple[float, ...] = (
    0.06, 0.08, 0.04, 0.13, 0.07, 0.09,
    0.06, 0.12, 0.08, 0.07, 0.05, 0.08, 0.07,
)

# Education level mapping
_EDUCATION_MAP: dict[str, str] = {
    "high_school": "A Level or Equivalent",
    "associate": "Lower Than A Level",
    "bachelor": "HE Qualification",
}

# Socioeconomic level to IMD band mapping
_IMD_BANDS_BY_SES: dict[str, tuple[str, ...]] = {
    "low": ("0-10%", "10-20%", "20-30%", "30-40%"),
    "middle": ("40-50%", "50-60%", "60-70%", "70-80%"),
    "high": ("80-90%", "90-100%"),
}

# Interaction type to VLE activity_type
_ACTIVITY_TYPE_MAP: dict[str, str] = {
    "lms_login": "homepage",
    "forum_read": "forumng",
    "forum_post": "forumng",
    "live_session": "oucollaborate",
}

# Final result vocabulary
_FINAL_RESULT_DISTINCTION_GPA: float = 3.4  # GPA >= this → Distinction
_FINAL_RESULT_PASS_GPA: float = 1.6         # GPA >= this → Pass


# ─────────────────────────────────────────────
# Pure mapping functions
# ─────────────────────────────────────────────

def semester_to_presentation(semester_name: str) -> str:
    """Convert SynthEd semester name to OULAD code_presentation.

    'Fall 2026' → '2026J', 'Spring 2026' → '2026B', 'Summer 2026' → '2026B'
    """
    parts = semester_name.split()
    if len(parts) != 2:
        return "2026B"
    season, year = parts
    suffix = "J" if season.lower() == "fall" else "B"
    return f"{year}{suffix}"


def age_to_band(age: int) -> str:
    """Convert integer age to OULAD age_band."""
    if age < 35:
        return "0-35"
    elif age < 55:
        return "35-55"
    return "55<="


def gender_to_oulad(gender: str) -> str:
    """Convert SynthEd gender to OULAD format."""
    return "M" if gender == "male" else "F"


def education_to_oulad(prior_education_level: str) -> str:
    """Convert SynthEd education level to OULAD highest_education."""
    return _EDUCATION_MAP.get(prior_education_level, "A Level or Equivalent")


def select_region(rng: np.random.Generator) -> str:
    """Select a UK region weighted by OULAD observed distribution."""
    idx = rng.choice(len(_OULAD_REGIONS), p=_REGION_WEIGHTS)
    return _OULAD_REGIONS[idx]


def select_imd_band(rng: np.random.Generator, socioeconomic_level: str) -> str:
    """Select an IMD band based on socioeconomic level."""
    bands = _IMD_BANDS_BY_SES.get(socioeconomic_level, _IMD_BANDS_BY_SES["middle"])
    return str(rng.choice(bands))


def map_final_result(
    has_dropped_out: bool,
    withdrawal_reason: str | None,
    cumulative_gpa: float,
    gpa_count: int,
) -> str:
    """Map simulation outcome to OULAD final_result vocabulary."""
    if has_dropped_out or withdrawal_reason is not None:
        return "Withdrawn"
    if gpa_count == 0:
        return "Pass"  # No graded items but completed — default to Pass
    if cumulative_gpa >= _FINAL_RESULT_DISTINCTION_GPA:
        return "Distinction"
    if cumulative_gpa >= _FINAL_RESULT_PASS_GPA:
        return "Pass"
    return "Fail"


def map_activity_type(interaction_type: str) -> str | None:
    """Map SynthEd interaction type to OULAD activity_type.

    Returns None for types that go to studentAssessment (not VLE).
    """
    if interaction_type in ("assignment_submit", "exam"):
        return None  # These go to studentAssessment, not VLE
    return _ACTIVITY_TYPE_MAP.get(interaction_type, "oucontent")


def click_heuristic(interaction_type: str, duration_minutes: float, metadata: dict) -> int:
    """Convert a SynthEd interaction record to OULAD sum_click count."""
    if interaction_type == "lms_login":
        return 1
    elif interaction_type == "forum_read":
        return max(1, int(duration_minutes / 3))
    elif interaction_type == "forum_post":
        post_length = metadata.get("post_length", 50)
        return max(1, int(post_length / 20))
    elif interaction_type == "live_session":
        return max(1, int(duration_minutes / 10))
    return max(1, int(duration_minutes / 5))


def student_id_to_int(display_id: str) -> int:
    """Convert SynthEd display_id (S-0001) to OULAD integer id_student."""
    try:
        return int(display_id.replace("S-", ""))
    except (ValueError, AttributeError):
        return 0
