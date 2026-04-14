#!/usr/bin/env python
"""Run NSGA-II calibration for the default benchmark profile.

Usage:
    python run_calibration.py                    # Full run
    python run_calibration.py --quick            # Quick test (~20 min)
    python run_calibration.py --profile default  # Single profile (only 'default' available)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

from synthed.analysis.nsga2_calibrator import NSGAIICalibrator
from synthed.analysis.sobol_sensitivity import SobolAnalyzer, SobolRanking
from synthed.benchmarks.profiles import PROFILES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROFILE_NAMES = ["default"]

OUTPUT_DIR = Path("calibration_output")


def run_sobol(n_students: int, seed: int, n_workers: int = 1, n_samples: int = 128) -> list[SobolRanking]:
    """Run single Sobol analysis and return dropout rankings."""
    logger.info("Running Sobol analysis (n_students=%d, n_samples=%d, n_workers=%d)...", n_students, n_samples, n_workers)
    t0 = time.time()
    analyzer = SobolAnalyzer(n_students=n_students, seed=seed, n_workers=n_workers)
    results = analyzer.run(n_samples=n_samples)
    dropout_result = next(r for r in results if r.metric == "dropout_rate")
    rankings = analyzer.rank(dropout_result)
    logger.info("Sobol complete in %.1fs, %d parameters ranked", time.time() - t0, len(rankings))
    return rankings


def calibrate_profile(
    cal: NSGAIICalibrator,
    profile_name: str,
    rankings: list[SobolRanking],
    pop_size: int,
    n_trials: int,
    sobol_top_n: int,
) -> dict:
    """Calibrate one profile and return results as dict."""
    logger.info("=" * 60)
    logger.info("Calibrating: %s", profile_name)
    logger.info("=" * 60)

    t0 = time.time()
    result = cal.run(
        profile=profile_name,
        pop_size=pop_size,
        n_trials=n_trials,
        sobol_rankings=rankings,
        sobol_top_n=sobol_top_n,
    )
    cal_time = time.time() - t0

    # Validate
    validation_n = 1000
    validation_seeds = (42, 123, 456, 789, 2024, 1337, 7777, 9999, 31415, 27182)
    logger.info("Validating knee-point (n=%d, %d seeds)...", validation_n, len(validation_seeds))
    d_mean, d_std, g_mean, g_std = cal.validate_solution(
        result.knee_point,
        profile=profile_name,
        n_students=validation_n,
        seeds=validation_seeds,
    )

    profile = PROFILES[profile_name]
    lo, hi = profile.expected_dropout_range

    summary = {
        "profile": profile_name,
        "pareto_size": len(result.pareto_front),
        "n_evaluations": result.n_evaluations,
        "calibration_time_s": round(cal_time, 1),
        "knee_point": {
            "dropout_error": round(result.knee_point.dropout_error, 4),
            "gpa_error": round(result.knee_point.gpa_error, 4),
            "achieved_dropout": round(result.knee_point.achieved_dropout, 4),
            "achieved_gpa": round(result.knee_point.achieved_gpa, 4),
            "achieved_engagement": round(result.knee_point.achieved_engagement, 4),
            "params": {k: round(v, 6) for k, v in result.knee_point.params.items()},
        },
        "validation": {
            "dropout_mean": round(d_mean, 4),
            "dropout_std": round(d_std, 4),
            "gpa_mean": round(g_mean, 4),
            "gpa_std": round(g_std, 4),
            "in_range": lo <= d_mean <= hi,
            "expected_range": [lo, hi],
        },
        "parameter_names": list(result.parameter_names),
    }

    logger.info(
        "Result: Pareto=%d, knee dropout=%.1f%% (target %.0f%%-%.0f%%), "
        "gpa=%.2f, validation=%.1f%%+/-%.1f%%",
        len(result.pareto_front),
        result.knee_point.achieved_dropout * 100,
        lo * 100, hi * 100,
        result.knee_point.achieved_gpa,
        d_mean * 100, d_std * 100,
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description="NSGA-II benchmark calibration")
    parser.add_argument("--quick", action="store_true", help="Quick test run")
    parser.add_argument("--profile", type=str, help="Profile name (default: 'default')")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel workers (capped at CPU count)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    args.workers = max(1, min(args.workers, os.cpu_count() or 8))

    if args.quick:
        n_students, pop_size, n_trials, sobol_top_n, sobol_n_samples = 100, 20, 500, 10, 128
    else:
        n_students, pop_size, n_trials, sobol_top_n, sobol_n_samples = 500, 200, 62_000, 20, 512

    profiles = [args.profile] if args.profile else PROFILE_NAMES
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Step 1: Sobol (once)
    rankings = run_sobol(n_students=n_students, seed=args.seed, n_workers=args.workers, n_samples=sobol_n_samples)

    # Step 2: Calibrate each profile
    cal = NSGAIICalibrator(n_students=n_students, seed=args.seed, n_workers=args.workers)
    all_results = []
    total_t0 = time.time()

    for name in profiles:
        try:
            summary = calibrate_profile(
                cal, name, rankings, pop_size, n_trials, sobol_top_n,
            )
            all_results.append(summary)

            # Save per-profile JSON
            out_file = OUTPUT_DIR / f"nsga2_{name}.json"
            out_file.write_text(json.dumps(summary, indent=2))
            logger.info("Saved: %s", out_file)

        except Exception as e:
            logger.error("Failed to calibrate %s: %s", name, e)
            all_results.append({"profile": name, "error": str(e)})

    # Summary
    total_time = time.time() - total_t0
    logger.info("=" * 60)
    logger.info("CALIBRATION COMPLETE (%.1f min)", total_time / 60)
    logger.info("=" * 60)

    for r in all_results:
        if "error" in r:
            logger.info("  %s: FAILED — %s", r["profile"], r["error"])
        else:
            v = r["validation"]
            logger.info(
                "  %s: dropout=%.1f%% +/-%.1f%% (range %.0f%%-%.0f%%) %s",
                r["profile"],
                v["dropout_mean"] * 100,
                v["dropout_std"] * 100,
                v["expected_range"][0] * 100,
                v["expected_range"][1] * 100,
                "IN RANGE" if v["in_range"] else "OUT OF RANGE",
            )

    # Save combined
    combined = OUTPUT_DIR / "nsga2_all_profiles.json"
    combined.write_text(json.dumps(all_results, indent=2))
    logger.info("Combined results: %s", combined)


if __name__ == "__main__":
    main()
