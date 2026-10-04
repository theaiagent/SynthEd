"""Measure assignment-scope changes on independent runs of 1/2/4 semesters.

Run this same script before and after the fix. N=500 and seeds 42..46 retain
the targeting measurement design; neither is an empirical model parameter.
No calibration target is applied, so differences reflect the model change.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from dataclasses import replace
from pathlib import Path

from scripts.diagnose_dropout_horizons import _finite_validation, _write_checkpoint
from scripts.measure_dropout_horizons import _provenance
from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig

logger = logging.getLogger(__name__)


def measure(n_students: int, seeds: list[int], output: Path) -> None:
    """Save default-model statistics and full validation with generating hashes."""
    if n_students < 1 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Use a positive population and nonempty, distinct seeds")
    root = Path(__file__).resolve().parents[1]
    config = PipelineConfig(output_dir=None)
    horizons = (1, 2, 4)
    data = {**_provenance(root), "n_students": n_students, "seeds": seeds,
            "horizons": horizons, "config": config.to_dict(),
            "expected_runs": len(seeds) * len(horizons), "complete": False, "runs": []}
    for source in (Path(__file__), root / "scripts/diagnose_dropout_horizons.py"):
        data["source_sha256"][source.relative_to(root).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    for horizon in horizons:
        for seed in seeds:
            pipeline = SynthEdPipeline(config=replace(config, seed=seed, n_semesters=horizon),
                                       _calibration_mode=True)
            report = pipeline.run(n_students=n_students)
            validation, undefined = _finite_validation(report["validation"])
            data["runs"].append({"n_semesters": horizon, "seed": seed,
                                 "simulation_summary": report["simulation_summary"],
                                 "validation": validation, "undefined_validation_fields": undefined})
            data["complete"] = len(data["runs"]) == data["expected_runs"]
            _write_checkpoint(output, data)
            logger.info("semesters=%d seed=%d dropout=%.4f GPA=%s", horizon, seed,
                        report["simulation_summary"]["dropout_rate"],
                        report["simulation_summary"]["mean_final_gpa"])


def main() -> None:
    """Choose a reproducible population design and explicit evidence destination."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-students", type=int, default=500)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(42, 47)))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    measure(args.n_students, args.seeds, args.output)


if __name__ == "__main__":
    main()
