#!/usr/bin/env python3
"""
SynthEd — Quick start script.

Usage:
    python run_pipeline.py                     # Default: 200 students, no LLM
    python run_pipeline.py --n 500             # 500 students
    python run_pipeline.py --n 100 --llm       # 100 students with LLM enrichment
    python run_pipeline.py --config configs/default.json
"""

import argparse
import json
from pathlib import Path

from synthed.utils.log_config import configure_logging

from synthed.agents.persona import PersonaConfig
from synthed.validation.validator import ReferenceStatistics
from synthed.pipeline import SynthEdPipeline


def _cli_confirm(warning: str) -> bool:
    """Prompt user for confirmation when estimated cost exceeds threshold."""
    response = input(f"\nWARNING: {warning}\nProceed? [y/N]: ")
    return response.strip().lower() in ("y", "yes")


def main():
    parser = argparse.ArgumentParser(description="SynthEd: Synthetic Educational Data Generator")
    parser.add_argument("--n", type=int, default=200, help="Number of students (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default="./output", help="Output directory")
    parser.add_argument("--llm", action="store_true", help="Enable LLM enrichment (requires OPENAI_API_KEY)")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="LLM model (default: gpt-4o-mini)")
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="OpenAI-compatible API base URL (e.g., http://localhost:11434/v1 for Ollama)",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to JSON config file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose/debug logging")
    parser.add_argument(
        "--target-dropout", type=float, nargs=2, metavar=("LOWER", "UPPER"),
        help="Target dropout range, e.g. --target-dropout 0.40 0.60",
    )
    parser.add_argument(
        "--cost-threshold", type=float, default=1.0,
        help="LLM cost warning threshold in USD (default: 1.0)",
    )
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)

    # Load config if provided
    if args.config:
        config_data = json.loads(Path(args.config).read_text())
        persona_config = PersonaConfig(**config_data.get("persona_config", {}))
        reference_stats = ReferenceStatistics(**config_data.get("reference_statistics", {}))
        sim_config = config_data.get("simulation", {})
        n_students = sim_config.get("n_students", args.n)
        seed = sim_config.get("seed", args.seed)
        use_llm = sim_config.get("use_llm", args.llm)
        llm_model = sim_config.get("llm_model", args.model)
    else:
        persona_config = PersonaConfig()
        reference_stats = ReferenceStatistics()
        n_students = args.n
        seed = args.seed
        use_llm = args.llm
        llm_model = args.model

    # Parse and validate target dropout range from CLI
    target_dropout_range = None
    if args.target_dropout:
        lo, hi = args.target_dropout
        if not (0.0 < lo < hi < 1.0):
            parser.error(
                f"--target-dropout: expected 0 < LOWER < UPPER < 1, got {lo} {hi}"
            )
        target_dropout_range = (lo, hi)

    print("=" * 60)
    print("  SynthEd: Agent-Based Synthetic Educational Data Generator")
    print("=" * 60)
    print(f"  Students: {n_students} | Seed: {seed} | LLM: {'ON' if use_llm else 'OFF'}")
    if target_dropout_range:
        print(f"  Target dropout: {target_dropout_range[0]:.0%}-{target_dropout_range[1]:.0%}")
    print(f"  Output: {args.output}")
    print("=" * 60 + "\n")

    pipeline = SynthEdPipeline(
        persona_config=persona_config,
        reference_stats=reference_stats,
        output_dir=args.output,
        llm_model=llm_model,
        llm_base_url=args.base_url,
        use_llm=use_llm,
        seed=seed,
        target_dropout_range=target_dropout_range,
        cost_threshold=args.cost_threshold,
        confirm_callback=_cli_confirm if use_llm else None,
    )

    report = pipeline.run(n_students=n_students, enrich_personas=use_llm)

    # Print summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    sim = report.get("simulation_summary", {})
    val = report.get("validation", {}).get("summary", {})
    print(f"  Population: {n_students} students")
    print(f"  Interactions: {len(report.get('exported_files', {}))} files exported")
    print(f"  Dropout rate: {sim.get('dropout_rate', 0):.1%}")
    if "dropout_targeting" in report:
        dt = report["dropout_targeting"]
        lo, hi = dt["target_range"]
        actual = sim.get("dropout_rate", 0)
        in_range = lo <= actual <= hi
        print(f"  Target range: {lo:.0%}-{hi:.0%} ({'HIT' if in_range else 'MISS'})")
    print(f"  Validation: {val.get('overall_quality', 'N/A')}")
    print(f"  Tests: {val.get('passed', 0)}/{val.get('total_tests', 0)} passed")
    timing = report.get("timing", {})
    total_time = sum(timing.values())
    print(f"  Total time: {total_time:.1f}s")
    if report.get("llm_costs"):
        print(f"  LLM cost: ${report['llm_costs']['estimated_cost_usd']:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
