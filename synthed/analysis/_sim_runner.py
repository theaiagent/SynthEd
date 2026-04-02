"""
Shared simulation runner for Sobol and trait calibration analyses.

Encapsulates the common pattern: build PersonaConfig with overrides,
create a fresh SynthEdPipeline, apply engine/theory overrides, run,
and extract metrics. Used by both SobolAnalyzer and TraitCalibrator.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import fields, replace

from ..agents.persona import PersonaConfig
from ..pipeline import SynthEdPipeline
from ..simulation.institutional import InstitutionalConfig

logger = logging.getLogger(__name__)

# Theory module alias → SimulationEngine attribute name
MODULE_ALIASES: dict[str, str] = {
    "tinto": "tinto",
    "bean": "bean_metzner",
    "kember": "kember",
    "baulke": "baulke",
    "sdt": "sdt",
    "rovai": "rovai",
    "garrison": "garrison",
    "gonzalez": "gonzalez",
    "moore": "moore",
    "epstein": "epstein_axtell",
}


def run_simulation_with_overrides(
    overrides: dict[str, float],
    n_students: int,
    seed: int,
    default_config: PersonaConfig,
) -> dict[str, float]:
    """
    Run a single SynthEd simulation with parameter overrides.

    Creates a fresh pipeline per call — instance-level attribute shadows
    do not persist across calls, ensuring isolation.

    Args:
        overrides: Parameter overrides keyed by "prefix.attr" names.
        n_students: Population size for the simulation.
        seed: RNG seed for reproducibility.
        default_config: Base PersonaConfig to apply config overrides onto.

    Returns:
        Dict with keys: dropout_rate, mean_engagement, mean_gpa.
    """
    config_overrides: dict[str, float] = {}
    engine_overrides: dict[str, float] = {}
    theory_overrides: dict[str, dict[str, float]] = {}
    inst_overrides: dict[str, float] = {}

    for key, value in overrides.items():
        prefix, _, attr = key.partition(".")
        if prefix == "config":
            config_overrides[attr] = value
        elif prefix == "engine":
            engine_overrides[attr] = value
        elif prefix == "inst":
            inst_overrides[attr] = value
        else:
            theory_overrides.setdefault(prefix, {})[attr] = value

    config = _build_config(default_config, config_overrides)
    inst_config = replace(InstitutionalConfig(), **inst_overrides) if inst_overrides else None

    tmp_dir = tempfile.mkdtemp(prefix="synthed_analysis_")
    try:
        pipeline = SynthEdPipeline(
            persona_config=config,
            output_dir=tmp_dir,
            seed=seed,
            institutional_config=inst_config,
        )
        _apply_engine_overrides(pipeline, engine_overrides, theory_overrides)
        report = pipeline.run(n_students=n_students)

        summary = report["simulation_summary"]
        engagement = summary.get("mean_final_engagement")
        gpa = summary.get("mean_final_gpa")
        engagement_std = summary.get("std_final_engagement")
        if engagement is None:
            logger.warning("mean_final_engagement missing from summary; defaulting to 0.0")
            engagement = 0.0
        if gpa is None:
            logger.warning("mean_final_gpa missing from summary; defaulting to 0.0")
            gpa = 0.0

        return {
            "dropout_rate": summary["dropout_rate"],
            "mean_engagement": float(engagement),
            "mean_gpa": float(gpa),
            "std_engagement": float(engagement_std) if engagement_std is not None else 0.0,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _build_config(
    default_config: PersonaConfig,
    overrides: dict[str, float],
) -> PersonaConfig:
    """Create PersonaConfig with overrides via dataclasses.replace()."""
    valid = {f.name for f in fields(PersonaConfig)}
    filtered = {}
    for attr, value in overrides.items():
        if attr in valid:
            filtered[attr] = value
        else:
            logger.warning("config override '%s' not in PersonaConfig — ignored", attr)
    return replace(default_config, **filtered)


def _apply_engine_overrides(
    pipeline: SynthEdPipeline,
    engine_overrides: dict[str, float],
    theory_overrides: dict[str, dict[str, float]],
) -> None:
    """
    Apply parameter overrides to the pipeline's engine and theory modules.

    Sets instance-level attributes that shadow class defaults without
    mutating the class itself. Safe because callers always create a fresh
    SynthEdPipeline (and therefore fresh engine + theory instances) per
    simulation call — instance shadows do not persist across runs.
    """
    engine = pipeline.engine

    for attr, value in engine_overrides.items():
        setattr(engine, attr, value)

    for module_alias, attrs in theory_overrides.items():
        engine_attr = MODULE_ALIASES.get(module_alias)
        if engine_attr is None:
            logger.warning("Unknown theory module alias: %s", module_alias)
            continue
        module = getattr(engine, engine_attr)
        for attr, value in attrs.items():
            setattr(module, attr, value)
