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
from ..simulation.engine_config import EngineConfig
from ..simulation.grading import GradingConfig
from ..simulation.institutional import InstitutionalConfig

logger = logging.getLogger(__name__)

# Cached field name sets for override validation
_ENGINE_FIELDS: frozenset[str] = frozenset(f.name for f in fields(EngineConfig))
_INST_FIELDS: frozenset[str] = frozenset(f.name for f in fields(InstitutionalConfig))

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


def _extract_metrics(summary: dict) -> dict[str, float]:
    """Extract standard metrics from a pipeline simulation_summary dict."""
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
        "pass_rate": float(summary.get("pass_rate", 0.0)),
        "distinction_rate": float(summary.get("distinction_rate", 0.0)),
        "fail_rate": float(summary.get("fail_rate", 0.0)),
    }


def run_simulation_with_overrides(
    overrides: dict[str, float],
    n_students: int,
    seed: int,
    default_config: PersonaConfig,
    calibration_mode: bool = False,
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
        Dict with keys: dropout_rate, mean_engagement, mean_gpa, std_engagement,
        pass_rate, distinction_rate, fail_rate.
    """
    config_overrides: dict[str, float] = {}
    engine_overrides: dict[str, float] = {}
    theory_overrides: dict[str, dict[str, float]] = {}
    inst_overrides: dict[str, float] = {}
    grading_overrides: dict[str, float] = {}

    for key, value in overrides.items():
        prefix, _, attr = key.partition(".")
        if prefix == "config":
            config_overrides[attr] = value
        elif prefix == "engine":
            engine_overrides[attr] = value
        elif prefix == "inst":
            inst_overrides[attr] = value
        elif prefix == "grading":
            grading_overrides[attr] = value
        else:
            theory_overrides.setdefault(prefix, {})[attr] = value

    config = _build_config(default_config, config_overrides)
    if inst_overrides:
        filtered_inst = {}
        for attr in inst_overrides:
            if attr in _INST_FIELDS:
                filtered_inst[attr] = inst_overrides[attr]
            else:
                logger.warning("inst override '%s' not in InstitutionalConfig — ignored", attr)
        inst_config = replace(InstitutionalConfig(), **filtered_inst) if filtered_inst else None
    else:
        inst_config = None
    if grading_overrides:
        _grading_fields = {f.name for f in fields(GradingConfig)}
        for attr in grading_overrides:
            if attr not in _grading_fields:
                logger.warning("grading override '%s' not in GradingConfig — ignored", attr)
        filtered_grading = {k: v for k, v in grading_overrides.items() if k in _grading_fields}
        # Ensure distinction > pass when both are sampled independently
        if "pass_threshold" in filtered_grading and "distinction_threshold" in filtered_grading:
            lo, hi = sorted([filtered_grading["pass_threshold"], filtered_grading["distinction_threshold"]])
            filtered_grading["pass_threshold"] = lo
            filtered_grading["distinction_threshold"] = hi
        grading_config = replace(GradingConfig(), **filtered_grading) if filtered_grading else None
    else:
        grading_config = None

    if calibration_mode:
        pipeline = SynthEdPipeline(
            persona_config=config,
            output_dir=None,
            seed=seed,
            institutional_config=inst_config,
            grading_config=grading_config,
            _calibration_mode=True,
        )
        _apply_engine_overrides(pipeline, engine_overrides, theory_overrides)
        report = pipeline.run(n_students=n_students)

        return _extract_metrics(report["simulation_summary"])

    tmp_dir = tempfile.mkdtemp(prefix="synthed_analysis_")
    try:
        pipeline = SynthEdPipeline(
            persona_config=config,
            output_dir=tmp_dir,
            seed=seed,
            institutional_config=inst_config,
            grading_config=grading_config,
            _calibration_mode=False,
        )
        _apply_engine_overrides(pipeline, engine_overrides, theory_overrides)
        report = pipeline.run(n_students=n_students)

        return _extract_metrics(report["simulation_summary"])
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

    Engine constants live in a frozen ``EngineConfig`` on ``engine.cfg``.
    Overrides are applied via ``dataclasses.replace()`` — the engine object
    itself is mutable, so reassigning ``engine.cfg`` is safe.
    """
    engine = pipeline.engine

    if engine_overrides:
        filtered = {}
        for attr, value in engine_overrides.items():
            if attr in _ENGINE_FIELDS:
                filtered[attr] = value
            else:
                logger.warning("engine override '%s' not in EngineConfig — ignored", attr)
        if filtered:
            engine.cfg = replace(engine.cfg, **filtered)

    for module_alias, attrs in theory_overrides.items():
        engine_attr = MODULE_ALIASES.get(module_alias)
        if engine_attr is None:
            logger.warning("Unknown theory module alias: %s", module_alias)
            continue
        module = getattr(engine, engine_attr)
        for attr, value in attrs.items():
            if attr.startswith("__") or not hasattr(module, attr):
                logger.warning(
                    "theory override '%s.%s' not a known attribute — ignored",
                    module_alias, attr,
                )
                continue
            setattr(module, attr, value)
