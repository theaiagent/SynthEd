"""Measure default-model dropout curves and conditional semester risks.

Run from the repository root with an explicit output path. The default design
retains the existing calibration sample size (500 students, five seeds). Seeds
42..46 and the grid are reproducible experimental choices, not model parameters.
Each four-semester run supplies its 1/2/3/4-semester prefixes; no future semester
affects an earlier dropout count. Validation runs on each completed cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import subprocess
from dataclasses import asdict, replace
from importlib.metadata import version
from pathlib import Path

from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig
from synthed.simulation.semester import MultiSemesterRunner, SemesterCarryOverConfig

logger = logging.getLogger(__name__)
_BASE_RATES = (0.01, 0.025, 0.05, 0.075, 0.10, 0.20, 0.30, 0.40,
               0.46, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95)


def _provenance(root: Path) -> dict:
    """Fingerprint generating code and dependencies at the start of a run."""
    source_files = sorted([*root.joinpath("synthed").rglob("*.py"), Path(__file__).resolve()])
    return {
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        ).strip(),
        "source_sha256": {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source_files
        },
        "python": platform.python_version(),
        "dependencies": {p: version(p) for p in ("numpy", "scipy", "uuid-utils")},
    }


def measure(n_students: int, seeds: list[int], base_rates: list[float],
            output: Path) -> None:
    """Save raw counts, validation summaries, settings, and source provenance."""
    if n_students < 1 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Use a positive population and nonempty, distinct seeds")
    if not base_rates or len(set(base_rates)) != len(base_rates):
        raise ValueError("Use nonempty, distinct base rates")
    root = Path(__file__).resolve().parents[1]
    config = PipelineConfig(n_semesters=4, output_dir=None)
    carry_over = SemesterCarryOverConfig()
    data = {
        **_provenance(root),
        "n_students": n_students, "seeds": seeds, "base_rates": base_rates,
        "config": config.to_dict(), "resolved_carry_over": asdict(carry_over), "runs": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    for rate in base_rates:
        for seed in seeds:
            cfg = replace(config, seed=seed, persona_config=replace(
                config.persona_config, dropout_base_rate=rate,
            ))
            pipeline = SynthEdPipeline(config=cfg, _calibration_mode=True)
            students = pipeline.factory.generate_population(n=n_students)
            result = MultiSemesterRunner(pipeline.engine, 4, carry_over=carry_over).run(students)
            cumulative = 0
            semesters = []
            for semester in result.semester_results:
                states = semester.states
                dropped = sum(s.has_dropped_out for s in states.values())
                cumulative += dropped
                semesters.append({
                    "semester": semester.semester_index + 1,
                    "at_risk": len(states), "dropped": dropped,
                    "conditional_dropout_rate": dropped / len(states) if states else None,
                    "cumulative_dropout_rate": cumulative / n_students,
                })
            validation = pipeline.validator.validate_all(
                *pipeline._prepare_validation_data(
                    students, result.final_states, result.final_network,
                    engagement_histories=result.engagement_histories,
                ), total_weeks=4 * config.environment.total_weeks,
            )
            data["runs"].append({
                "base_rate": rate, "seed": seed, "semesters": semesters,
                "validation_summary": validation["summary"],
            })
            # Checkpoint only completed runs; errors propagate rather than adding placeholders.
            output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        means = [sum(r["semesters"][s]["cumulative_dropout_rate"] for r in data["runs"]
                     if r["base_rate"] == rate) / len(seeds) for s in range(4)]
        logger.info("base=%.3f cumulative=%s", rate, [round(v, 4) for v in means])


def validate_targets(n_students: int, seeds: list[int], target_range: tuple[float, float],
                     curve_evidence: Path, output: Path) -> None:
    """Check target attainment on explicit seeds, preserving curve and code hashes."""
    if n_students < 1 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Use a positive population and nonempty, distinct seeds")
    root = Path(__file__).resolve().parents[1]
    config = PipelineConfig(output_dir=None, target_dropout_range=target_range)
    data = {
        **_provenance(root),
        "curve_evidence": curve_evidence.name,
        "curve_sha256": hashlib.sha256(curve_evidence.read_bytes()).hexdigest(),
        "config": config.to_dict(), "resolved_carry_over": asdict(SemesterCarryOverConfig()),
        "n_students": n_students, "seeds": seeds, "target_range": target_range, "runs": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    for n_semesters in (1, 2, 4):
        for seed in seeds:
            pipeline = SynthEdPipeline(config=replace(
                config, seed=seed, n_semesters=n_semesters,
            ), _calibration_mode=True)
            report = pipeline.run(n_students=n_students)
            data["runs"].append({
                "n_semesters": n_semesters, "seed": seed,
                "dropout_targeting": report["dropout_targeting"],
                "validation_summary": report["validation"]["summary"],
            })
            output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        rates = [r["dropout_targeting"]["actual_dropout_rate"] for r in data["runs"]
                 if r["n_semesters"] == n_semesters]
        logger.info("semesters=%d dropout=%s mean=%.4f", n_semesters, rates, sum(rates) / len(rates))


def main() -> None:
    """Parse the reproducible measurement design and write its evidence file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-students", type=int, default=500)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(42, 47)))
    parser.add_argument("--base-rates", type=float, nargs="+", default=list(_BASE_RATES))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-range", type=float, nargs=2)
    parser.add_argument("--curve-evidence", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logger.setLevel(logging.INFO)
    if args.target_range is not None:
        if args.curve_evidence is None:
            parser.error("--target-range requires --curve-evidence")
        validate_targets(args.n_students, args.seeds, tuple(args.target_range), args.curve_evidence, args.output)
    else:
        measure(args.n_students, args.seeds, args.base_rates, args.output)


if __name__ == "__main__":
    main()
