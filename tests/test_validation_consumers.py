"""Regression tests for assessment coverage in rendered reports and exports."""

import ast
import inspect
from types import SimpleNamespace

import pytest

from synthed.benchmarks.generator import BenchmarkGenerator
from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig


def _mixed_validation():
    """Provide legacy rows plus one explicitly unassessed modern row."""
    return {"summary": {"passed": 99, "total_tests": 99}, "results": [
        {"test": "age_distribution", "passed": True},
        {"test": "age_distribution", "passed": False},
        {"test": "privacy_uniqueness", "passed": False, "status": "not_assessed",
         "synthetic": None, "reference": None, "p_value": None,
         "details": "reason=<empty cohort>"},
    ]}


@pytest.mark.parametrize("lang,label", [("en", "Not assessed"), ("tr", "Değerlendirilemedi")])
def test_html_reports_assessed_denominator_and_visible_escaped_reason(monkeypatch, lang, label):
    """N/A is separate from failure and its reason remains escaped HTML."""
    pytest.importorskip("jinja2")
    from synthed.report.generator import ReportGenerator

    monkeypatch.setattr(ReportGenerator, "_render_charts", lambda *args: {})
    html = ReportGenerator({"validation": _mixed_validation()}, lang=lang).render_html()
    assert "1 / 2" in html
    assert label in html
    assert "reason=&lt;empty cohort&gt;" in html
    assert "result-not-assessed" in html


def test_report_radar_excludes_unassessed_categories(monkeypatch):
    """The radar uses assessed rows only, including the category denominator."""
    pytest.importorskip("plotly")
    from synthed.dashboard import charts
    from synthed.report import generator

    captured = []
    original = charts.validation_radar

    def capture(scores):
        """Record radar inputs while retaining the actual figure rendering."""
        captured.append(scores)
        return original(scores)

    monkeypatch.setattr(charts, "validation_radar", capture)
    monkeypatch.setattr(generator, "_fig_to_b64", lambda fig: "image")
    generator.ReportGenerator({})._render_charts({}, {}, _mixed_validation())
    assert captured == [{"Demographics": 0.5}]


def test_scorecard_distinguishes_not_assessed_from_failure():
    """Coverage and reason must be visible without a failure cross on N/A."""
    pytest.importorskip("shiny")
    from synthed.dashboard.components.calibrate_panel import _scorecard_row, scorecard_table

    rows = _mixed_validation()["results"]
    row_html = str(_scorecard_row(rows[-1]))
    assert "N/A" in row_html
    assert "✗" not in row_html
    assert "reason=&lt;empty cohort&gt;" in row_html
    html = str(scorecard_table(rows))
    assert "1/2 tests passed" in html
    assert "1 not assessed" in html
    assert "3 total" in html


@pytest.mark.parametrize("name,expected", [
    ("validation_grade", "D"), ("validation_grade_sub", "1/2 passed; 1 not assessed; 3 total"),
])
def test_dashboard_callbacks_use_shared_quality_and_coverage(name, expected):
    """Execute the real nested callback body without a reactive session."""
    pytest.importorskip("shiny")
    from synthed.dashboard import app

    tree = ast.parse(inspect.getsource(app))
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    callback.decorator_list = []
    namespace = dict(vars(app))
    namespace["sim_results"] = SimpleNamespace(get=lambda: {"validation": _mixed_validation()})
    exec(compile(ast.Module(body=[callback], type_ignores=[]), app.__file__, "exec"), namespace)
    assert namespace[name]() == expected


def test_benchmark_report_discloses_assessment_coverage():
    """Benchmark text must not score unassessed rows or trust stale totals."""
    text = BenchmarkGenerator._format_report([{"validation": _mixed_validation()}], 1)
    assert "1/2" in text
    assert "1 not assessed" in text
    assert "3 total" in text


@pytest.mark.parametrize("rows,expected", [
    ([{"passed": True}] * 17 + [{"passed": False}] * 3, "B"),
    ([{"passed": False, "status": "not_assessed"}], "N/A"),
    ([], "N/A"),
])
def test_dashboard_grade_matches_validator_thresholds_even_without_assessments(rows, expected):
    """The UI must share A>=90% and N/A semantics with the validator."""
    pytest.importorskip("shiny")
    from synthed.dashboard import app

    tree = ast.parse(inspect.getsource(app))
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "validation_grade")
    callback.decorator_list = []
    namespace = dict(vars(app))
    namespace["sim_results"] = SimpleNamespace(get=lambda: {"validation": {"results": rows}})
    exec(compile(ast.Module(body=[callback], type_ignores=[]), app.__file__, "exec"), namespace)
    assert namespace["validation_grade"]() == expected


@pytest.mark.parametrize("name,expected", [
    ("validation_grade", "B"), ("validation_grade_sub", "3/4 passed; 0 not assessed; 4 total"),
])
def test_dashboard_preserves_summary_only_historical_reports(name, expected):
    """Absence of historical rows must not relabel an existing grade as N/A."""
    pytest.importorskip("shiny")
    from synthed.dashboard import app

    report = {"validation": {"summary": {"total_tests": 4, "passed": 3, "failed": 1,
                                         "pass_rate": 0.75, "overall_quality": "B (Good)"}}}
    callback = next(node for node in ast.walk(ast.parse(inspect.getsource(app)))
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    callback.decorator_list = []
    namespace = dict(vars(app))
    namespace["sim_results"] = SimpleNamespace(get=lambda: report)
    exec(compile(ast.Module(body=[callback], type_ignores=[]), app.__file__, "exec"), namespace)
    assert namespace[name]() == expected


@pytest.mark.parametrize("seed", [42, 7, 123])
def test_pipeline_rejects_non_finite_report_before_writing(tmp_path, monkeypatch, seed):
    """A malformed validator cannot publish nonstandard JSON as a report."""
    pipeline = SynthEdPipeline(config=PipelineConfig(output_dir=str(tmp_path), seed=seed))
    bad_report = {"summary": {"overall_quality": "A", "passed": 1, "total_tests": 1},
                  "results": [{"passed": True, "synthetic": float("nan")}]}
    monkeypatch.setattr(pipeline.validator, "validate_all", lambda *args, **kwargs: bad_report)
    with pytest.raises(ValueError, match="Out of range float"):
        pipeline.run(n_students=12)
    assert not (tmp_path / "pipeline_report.json").exists()
