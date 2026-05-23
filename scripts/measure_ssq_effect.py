"""Empirical SSQ effect-size measurement for Issue #86.

Runs 50 seeds (41-90) at SSQ={0.2, 0.5, 0.8} with n=200 students each.
Measures dropout rate differences to calibrate test_baulke_institutional thresholds.
"""
import dataclasses
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synthed.pipeline import SynthEdPipeline
from synthed.simulation.institutional import InstitutionalConfig


def run_single(ssq: float, n: int, seed: int) -> float:
    """Run a single simulation and return dropout rate."""
    inst = dataclasses.replace(InstitutionalConfig(), support_services_quality=ssq)
    with tempfile.TemporaryDirectory() as tmp:
        pipeline = SynthEdPipeline(
            institutional_config=inst,
            output_dir=tmp,
            seed=seed,
        )
        report = pipeline.run(n_students=n)
    return report["simulation_summary"]["dropout_rate"]


def percentile(data: list[float], p: float) -> float:
    """Compute the p-th percentile of data."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    d = k - f
    return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])


def main():
    seeds = list(range(41, 91))  # 50 seeds
    ssq_values = [0.2, 0.5, 0.8]
    n_students = 200

    print("SSQ Effect-Size Measurement (Issue #86)")
    print(f"Seeds: {seeds[0]}..{seeds[-1]} ({len(seeds)} seeds)")
    print(f"N students per run: {n_students}")
    print(f"SSQ values: {ssq_values}")
    print(f"Total runs: {len(seeds) * len(ssq_values)}")
    print()

    results = {}
    start = time.time()

    for ssq in ssq_values:
        rates = []
        for i, seed in enumerate(seeds):
            rate = run_single(ssq, n_students, seed)
            rates.append(rate)
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start
                print(f"  SSQ={ssq}: {i+1}/{len(seeds)} done ({elapsed:.0f}s)")

        results[str(ssq)] = {
            "rates": rates,
            "mean": statistics.mean(rates),
            "std": statistics.stdev(rates),
            "min": min(rates),
            "p10": percentile(rates, 10),
            "p25": percentile(rates, 25),
            "p50": percentile(rates, 50),
            "p75": percentile(rates, 75),
            "p90": percentile(rates, 90),
            "max": max(rates),
        }

    elapsed = time.time() - start

    # Per-seed paired differences
    high_diffs = [results["0.5"]["rates"][i] - results["0.8"]["rates"][i] for i in range(len(seeds))]
    low_diffs = [results["0.2"]["rates"][i] - results["0.5"]["rates"][i] for i in range(len(seeds))]

    high_p10 = percentile(high_diffs, 10)
    low_p10 = percentile(low_diffs, 10)

    print(f"\n{'='*60}")
    print(f"RESULTS (elapsed: {elapsed:.0f}s)")
    print(f"{'='*60}")
    print()

    for ssq_str, stats in results.items():
        print(f"SSQ={ssq_str}:")
        print(f"  mean={stats['mean']:.4f}  std={stats['std']:.4f}")
        print(f"  min={stats['min']:.4f}  p10={stats['p10']:.4f}  p50={stats['p50']:.4f}  p90={stats['p90']:.4f}  max={stats['max']:.4f}")
        print()

    print("Effect sizes (paired per-seed):")
    print(f"  HIGH SSQ (0.5 vs 0.8): mean={statistics.mean(high_diffs):.4f}  std={statistics.stdev(high_diffs):.4f}  p10={high_p10:.4f}")
    print(f"  LOW  SSQ (0.2 vs 0.5): mean={statistics.mean(low_diffs):.4f}  std={statistics.stdev(low_diffs):.4f}  p10={low_p10:.4f}")
    print()

    # Decision table
    print("DECISION TABLE:")
    for label, p10_val in [("HIGH SSQ", high_p10), ("LOW SSQ", low_p10)]:
        if p10_val >= 0.012:
            decision = "Lower eps to 0.008, keep seeds=10"
        elif p10_val >= 0.007:
            decision = "Keep eps=0.010, document as confirmed-safe"
        elif p10_val >= 0.003:
            decision = "Raise seeds to 20, keep eps=0.010"
        else:
            decision = "ESCALATE: xfail + model-validity issue"
        print(f"  {label}: p10={p10_val:.4f} -> {decision}")

    # Save results
    output = {
        "config": {"seeds": seeds, "n_students": n_students, "ssq_values": ssq_values},
        "results": {k: {kk: vv for kk, vv in v.items()} for k, v in results.items()},
        "effect_sizes": {
            "high_ssq": {
                "mean": statistics.mean(high_diffs),
                "std": statistics.stdev(high_diffs),
                "p10": high_p10,
                "per_seed_diffs": high_diffs,
            },
            "low_ssq": {
                "mean": statistics.mean(low_diffs),
                "std": statistics.stdev(low_diffs),
                "p10": low_p10,
                "per_seed_diffs": low_diffs,
            },
        },
        "elapsed_seconds": elapsed,
    }

    out_path = Path(__file__).resolve().parent / "ssq_effect_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
