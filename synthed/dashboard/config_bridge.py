"""Bridge between frozen config dataclasses and mutable UI reactive values."""

from __future__ import annotations

import os
from dataclasses import fields
from pathlib import Path
from typing import Any

from ..agents.persona import PersonaConfig
from ..simulation.engine_config import EngineConfig
from ..simulation.grading import GradingConfig
from ..simulation.institutional import InstitutionalConfig
from ..pipeline_config import PipelineConfig


# ── Security constants ──

MAX_IMPORT_SIZE_BYTES: int = 512 * 1024  # 512 KB
MAX_N_STUDENTS: int = 10_000


# ── Metadata: field descriptions + warnings ──

FIELD_DESCRIPTIONS: dict[str, str] = {
    # PersonaConfig
    "age_range": "Min/max age for generated student population",
    "employment_rate": "Fraction of population that is employed (Beta distribution gate)",
    "has_family_rate": "Fraction of population with family responsibilities",
    "financial_stress_mean": "Population mean financial stress [0-1]",
    "prior_gpa_mean": "Population mean prior GPA [0-4]",
    "prior_gpa_std": "Standard deviation of prior GPA",
    "digital_literacy_mean": "Population mean digital literacy [0-1]",
    "digital_literacy_std": "Standard deviation of digital literacy",
    "self_regulation_mean": "Population mean self-regulation [0-1]",
    "self_regulation_std": "Standard deviation of self-regulation",
    "dropout_base_rate": "Base dropout probability — calibrated via CalibrationMap",
    "unavoidable_withdrawal_rate": "Per-semester probability of forced withdrawal (illness, emergency)",
    "disability_rate": "Fraction of population with disabilities (Rovai accessibility)",
    "generate_names": "Generate culturally diverse names for personas",
    # InstitutionalConfig
    "instructional_design_quality": "Quality of instructional design [0=poor, 1=excellent]",
    "teaching_presence_baseline": "Baseline teaching presence level [0-1]",
    "support_services_quality": "Student support quality — scales 13 Baulke dropout thresholds",
    "technology_quality": "LMS and technology infrastructure quality [0-1]",
    "curriculum_flexibility": "Degree of curriculum flexibility [0-1]",
    # GradingConfig
    "scale": "Grading scale: SCALE_100 or SCALE_4",
    "assessment_mode": "Assessment mode: mixed, exam_only, or continuous",
    "midterm_weight": "Weight of midterm in semester grade [0-1]",
    "final_weight": "Weight of final in semester grade [0-1]",
    "distribution": "Grade distribution shape: beta, normal, or uniform",
    "dist_alpha": "Alpha parameter for grade distribution",
    "dist_beta": "Beta parameter for grade distribution",
    "grading_method": "Grading method: absolute or relative (t-score)",
    "grade_floor": "Minimum possible grade (transcript floor) [0-1]",
    "pass_threshold": "Threshold for passing [0-1]. Must be < distinction_threshold",
    "distinction_threshold": "Threshold for distinction [0-1]. Must be > pass_threshold",
    "dual_hurdle": "Require passing both components separately",
    "exam_eligibility_threshold": "Minimum coursework score for exam eligibility",
    "late_penalty": "Per-instance late submission penalty [0-1]",
    "noise_std": "Grade noise standard deviation [0-1]",
    "missing_policy": "Missing assignment policy: zero or redistribute",
    # Pipeline
    "seed": "Random seed for reproducibility",
    "n_semesters": "Number of semesters to simulate",
    "output_dir": "Directory for CSV output files",
    "export_oulad": "Export in OULAD 7-table format",
    "cost_threshold": "LLM cost confirmation threshold ($)",
}

FIELD_WARNINGS: dict[str, tuple[str, Any]] = {
    "dropout_base_rate": ("High dropout rate (>0.9) may produce unrealistic populations", 0.9),
    "disability_rate": ("High disability rate (>0.5) is unusual", 0.5),
    "unavoidable_withdrawal_rate": ("Rate >0.02 means >2% forced withdrawal per semester", 0.02),
}

# Distribution fields that must sum to 1.0
DISTRIBUTION_FIELDS: dict[str, str] = {
    "gender_distribution": "Gender",
    "motivation_levels": "Motivation",
    "socioeconomic_distribution": "Socioeconomic",
    "prior_education_distribution": "Prior Education",
    "device_distribution": "Device",
    "goal_orientation_distribution": "Goal Orientation",
    "learning_style_distribution": "Learning Style",
}


def config_to_dict(config: PipelineConfig) -> dict[str, Any]:
    """Flatten PipelineConfig into a dict of scalar/dict values for UI binding."""
    result: dict[str, Any] = {}

    # Pipeline scalars
    result["seed"] = config.seed
    result["n_semesters"] = config.n_semesters
    result["output_dir"] = config.output_dir or "./output"
    result["export_oulad"] = config.export_oulad
    result["cost_threshold"] = config.cost_threshold

    # PersonaConfig
    pc = config.persona_config
    for f in fields(pc):
        result[f"persona_{f.name}"] = getattr(pc, f.name)

    # InstitutionalConfig
    ic = config.institutional_config
    for f in fields(ic):
        result[f"inst_{f.name}"] = getattr(ic, f.name)

    # GradingConfig
    gc = config.grading_config
    for f in fields(gc):
        val = getattr(gc, f.name)
        if hasattr(val, "value"):  # enum
            val = val.value
        result[f"grading_{f.name}"] = val

    # EngineConfig
    ec = config.engine_config
    for f in fields(ec):
        result[f"engine_{f.name}"] = getattr(ec, f.name)

    return result


def dict_to_config(values: dict[str, Any]) -> PipelineConfig:
    """Reconstruct PipelineConfig from flat UI values dict."""
    from ..simulation.grading import GradingScale

    persona_kwargs = {}
    inst_kwargs = {}
    grading_kwargs = {}
    engine_kwargs = {}
    pipeline_kwargs = {}

    for key, val in values.items():
        if key.startswith("persona_"):
            persona_kwargs[key.removeprefix("persona_")] = val
        elif key.startswith("inst_"):
            inst_kwargs[key.removeprefix("inst_")] = val
        elif key.startswith("grading_"):
            name = key.removeprefix("grading_")
            if name == "scale" and isinstance(val, int):
                val = GradingScale(val)
            grading_kwargs[name] = val
        elif key.startswith("engine_"):
            engine_kwargs[key.removeprefix("engine_")] = val
        elif key in ("seed", "n_semesters", "output_dir", "export_oulad", "cost_threshold"):
            pipeline_kwargs[key] = val

    pc = PersonaConfig(**persona_kwargs)
    ic = InstitutionalConfig(**inst_kwargs)
    gc = GradingConfig(**grading_kwargs)
    ec = EngineConfig(**engine_kwargs)

    return PipelineConfig(
        persona_config=pc,
        institutional_config=ic,
        grading_config=gc,
        engine_config=ec,
        **pipeline_kwargs,
    )


def _strip_prefix(field_name: str) -> str:
    """Strip config prefix: persona_employment_rate → employment_rate."""
    for prefix in ("persona_", "inst_", "grading_", "engine_"):
        if field_name.startswith(prefix):
            return field_name[len(prefix):]
    return field_name


def get_description(field_name: str) -> str:
    """Get human-readable description for a parameter."""
    clean = _strip_prefix(field_name)
    return FIELD_DESCRIPTIONS.get(clean, "")


def check_warning(field_name: str, value: Any) -> str | None:
    """Check if a field value triggers a warning. Returns warning text or None."""
    clean = _strip_prefix(field_name)
    entry = FIELD_WARNINGS.get(clean)
    if entry is None:
        return None
    msg, threshold = entry
    try:
        if float(value) > float(threshold):
            return msg
    except (TypeError, ValueError):
        pass
    return None


def normalize_distribution(dist: dict[str, float], changed_key: str) -> dict[str, float]:
    """Auto-normalize a probability distribution after one value changes.

    Adjusts all keys except changed_key proportionally so the total sums to 1.0.
    """
    changed_val = dist[changed_key]
    changed_val = max(0.0, min(1.0, changed_val))
    remaining = 1.0 - changed_val
    other_keys = [k for k in dist if k != changed_key]
    other_sum = sum(dist[k] for k in other_keys)

    result = {changed_key: round(changed_val, 4)}
    if other_sum > 0 and remaining > 0:
        scale = remaining / other_sum
        for k in other_keys:
            result[k] = round(dist[k] * scale, 4)
    else:
        equal_share = round(remaining / max(len(other_keys), 1), 4)
        for k in other_keys:
            result[k] = equal_share

    # Fix rounding to exactly 1.0
    diff = 1.0 - sum(result.values())
    if abs(diff) > 1e-6:
        first_other = other_keys[0] if other_keys else changed_key
        result[first_other] = round(result[first_other] + diff, 4)

    return result


def validate_output_dir(output_dir: str) -> str:
    """Validate output_dir is safe — no path traversal, stays under CWD.

    Returns the resolved path string if valid, raises ValueError otherwise.
    """
    resolved = Path(output_dir).resolve()
    cwd = Path(os.getcwd()).resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError:
        raise ValueError("output_dir must be within the working directory")
    return str(resolved)


# ── Presets ──

PRESETS: dict[str, dict[str, Any]] = {
    "default": {},
    "high_risk": {
        "persona_dropout_base_rate": 0.95,
        "persona_financial_stress_mean": 0.80,
        "persona_employment_rate": 0.90,
        "inst_support_services_quality": 0.2,
        "inst_instructional_design_quality": 0.3,
    },
    "low_dropout": {
        "persona_dropout_base_rate": 0.30,
        "persona_financial_stress_mean": 0.25,
        "persona_self_regulation_mean": 0.70,
        "inst_support_services_quality": 0.9,
        "inst_instructional_design_quality": 0.8,
        "inst_teaching_presence_baseline": 0.8,
    },
}
