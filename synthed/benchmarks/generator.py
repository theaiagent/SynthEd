"""Benchmark dataset generator for SynthEd profiles."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..pipeline import SynthEdPipeline
from .profiles import PROFILES, BenchmarkProfile

logger = logging.getLogger(__name__)


class BenchmarkGenerator:
    """Generate and validate benchmark datasets from pre-defined profiles."""

    def generate(
        self,
        profile_name: str,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """Generate a single benchmark dataset."""
        if profile_name not in PROFILES:
            available = ", ".join(PROFILES.keys())
            raise ValueError(
                f"Unknown profile '{profile_name}'. Available: {available}"
            )

        profile = PROFILES[profile_name]
        out = output_dir or f"./benchmarks/{profile_name}"

        logger.info("Generating benchmark: %s (%s)", profile.name, profile.description)

        pipeline = SynthEdPipeline(
            persona_config=profile.persona_config,
            environment=profile.environment,
            reference_stats=profile.reference_stats,
            output_dir=out,
            seed=profile.seed,
        )

        report = pipeline.run(n_students=profile.n_students)

        # Validate against expected range
        actual_dropout = report["simulation_summary"]["dropout_rate"]
        lo, hi = profile.expected_dropout_range
        in_range = lo <= actual_dropout <= hi

        report["benchmark_validation"] = {
            "profile": profile_name,
            "expected_dropout_range": profile.expected_dropout_range,
            "actual_dropout_rate": round(actual_dropout, 4),
            "in_expected_range": in_range,
        }

        if not in_range:
            logger.warning(
                "Benchmark %s: dropout %.1f%% outside expected range [%.0f%%-%.0f%%]",
                profile_name, actual_dropout * 100, lo * 100, hi * 100,
            )

        return report

    def generate_all(
        self,
        output_dir: str = "./benchmarks",
    ) -> list[dict[str, Any]]:
        """Generate all benchmark datasets."""
        results = []
        for name in PROFILES:
            report = self.generate(name, output_dir=f"{output_dir}/{name}")
            results.append(report)
        return results

    @staticmethod
    def list_profiles() -> dict[str, str]:
        """Return profile names and descriptions."""
        return {name: p.description for name, p in PROFILES.items()}
