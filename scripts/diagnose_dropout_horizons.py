"""Trace long-horizon engagement and run explicitly scoped model ablations.

Run as ``python -m scripts.diagnose_dropout_horizons --output PATH``.
The observer patches only the supplied engine's instances, restores every method
on exit, and consumes no random draws. Ablations are diagnostic counterfactuals,
not proposed defaults or estimates of causal effects in real learners.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from scripts.measure_dropout_horizons import _provenance
from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig
from synthed.simulation.semester import MultiSemesterRunner, SemesterCarryOverConfig
from synthed.validation.validator import _STANDARD_TESTS

logger = logging.getLogger(__name__)


def _write_checkpoint(output: Path, data: dict) -> None:
    """Publish complete JSON atomically, preserving the previous file on errors."""
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                prefix=output.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _skipped_validation_checks(students, outcomes, histories, report) -> list[dict]:
    """Explain absent default checks without changing validator results or grades.

    Eligibility gates mirror validator.py: correlations need >10 pairs, SDT
    needs >=5 in each group, and temporal comparisons need both outcome groups.
    This CLI uses default reference settings and no LLM, so optional outcome-rate
    references and backstory checks are outside this manifest.
    """
    emitted = {r["test"] for r in report["results"]}
    outcome_map = {o["student_id"]: o for o in outcomes}
    eligibility = {}
    for attr, outcome, name, *_ in _STANDARD_TESTS:
        pairs = sum(s["student_id"] in outcome_map and attr in s
                    and outcome_map[s["student_id"]].get(outcome) not in (None, "") for s in students)
        eligibility[name] = ({"pairs": pairs}, {"pairs": 11})
    for name, fields in (("gpa_dropout_correlation", ("final_gpa", "has_dropped_out")),
                         ("engagement_gpa_correlation", ("mean_engagement", "final_gpa"))):
        pairs = sum(all(o.get(k) is not None for k in fields) for o in outcomes)
        eligibility[name] = ({"pairs": pairs}, {"pairs": 11})
    motivation_counts = {
        m: sum(s.get("motivation_type") == m and s["student_id"] in outcome_map
               and outcome_map[s["student_id"]].get("final_engagement") is not None for s in students)
        for m in ("intrinsic", "amotivation")}
    eligibility["sdt_intrinsic_vs_amotivation"] = (motivation_counts, {m: 5 for m in motivation_counts})
    cohorts = {"dropped": 0, "retained": 0}
    timed_dropouts = 0
    for o in outcomes:
        if o["student_id"] in histories:
            dropped = o.get("has_dropped_out", False)
            cohorts["dropped" if dropped else "retained"] += 1
            timed_dropouts += bool(dropped and o.get("dropout_week") is not None)
    for name in ("engagement_trajectory_divergence", "dropout_negative_trend_rate"):
        eligibility[name] = (cohorts, {"dropped": 1, "retained": 1})
    eligibility["dropout_early_attrition"] = ({"timed_dropouts": timed_dropouts}, {"timed_dropouts": 1})
    for name in ("age_distribution", "gender_distribution", "employment_rate", "k_anonymity"):
        eligibility[name] = ({"students": len(students)}, {"students": 1})
    eligibility["gpa_distribution"] = ({"prior_gpas": sum("prior_gpa" in s for s in students)}, {"prior_gpas": 1})
    eligibility["dropout_rate"] = ({"outcomes": len(outcomes)}, {"outcomes": 1})
    eligibility["baulke_phase_distribution"] = (
        {"phases": sum(o.get("final_dropout_phase") is not None for o in outcomes)}, {"phases": 1})
    return [{"test": name, "eligible_counts": counts, "minimum_counts": minima,
             "reason": ("insufficient eligible observations" if any(counts[k] < v for k, v in minima.items())
                        else "not emitted despite available inputs")}
            for name, (counts, minima) in eligibility.items() if name not in emitted]


def _finite_validation(report: dict) -> tuple[dict, list[str]]:
    """Encode undefined statistics as null and list their paths explicitly."""
    undefined = []

    def clean(value, path):
        """Copy the report recursively, retaining failed checks and their details."""
        if isinstance(value, float) and not math.isfinite(value):
            undefined.append(path)
            return None
        if isinstance(value, dict):
            return {k: clean(v, f"{path}.{k}" if path else k) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v, f"{path}[{i}]") for i, v in enumerate(value)]
        return value

    return clean(report, ""), undefined


def _state_snapshot(state) -> dict:
    """Copy diagnostic scalars before later simulation steps mutate the state."""
    return {
        "engagement": state.current_engagement,
        "phase": state.dropout_phase,
        "cost_benefit": state.perceived_cost_benefit,
        "exhaustion": state.exhaustion.exhaustion_level,
        "mastery": state.perceived_mastery,
    }


def _population_summary(snapshots: list[dict]) -> dict:
    """Describe the observed risk set; empty sets have no invented averages."""
    return {
        "count": len(snapshots),
        "phase_counts": dict(sorted(Counter(s["phase"] for s in snapshots).items())),
        **{f"mean_{key}": mean(s[key] for s in snapshots) if snapshots else None
           for key in ("engagement", "cost_benefit", "exhaustion", "mastery")},
    }


class EngagementTrace:
    """Accumulate term-level sums on the actual active student-week risk set."""

    def __init__(self):
        """Create an empty trace for one multi-semester simulation."""
        self.semester = 0
        self.rows = defaultdict(self._empty_row)

    @staticmethod
    def _empty_row() -> dict:
        """Allocate independent counters for a term when first observed."""
        return {
            "student_weeks": 0, "raw": defaultdict(float), "applied": defaultdict(float),
            "update_delta": 0.0, "peer_delta": 0.0, "entry": [], "survivors": [],
            "at_risk": 0, "dropped": 0, "dropout_week_counts": {},
        }

    def summaries(self) -> list[dict]:
        """Return means per active student-week, preserving raw risk-set counts."""
        result = []
        for term, row in sorted(self.rows.items()):
            n = row["student_weeks"]
            result.append({
                "semester": term, "student_weeks": n,
                "at_risk": row["at_risk"], "dropped": row["dropped"],
                "conditional_dropout_rate": row["dropped"] / row["at_risk"] if row["at_risk"] else None,
                "dropout_week_counts": row["dropout_week_counts"],
                "entry": _population_summary(row["entry"]),
                "survivors": _population_summary(row["survivors"]),
                "mean_raw_theory_delta": {k: v / n for k, v in row["raw"].items()} if n else {},
                "mean_applied_theory_delta": {k: v / n for k, v in row["applied"].items()} if n else {},
                "mean_update_delta": row["update_delta"] / n if n else None,
                "mean_inline_and_clipping_delta": (
                    (row["update_delta"] - sum(row["applied"].values())) / n if n else None),
                "mean_peer_delta": row["peer_delta"] / n if n else None,
            })
        return result


@contextmanager
def trace_engagement(engine, neutralize: str | None = None):
    """Observe real calls; optionally zero one return after all its side effects.

    ``neutralize`` names an engagement theory class. Other methods, state
    updates, and random draws within that class still execute. Subsequent
    trajectories and random-stream positions can diverge from the baseline.
    The inline residual combines academic/streak/exam effects and floor/clipping;
    it must not be interpreted as one isolated mechanism.
    """
    names = {type(t).__name__ for t in engine._engagement_theories}
    if neutralize is not None and neutralize not in names:
        raise ValueError(f"Unknown engagement theory: {neutralize}")
    trace = EngagementTrace()
    original_run = engine.run
    original_withdrawal = engine.unavoidable_withdrawal.check_withdrawal
    original_update = engine._update_engagement
    original_peer = engine.epstein_axtell.on_post_peer_step

    def run(students, *args, **kwargs):
        """Bracket each term and snapshot survivors before carry-over mutates them."""
        trace.semester += 1
        row = trace.rows[trace.semester]
        row["at_risk"] = len(students)
        records, states, network = original_run(students, *args, **kwargs)
        row["dropped"] = sum(s.has_dropped_out for s in states.values())
        row["survivors"] = [_state_snapshot(s) for s in states.values() if not s.has_dropped_out]
        row["dropout_week_counts"] = dict(sorted(Counter(
            s.dropout_week for s in states.values() if s.has_dropped_out).items()))
        return records, states, network

    def withdrawal(student, state, week, rng):
        """Snapshot all term entrants before even external withdrawal can occur."""
        if week == 1:
            trace.rows[trace.semester]["entry"].append(_state_snapshot(state))
        return original_withdrawal(student, state, week, rng)

    def update(ctx):
        """Measure the actual engagement update without copying engine formulas."""
        row = trace.rows[trace.semester]
        row["student_weeks"] += 1
        before = ctx.state.current_engagement
        original_update(ctx)
        row["update_delta"] += ctx.state.current_engagement - before

    def peer(ctx):
        """Measure net peer influence after its own clipping and contagion."""
        before = ctx.state.current_engagement
        original_peer(ctx)
        trace.rows[trace.semester]["peer_delta"] += ctx.state.current_engagement - before

    def wrap_contribution(original, name):
        """Bind a distinct original method and class label for each wrapper."""
        def contribute(ctx):
            """Preserve state and RNG effects even when neutralizing the return."""
            raw = original(ctx)
            applied = 0.0 if name == neutralize else raw
            row = trace.rows[trace.semester]
            row["raw"][name] += raw
            row["applied"][name] += applied
            return applied
        return contribute

    with ExitStack() as stack:
        for theory in engine._engagement_theories:
            stack.enter_context(patch.object(theory, "contribute_engagement_delta",
                wrap_contribution(theory.contribute_engagement_delta, type(theory).__name__)))
        stack.enter_context(patch.object(engine, "run", run))
        stack.enter_context(patch.object(engine.unavoidable_withdrawal, "check_withdrawal", withdrawal))
        stack.enter_context(patch.object(engine, "_update_engagement", update))
        stack.enter_context(patch.object(engine.epstein_axtell, "on_post_peer_step", peer))
        yield trace


def run_diagnostic(n_students: int, seed: int, scenario: str) -> dict:
    """Run and validate a fresh default model or one explicit diagnostic variant."""
    config = PipelineConfig(seed=seed, n_semesters=4, output_dir=None)
    carry_over = SemesterCarryOverConfig()
    neutralize = None
    if scenario.startswith("without:"):
        neutralize = scenario.removeprefix("without:")
    elif scenario == "no_missed_streak_penalty":
        config = replace(config, engine_config=replace(config.engine_config, _MISSED_STREAK_PENALTY=0.0))
    elif scenario == "reset_phase_between_terms":
        # Phase 5 is terminal; surviving phases are 0..4. A regression of 5
        # resets them all to zero. This deliberately removes phase memory only.
        carry_over = replace(carry_over, dropout_phase_regression=5)
    elif scenario != "baseline":
        raise ValueError(f"Unknown diagnostic scenario: {scenario}")
    pipeline = SynthEdPipeline(config=config, _calibration_mode=True)
    students = pipeline.factory.generate_population(n=n_students)
    with trace_engagement(pipeline.engine, neutralize) as trace:
        result = MultiSemesterRunner(pipeline.engine, 4, carry_over=carry_over).run(students)
    validation_data = pipeline._prepare_validation_data(
        students, result.final_states, result.final_network, engagement_histories=result.engagement_histories)
    validation = pipeline.validator.validate_all(*validation_data, total_weeks=4 * config.environment.total_weeks)
    skipped_checks = _skipped_validation_checks(*validation_data, validation)
    validation, undefined_fields = _finite_validation(validation)
    rows = trace.summaries()
    cumulative = 0
    for row in rows:
        cumulative += row["dropped"]
        row["cumulative_dropout_rate"] = cumulative / n_students
    return {"seed": seed, "scenario": scenario, "config": config.to_dict(),
            "resolved_carry_over": asdict(carry_over), "semesters": rows, "validation": validation,
            "undefined_validation_fields": undefined_fields, "skipped_validation_checks": skipped_checks}


def measure(n_students: int, seeds: list[int], scenarios: list[str], output: Path) -> None:
    """Save complete runs and provenance; failures propagate, never become zeros."""
    if n_students < 1 or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Use a positive population and nonempty, distinct seeds")
    if not scenarios or len(set(scenarios)) != len(scenarios):
        raise ValueError("Use nonempty, distinct scenarios")
    root = Path(__file__).resolve().parents[1]
    data = {**_provenance(root), "n_students": n_students, "seeds": seeds,
            "scenarios": scenarios, "expected_runs": len(seeds) * len(scenarios),
            "complete": False, "runs": []}
    data["source_sha256"][Path(__file__).relative_to(root).as_posix()] = hashlib.sha256(
        Path(__file__).read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        for seed in seeds:
            run = run_diagnostic(n_students, seed, scenario)
            data["runs"].append(run)
            data["complete"] = len(data["runs"]) == data["expected_runs"]
            _write_checkpoint(output, data)
            logger.info("%s seed=%d cumulative=%s", scenario, seed,
                        [round(s["cumulative_dropout_rate"], 4) for s in run["semesters"]])


def main() -> None:
    """Use the existing five-seed, 500-student design unless explicitly overridden."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-students", type=int, default=500)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(42, 47)))
    parser.add_argument("--scenarios", nargs="+", default=["baseline"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    measure(args.n_students, args.seeds, args.scenarios, args.output)


if __name__ == "__main__":
    main()
