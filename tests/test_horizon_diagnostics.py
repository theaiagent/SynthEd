"""Guard the diagnostic observer against changing the stochastic model."""

import json
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig
from synthed.simulation.semester import MultiSemesterRunner


@pytest.mark.parametrize("seed", [42, 7, 123])
def test_observer_preserves_full_run_and_random_stream(seed):
    """Tracing preserves every record, state, edge and RNG draw across terms."""
    from scripts.diagnose_dropout_horizons import trace_engagement

    plain = SynthEdPipeline(config=PipelineConfig(seed=seed, output_dir=None))
    traced = SynthEdPipeline(config=PipelineConfig(seed=seed, output_dir=None))
    students = plain.factory.generate_population(n=100)
    expected = MultiSemesterRunner(plain.engine, 2).run(students)
    with trace_engagement(traced.engine) as trace:
        actual = MultiSemesterRunner(traced.engine, 2).run(students)

    assert actual.all_records == expected.all_records
    assert actual.final_states == expected.final_states
    assert actual.final_network._adjacency == expected.final_network._adjacency
    assert traced.engine.rng.bit_generator.state == plain.engine.rng.bit_generator.state
    assert "run" not in vars(traced.engine)
    assert "_update_engagement" not in vars(traced.engine)
    assert all("contribute_engagement_delta" not in vars(t)
               for t in traced.engine._engagement_theories)
    rows = trace.summaries()
    assert [r["semester"] for r in rows] == [1, 2]
    for row, semester in zip(rows, actual.semester_results):
        assert row["student_weeks"] == sum(len(s.weekly_engagement_history)
                                            for s in semester.states.values())
        assert row["mean_update_delta"] == pytest.approx(
            sum(row["mean_applied_theory_delta"].values()) + row["mean_inline_and_clipping_delta"])
        assert row["entry"]["count"] == len(semester.states)
        assert sum(row["entry"]["phase_counts"].values()) == len(semester.states)


def test_neutralizing_return_preserves_side_effects_and_restores_on_error():
    """A diagnostic ablation calls the real module and cleans up even on failure."""
    from scripts.diagnose_dropout_horizons import trace_engagement

    pipeline = SynthEdPipeline(config=PipelineConfig(output_dir=None))
    engine = pipeline.engine
    original = engine.bean_metzner.contribute_engagement_delta
    state = SimpleNamespace(calls=0)

    def contribution(ctx):
        """Represent a module with state changes alongside its returned delta."""
        ctx.state.calls += 1
        return -0.125

    engine.bean_metzner.contribute_engagement_delta = contribution
    try:
        with pytest.raises(RuntimeError, match="interrupted"):
            with trace_engagement(engine, neutralize="BeanMetznerPressure"):
                ctx = SimpleNamespace(state=state)
                assert engine.bean_metzner.contribute_engagement_delta(ctx) == 0.0
                assert state.calls == 1
                raise RuntimeError("interrupted")
        assert engine.bean_metzner.contribute_engagement_delta is contribution
        assert "run" not in vars(engine)
    finally:
        engine.bean_metzner.contribute_engagement_delta = original


def test_unknown_theory_fails_before_patching_engine():
    """Typos must fail explicitly instead of silently producing baseline data."""
    from scripts.diagnose_dropout_horizons import trace_engagement

    engine = SynthEdPipeline(config=PipelineConfig(output_dir=None)).engine
    before = asdict(engine.cfg)
    with pytest.raises(ValueError, match="Unknown engagement theory"):
        with trace_engagement(engine, neutralize="missing"):
            pytest.fail("Invalid ablation was accepted")
    assert "run" not in vars(engine)
    assert asdict(engine.cfg) == before


def test_entry_includes_students_withdrawing_before_behavior():
    """Term entry describes all entrants, including immediate external withdrawals."""
    from scripts.diagnose_dropout_horizons import trace_engagement
    from synthed.simulation.theories import UnavoidableWithdrawal

    config = PipelineConfig(output_dir=None)
    config = replace(config, environment=replace(config.environment, total_weeks=1))
    pipeline = SynthEdPipeline(config=config)
    pipeline.engine.unavoidable_withdrawal = UnavoidableWithdrawal(
        per_semester_probability=1.0, total_weeks=1)
    students = pipeline.factory.generate_population(n=12)
    with trace_engagement(pipeline.engine) as trace:
        pipeline.engine.run(students, weeks=1)
    row = trace.summaries()[0]
    assert row["entry"]["count"] == row["at_risk"] == 12
    assert row["dropped"] == 12
    assert row["student_weeks"] == 0
    assert row["mean_update_delta"] is None
    assert row["survivors"]["count"] == 0


def test_undefined_validation_statistics_are_explicit_in_strict_json():
    """Undefined correlations must remain visible without invalid JSON numbers."""
    from scripts.diagnose_dropout_horizons import _finite_validation

    original = {"results": [{"test": "constant", "statistic": float("nan"),
                             "p_value": float("inf"), "passed": False}]}
    safe, fields = _finite_validation(original)
    decoded = json.loads(json.dumps(safe, allow_nan=False))
    assert decoded["results"][0] == {
        "test": "constant", "statistic": None, "p_value": None, "passed": False}
    assert fields == ["results[0].statistic", "results[0].p_value"]
    assert original["results"][0]["statistic"] is not None


@pytest.mark.parametrize("scenario", ["baseline", "without:BeanMetznerPressure",
                                      "no_missed_streak_penalty", "reset_phase_between_terms"])
def test_diagnostic_runs_keep_validation_and_risk_sets(scenario):
    """Every supported intervention preserves cohort accounting and validation."""
    from scripts.diagnose_dropout_horizons import run_diagnostic

    for seed in (42, 7, 123):
        run = run_diagnostic(40, seed, scenario)
        json.dumps(run, allow_nan=False)
        assert run["validation"]["summary"]["total_tests"] > 0
        remaining = 40
        for row in run["semesters"]:
            assert row["at_risk"] == row["entry"]["count"] == remaining
            assert sum(row["dropout_week_counts"].values()) == row["dropped"]
            remaining -= row["dropped"]
            assert row["survivors"]["count"] == remaining
            assert row["cumulative_dropout_rate"] == pytest.approx(1 - remaining / 40)


@pytest.mark.parametrize("n_students", [1, 10])
def test_small_cohorts_report_skipped_checks_and_eligibility(n_students):
    """Small runs disclose absent checks instead of implying full coverage."""
    from scripts.diagnose_dropout_horizons import run_diagnostic

    run = run_diagnostic(n_students, 42, "baseline")
    skipped = {r["test"]: r for r in run["skipped_validation_checks"]}
    assert 0 <= skipped["engagement_gpa_correlation"]["eligible_counts"]["pairs"] <= n_students
    assert 0 <= skipped["gpa_dropout_correlation"]["eligible_counts"]["pairs"] <= n_students
    assert skipped["gpa_dropout_correlation"]["minimum_counts"]["pairs"] == 11
    assert skipped["engagement_gpa_correlation"]["reason"] == "insufficient eligible observations"
    assert "sdt_intrinsic_vs_amotivation" in skipped
    assert len(skipped) + run["validation"]["summary"]["total_tests"] == 22


@pytest.mark.parametrize("failure", ["serialization", "replace"])
def test_checkpoint_failure_preserves_previous_completed_runs(tmp_path, monkeypatch, failure):
    """Failed serialization or replacement cannot truncate the last good checkpoint."""
    from pathlib import Path
    from scripts.diagnose_dropout_horizons import _write_checkpoint

    output = tmp_path / "evidence.json"
    output.write_text('{"runs": ["previous"]}', encoding="utf-8")
    original = output.read_bytes()

    def fail_replace(self, target):
        """Simulate a failed final publication without altering either file."""
        raise OSError("publication failed")

    data = {"runs": [float("nan")]} if failure == "serialization" else {"runs": ["next"]}
    if failure == "replace":
        monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises((ValueError, OSError)):
        _write_checkpoint(output, data)
    assert output.read_bytes() == original
    assert list(tmp_path.iterdir()) == [output]
