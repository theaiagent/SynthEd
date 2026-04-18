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
from synthed.analysis.pareto_utils import compare_knee_points
from synthed.analysis.sobol_sensitivity import SobolAnalyzer, SobolRanking
from synthed.benchmarks.profiles import PROFILES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROFILE_NAMES = ["default"]

CALIBRATION_SEEDS = (42, 2024)

GPA_FORCE_INCLUDE = frozenset({
    "grading.grade_floor",
    "grading.pass_threshold",
    "engine._ASSIGN_GPA_WEIGHT",
    "engine._EXAM_GPA_WEIGHT",
})

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
    quick_mode: bool = False,
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
        force_include=GPA_FORCE_INCLUDE,
    )
    cal_time = time.time() - t0

    # Re-evaluate Pareto front for noise-free knee-point selection
    if not quick_mode:
        logger.info("Re-evaluating Pareto front (n=2000, 3 seeds)...")
        reeval_result = cal.reevaluate_pareto_front(
            pareto_front=result.pareto_front,
            profile=profile_name,
            n_students=2000,
            seeds=(42, 123, 456),
        )
        knee_for_validation = reeval_result.knee_point
    else:
        knee_for_validation = result.knee_point

    # Validate
    validation_n = 1000
    validation_seeds = (42, 123, 456, 789, 2024, 1337, 7777, 9999, 31415, 27182)
    logger.info("Validating knee-point (n=%d, %d seeds)...", validation_n, len(validation_seeds))
    d_mean, d_std, g_mean, g_std = cal.validate_solution(
        knee_for_validation,
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
            "dropout_error": round(knee_for_validation.dropout_error, 4),
            "gpa_error": round(knee_for_validation.gpa_error, 4),
            "achieved_dropout": round(knee_for_validation.achieved_dropout, 4),
            "achieved_gpa": round(knee_for_validation.achieved_gpa, 4),
            "achieved_engagement": round(knee_for_validation.achieved_engagement, 4),
            "params": {k: round(v, 6) for k, v in knee_for_validation.params.items()},
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
        "hv_history": list(result.hv_history),
    }

    logger.info(
        "Result: Pareto=%d, knee dropout=%.1f%% (target %.0f%%-%.0f%%), "
        "gpa=%.2f, validation=%.1f%%+/-%.1f%%",
        len(result.pareto_front),
        knee_for_validation.achieved_dropout * 100,
        lo * 100, hi * 100,
        knee_for_validation.achieved_gpa,
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

    # Step 2: Calibrate each profile with replicated seeds
    calibration_seeds = CALIBRATION_SEEDS if not args.quick else (args.seed,)
    seed_knee_points: dict[str, dict] = {}
    # all_results entries have two shapes:
    #   success: {"seed": int, "profile": str, "pareto_size": int, "n_evaluations": int,
    #             "calibration_time_s": float, "knee_point": dict, "validation": dict,
    #             "parameter_names": list[str], "hv_history": list[float]}
    #   failure: {"seed": int, "profile": str, "error": str}
    # Consumers should branch on presence of "error" key.
    all_results: list[dict] = []

    for cal_seed in calibration_seeds:
        logger.info("=" * 60)
        logger.info("NSGA-II seed: %d", cal_seed)
        logger.info("=" * 60)

        cal = NSGAIICalibrator(n_students=n_students, seed=cal_seed, n_workers=args.workers)
        total_t0 = time.time()

        for name in profiles:
            try:
                summary = calibrate_profile(
                    cal, name, rankings, pop_size, n_trials, sobol_top_n,
                    quick_mode=args.quick,
                )
                seed_knee_points.setdefault(name, {})[cal_seed] = summary["knee_point"]
                all_results.append({"seed": cal_seed, **summary})

                out_file = OUTPUT_DIR / f"nsga2_{name}_seed{cal_seed}.json"
                out_file.write_text(json.dumps(summary, indent=2))
                logger.info("Saved: %s", out_file)

            except Exception as e:
                logger.error("Failed to calibrate %s (seed=%d): %s", name, cal_seed, e)
                all_results.append({"seed": cal_seed, "profile": name, "error": str(e)})

        total_time = time.time() - total_t0
        logger.info("Seed %d complete (%.1f min)", cal_seed, total_time / 60)

    # Compare knee-points across seeds (if replicated)
    if len(calibration_seeds) > 1:
        logger.info("=" * 60)
        logger.info("KNEE-POINT COMPARISON")
        logger.info("=" * 60)
        # NOTE: only compares the first two seeds. Sufficient for the current
        # 2-seed setup (CALIBRATION_SEEDS = (42, 2024)). When the seed count
        # grows (planned alongside the multi-objective calibration upgrade),
        # this should iterate over all combinations(seeds_list, 2) and persist
        # the full pairwise distance matrix to nsga2_all_profiles.json.
        for name, knees in seed_knee_points.items():
            if len(knees) >= 2:
                seeds_list = sorted(knees.keys())
                from synthed.analysis.pareto_utils import ParetoSolution
                sol_a = ParetoSolution(
                    params=knees[seeds_list[0]]["params"],
                    dropout_error=knees[seeds_list[0]]["dropout_error"],
                    gpa_error=knees[seeds_list[0]]["gpa_error"],
                    engagement_error=knees[seeds_list[0]].get("achieved_engagement", 0.5),
                    achieved_dropout=knees[seeds_list[0]]["achieved_dropout"],
                    achieved_gpa=knees[seeds_list[0]]["achieved_gpa"],
                    achieved_engagement=knees[seeds_list[0]].get("achieved_engagement", 0.5),
                )
                sol_b = ParetoSolution(
                    params=knees[seeds_list[1]]["params"],
                    dropout_error=knees[seeds_list[1]]["dropout_error"],
                    gpa_error=knees[seeds_list[1]]["gpa_error"],
                    engagement_error=knees[seeds_list[1]].get("achieved_engagement", 0.5),
                    achieved_dropout=knees[seeds_list[1]]["achieved_dropout"],
                    achieved_gpa=knees[seeds_list[1]]["achieved_gpa"],
                    achieved_engagement=knees[seeds_list[1]].get("achieved_engagement", 0.5),
                )
                dist = compare_knee_points(sol_a, sol_b)
                # The 0.1 threshold is informational, not a release gate. The model
                # is non-identifiable by construction (20 free params x 2 objectives
                # = 18-D null space); cross-seed parameter scatter is expected even
                # when output-level metrics match. See docs/CALIBRATION_METHODOLOGY.md
                # sec.7 (Limitations & Identifiability).
                status = "within informational threshold" if dist < 0.1 else "above informational threshold (expected for non-identifiable model)"
                logger.info("  %s: knee-point seed distance=%.4f — %s", name, dist, status)

    # Save combined
    combined = OUTPUT_DIR / "nsga2_all_profiles.json"
    combined.write_text(json.dumps(all_results, indent=2))
    logger.info("Combined results: %s", combined)


if __name__ == "__main__":
    main()
