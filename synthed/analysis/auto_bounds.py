"""
Automatic parameter bounds generation for Sobol and Optuna analyses.

Generates SobolParameter entries programmatically from PersonaConfig defaults
and engine/theory module constants, so the parameter space adapts when users
change default values or add new parameters.

Usage:
    from synthed.analysis.auto_bounds import auto_bounds

    # Full parameter space from current defaults
    params = auto_bounds()
    analyzer = SobolAnalyzer(parameters=params)

    # Custom config with different defaults
    my_config = PersonaConfig(employment_rate=0.95, prior_gpa_mean=3.5)
    params = auto_bounds(config=my_config, margin=0.3)
"""

from __future__ import annotations

import logging
from dataclasses import fields

from ..agents.persona import PersonaConfig
from ..simulation.engine import SimulationEngine
from ..simulation.environment import ODLEnvironment
from .sobol_sensitivity import SobolParameter
from ._sim_runner import MODULE_ALIASES

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Validation ranges from PersonaConfig.__post_init__
# ─────────────────────────────────────────────

_CONFIG_RANGES: dict[str, tuple[float, float]] = {
    "employment_rate": (0.0, 1.0),
    "has_family_rate": (0.0, 1.0),
    "financial_stress_mean": (0.0, 1.0),
    "prior_gpa_mean": (0.0, 4.0),
    "digital_literacy_mean": (0.0, 1.0),
    "self_regulation_mean": (0.0, 1.0),
    "dropout_base_rate": (0.01, 1.0),
    "unavoidable_withdrawal_rate": (0.0, 0.05),
    "disability_rate": (0.0, 1.0),
    # std fields: no explicit validate_range, use sensible defaults
    "prior_gpa_std": (0.1, 2.0),
    "digital_literacy_std": (0.05, 0.40),
    "self_regulation_std": (0.05, 0.40),
}

# Constants that should never be in sensitivity analysis
_NON_TUNEABLE: frozenset[str] = frozenset({
    # Scale denominators
    "_GPA_SCALE",
    # Clip bounds
    "_ENGAGEMENT_CLIP_LO", "_ENGAGEMENT_CLIP_HI",
    "_PRESENCE_CLIP_LO", "_PRESENCE_CLIP_HI",
    "_NEED_CLIP_LO", "_NEED_CLIP_HI",
    "_CLIP_LO", "_CLIP_HI",
    "_ACADEMIC_CLIP_LO", "_ACADEMIC_CLIP_HI",
    "_SOCIAL_CLIP_LO", "_SOCIAL_CLIP_HI",
    "_SOCIAL_CLIP_HI",
    # Memory impact values (narrative, not behavioral)
    "_IMPACT_NONFIT", "_IMPACT_RECOVERY_1_TO_0", "_IMPACT_PHASE_2",
    "_IMPACT_RECOVERY_2_TO_1", "_IMPACT_PHASE_3", "_IMPACT_RECOVERY_3_TO_2",
    "_IMPACT_PHASE_4", "_IMPACT_DROPOUT", "_MISSED_IMPACT",
    # Duration/noise std (not meaningful for sensitivity)
    "_LOGIN_DURATION_STD", "_LOGIN_DURATION_MIN",
    "_FORUM_POST_DURATION_MEAN", "_FORUM_POST_DURATION_STD",
    "_FORUM_POST_LENGTH_MEAN", "_FORUM_POST_LENGTH_STD",
    "_FORUM_READ_EXP_MEAN",
    "_ASSIGN_NOISE_STD", "_EXAM_NOISE_STD",
    "_LIVE_DURATION_MEAN", "_LIVE_DURATION_STD",
    # Fallback/identity constants
    "_DEFAULT_TD", "_OFFSET",
    # Sampling/network infra
    "_SAMPLING_THRESHOLD", "_DEGREE_CAP_PER_ACTIVITY",
})


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def auto_bounds(
    config: PersonaConfig | None = None,
    margin: float = 0.5,
    include_config: bool = True,
    include_engine: bool = True,
    include_theories: bool = True,
    exclude: frozenset[str] = frozenset(),
) -> tuple[SobolParameter, ...]:
    """
    Auto-generate SobolParameter bounds from current defaults.

    Bounds are computed as default * (1 ± margin), clipped to validation
    ranges. Adapts automatically when PersonaConfig defaults or engine
    constants change.

    Args:
        config: PersonaConfig to use as center. None = default config.
        margin: Fractional variation around default (0.5 = ±50%).
        include_config: Include PersonaConfig float fields.
        include_engine: Include SimulationEngine constants.
        include_theories: Include theory module constants.
        exclude: Parameter names to exclude (e.g., {"config.dropout_base_rate"}).

    Returns:
        Tuple of SobolParameter ready for SobolAnalyzer or TraitCalibrator.
    """
    config = config or PersonaConfig()
    params: list[SobolParameter] = []

    if include_config:
        params.extend(_bounds_from_config(config, margin))

    engine = SimulationEngine(environment=ODLEnvironment(), seed=0)

    if include_engine:
        params.extend(_bounds_from_constants(engine.cfg, "engine", margin))

    if include_theories:
        for alias, engine_attr in MODULE_ALIASES.items():
            module = getattr(engine, engine_attr)
            params.extend(_bounds_from_constants(module, alias, margin))

    # Filter exclusions
    filtered = [p for p in params if p.name not in exclude]
    return tuple(filtered)


# ─────────────────────────────────────────────
# Config bounds
# ─────────────────────────────────────────────

def _bounds_from_config(
    config: PersonaConfig,
    margin: float,
) -> list[SobolParameter]:
    """Generate bounds for PersonaConfig float fields."""
    params: list[SobolParameter] = []

    for f in fields(config):
        val = getattr(config, f.name)
        if not isinstance(val, float):
            continue

        lo, hi = _compute_bounds(val, margin)

        # Clip to validation range if known
        if f.name in _CONFIG_RANGES:
            range_lo, range_hi = _CONFIG_RANGES[f.name]
            lo = max(lo, range_lo)
            hi = min(hi, range_hi)

        if lo >= hi:
            continue

        params.append(SobolParameter(
            name=f"config.{f.name}",
            lower=round(lo, 6),
            upper=round(hi, 6),
            description=f"PersonaConfig.{f.name}",
        ))

    return params


# ─────────────────────────────────────────────
# Engine/theory constant bounds
# ─────────────────────────────────────────────

def _bounds_from_constants(
    obj: object,
    prefix: str,
    margin: float,
) -> list[SobolParameter]:
    """Generate bounds for _UPPERCASE float constants on a class instance."""
    params: list[SobolParameter] = []

    for attr in dir(obj):
        if not attr.startswith("_") or not attr[1:2].isupper():
            continue
        if attr in _NON_TUNEABLE:
            continue

        val = getattr(obj, attr)
        if not isinstance(val, float):
            continue
        if val == 0.0:
            continue

        lo, hi = _compute_bounds(val, margin)

        # Ensure positive range for positive defaults
        if val > 0:
            lo = max(lo, val * 0.1)  # floor at 10% of default

        if lo >= hi:
            continue

        desc = attr.lstrip("_").replace("_", " ").capitalize()
        params.append(SobolParameter(
            name=f"{prefix}.{attr}",
            lower=round(lo, 6),
            upper=round(hi, 6),
            description=desc,
        ))

    return params


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _compute_bounds(default: float, margin: float) -> tuple[float, float]:
    """Compute (lower, upper) from default ± margin fraction."""
    if default > 0:
        return (default * (1 - margin), default * (1 + margin))
    elif default < 0:
        # Negative: invert so lower < upper
        return (default * (1 + margin), default * (1 - margin))
    else:
        return (0.0, 0.0)
