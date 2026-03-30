"""
Sensitivity analysis for SynthEd simulation parameters.

Performs one-at-a-time (OAT) parameter sweeps to identify which
PersonaConfig and ODLEnvironment parameters most affect dropout rate.
"""

from __future__ import annotations

import copy
import logging
import shutil
import tempfile
from dataclasses import dataclass
from typing import Any

from ..agents.persona import PersonaConfig
from ..pipeline import SynthEdPipeline
from ..validation.validator import ReferenceStatistics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SensitivityResult:
    """Result of a single parameter perturbation."""
    parameter: str
    base_value: float
    perturbed_value: float
    base_dropout_rate: float
    perturbed_dropout_rate: float
    delta: float
    normalized_sensitivity: float  # |delta_output / delta_input|


# Sweepable parameters: name -> (min, max, attribute_path)
SWEEPABLE_PARAMS: dict[str, tuple[float, float]] = {
    "employment_rate": (0.3, 0.95),
    "financial_stress_mean": (0.2, 0.8),
    "self_regulation_mean": (0.2, 0.7),
    "digital_literacy_mean": (0.3, 0.8),
    "dropout_base_rate": (0.4, 0.9),
    "has_family_rate": (0.2, 0.7),
}


class SensitivityAnalyzer:
    """One-at-a-time (OAT) sensitivity analysis for SynthEd parameters."""

    def __init__(
        self,
        n_students: int = 200,
        seed: int = 42,
        base_config: PersonaConfig | None = None,
    ):
        self.n_students = n_students
        self.seed = seed
        self.base_config = base_config or PersonaConfig()

    def run_oat_sweep(
        self,
        n_steps: int = 5,
        params: dict[str, tuple[float, float]] | None = None,
    ) -> list[SensitivityResult]:
        """
        Run one-at-a-time sweep across all sweepable parameters.

        For each parameter, varies it from min to max in n_steps while
        holding all others at their base values. Returns sorted results
        by normalized sensitivity (most impactful first).
        """
        params = params or SWEEPABLE_PARAMS
        results: list[SensitivityResult] = []

        # Run baseline
        base_dropout = self._run_single(self.base_config)
        logger.info("Baseline dropout rate: %.1f%%", base_dropout * 100)

        for param_name, (lo, hi) in params.items():
            base_val = getattr(self.base_config, param_name)
            step_size = (hi - lo) / (n_steps - 1) if n_steps > 1 else 0

            for i in range(n_steps):
                perturbed_val = lo + i * step_size
                config = self._perturb(param_name, perturbed_val)
                perturbed_dropout = self._run_single(config)

                delta = perturbed_dropout - base_dropout
                input_delta = perturbed_val - base_val
                norm_sens = abs(delta / input_delta) if input_delta != 0 else 0.0

                results.append(SensitivityResult(
                    parameter=param_name,
                    base_value=base_val,
                    perturbed_value=round(perturbed_val, 3),
                    base_dropout_rate=round(base_dropout, 4),
                    perturbed_dropout_rate=round(perturbed_dropout, 4),
                    delta=round(delta, 4),
                    normalized_sensitivity=round(norm_sens, 4),
                ))

            logger.info("  %s sweep complete (%d steps)", param_name, n_steps)

        # Sort by max normalized sensitivity per parameter
        results.sort(key=lambda r: r.normalized_sensitivity, reverse=True)
        return results

    def tornado_chart_data(
        self,
        results: list[SensitivityResult],
    ) -> dict[str, dict[str, float]]:
        """
        Compute tornado chart data: for each parameter, the min and max
        dropout rate observed across all perturbation levels.
        """
        param_ranges: dict[str, dict[str, float]] = {}
        for r in results:
            if r.parameter not in param_ranges:
                param_ranges[r.parameter] = {
                    "min_dropout": r.perturbed_dropout_rate,
                    "max_dropout": r.perturbed_dropout_rate,
                    "base_dropout": r.base_dropout_rate,
                }
            else:
                entry = param_ranges[r.parameter]
                entry["min_dropout"] = min(entry["min_dropout"], r.perturbed_dropout_rate)
                entry["max_dropout"] = max(entry["max_dropout"], r.perturbed_dropout_rate)

        return param_ranges

    def _perturb(self, param_name: str, value: float) -> PersonaConfig:
        """Create a new PersonaConfig with one parameter changed."""
        from dataclasses import fields
        config_dict = {f.name: getattr(self.base_config, f.name) for f in fields(self.base_config)}
        config_dict[param_name] = value
        return PersonaConfig(**config_dict)

    def _run_single(self, config: PersonaConfig) -> float:
        """Run a single pipeline and return dropout rate."""
        tmp_dir = tempfile.mkdtemp(prefix="synthed_sens_")
        try:
            pipeline = SynthEdPipeline(
                persona_config=config,
                output_dir=tmp_dir,
                seed=self.seed,
            )
            report = pipeline.run(n_students=self.n_students)
            return report["simulation_summary"]["dropout_rate"]
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
