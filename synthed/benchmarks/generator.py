"""Benchmark dataset generator for SynthEd profiles."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from ..pipeline import SynthEdPipeline
from .profiles import PROFILES

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

    def generate_report(
        self,
        output_dir: str = "./benchmarks",
    ) -> str:
        """Run all profiles and produce a markdown comparison report.

        Returns the markdown text. Also writes benchmark_report.md and
        benchmark_results.json to *output_dir*.
        """
        start = time.time()
        results = self.generate_all(output_dir=output_dir)
        elapsed = time.time() - start

        md = self._format_report(results, elapsed)

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "benchmark_report.md").write_text(md, encoding="utf-8")
        (out / "benchmark_results.json").write_text(
            json.dumps(
                [r.get("benchmark_validation", {}) for r in results],
                indent=2,
            ),
            encoding="utf-8",
        )

        logger.info("Benchmark report saved to %s", out / "benchmark_report.md")
        return md

    @staticmethod
    def _format_report(results: list[dict[str, Any]], elapsed: float) -> str:
        """Build a markdown comparison table from benchmark results."""
        lines: list[str] = []
        lines.append("# SynthEd Benchmark Report")
        lines.append("")

        # Summary table
        lines.append("## Profile Comparison")
        lines.append("")
        lines.append(
            "| Profile | N | Dropout | Expected | In Range "
            "| GPA | Engagement | Validation | Time (s) |"
        )
        lines.append(
            "| --- | ---: | ---: | --- | :---: "
            "| ---: | ---: | --- | ---: |"
        )

        for report in results:
            bv = report.get("benchmark_validation", {})
            sim = report.get("simulation_summary", {})
            val = report.get("validation", {}).get("summary", {})
            timing = report.get("timing", {})
            total_time = sum(timing.values())

            profile_name = bv.get("profile", "?")
            n_students = sim.get("total_students", "?")
            dropout = sim.get("dropout_rate", 0)
            lo, hi = bv.get("expected_dropout_range", (0, 0))
            in_range = bv.get("in_expected_range", False)
            gpa = sim.get("mean_final_gpa")
            engagement = sim.get("mean_final_engagement")
            quality = val.get("overall_quality", "N/A")

            gpa_str = f"{gpa:.2f}" if gpa is not None else "-"
            eng_str = f"{engagement:.2f}" if engagement is not None else "-"
            lines.append(
                f"| {profile_name} | {n_students} "
                f"| {dropout:.1%} | {lo:.0%}-{hi:.0%} "
                f"| {'YES' if in_range else 'NO'} "
                f"| {gpa_str} | {eng_str} "
                f"| {quality} | {total_time:.1f} |"
            )

        lines.append("")

        # Per-profile details
        lines.append("## Profile Details")
        lines.append("")

        for report in results:
            bv = report.get("benchmark_validation", {})
            sim = report.get("simulation_summary", {})
            val = report.get("validation", {}).get("summary", {})
            profile_name = bv.get("profile", "?")
            profile = PROFILES.get(profile_name)

            lines.append(f"### {profile_name}")
            lines.append("")
            if profile:
                lines.append(f"> {profile.description}")
                lines.append("")

            lines.append(f"- **Students:** {sim.get('total_students', '?')}")
            lines.append(f"- **Dropout rate:** {sim.get('dropout_rate', 0):.1%}")
            lo, hi = bv.get("expected_dropout_range", (0, 0))
            lines.append(f"- **Expected range:** {lo:.0%}-{hi:.0%}")
            in_range = bv.get("in_expected_range", False)
            lines.append(f"- **In range:** {'Yes' if in_range else 'No'}")
            gpa = sim.get("mean_final_gpa")
            lines.append(f"- **Mean GPA:** {gpa:.2f}" if gpa is not None else "- **Mean GPA:** N/A")
            eng = sim.get("mean_final_engagement")
            lines.append(f"- **Mean engagement:** {eng:.2f}" if eng is not None else "- **Mean engagement:** N/A")
            lines.append(f"- **Retained:** {sim.get('retained_students', '?')}")
            mean_dw = sim.get("mean_dropout_week")
            lines.append(f"- **Mean dropout week:** {mean_dw:.1f}" if mean_dw is not None else "- **Mean dropout week:** N/A")
            lines.append(f"- **Validation:** {val.get('overall_quality', 'N/A')} ({val.get('passed', 0)}/{val.get('total_tests', 0)} tests)")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Generated in {elapsed:.1f}s*")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def list_profiles() -> dict[str, str]:
        """Return profile names and descriptions."""
        return {name: p.description for name, p in PROFILES.items()}

