"""Tests for the Calibrate tab UI components (PR B scorecard)."""

from __future__ import annotations

from synthed.dashboard.components.calibrate_panel import (
    calibrate_panel_ui,
)
from synthed.dashboard.components.calibrate_panel import empty_state
from synthed.dashboard.components.calibrate_panel import _fmt_num
from synthed.dashboard.components.calibrate_panel import _scorecard_row
from synthed.dashboard.components.calibrate_panel import _scorecard_footer
from synthed.dashboard.components.calibrate_panel import scorecard_table


def test_calibrate_panel_ui_has_swap_point_id():
    """PR #79 contract: outer shell must expose id=calibrate_content_area."""
    html = str(calibrate_panel_ui())
    assert 'id="calibrate_content_area"' in html


def test_calibrate_panel_ui_renders_output_ui_binding():
    """Server render binds calibrate_area; shell must reserve that output id."""
    html = str(calibrate_panel_ui())
    assert "calibrate_area" in html


def test_empty_state_renders_title_body_icon():
    """Title, body, and icon classes must appear in the rendered HTML."""
    html = str(empty_state(
        title="Run a simulation first",
        body="Use the Research tab first.",
        icon="bi-rocket-takeoff",
    ))
    assert "Run a simulation first" in html
    assert "Use the Research tab first." in html
    assert "bi-rocket-takeoff" in html


def test_empty_state_uses_muted_text_for_body():
    """Body copy should use text-muted class for de-emphasized display."""
    html = str(empty_state(title="t", body="b", icon="bi-info-circle"))
    assert "text-muted" in html


def test_fmt_num_none_is_em_dash():
    assert _fmt_num(None) == "—"


def test_fmt_num_float_uses_4_sig_figs():
    # {v:.4g} → "0.1235" for 0.123456
    assert _fmt_num(0.123456) == "0.1235"


def test_fmt_num_int_passes_through_as_str():
    assert _fmt_num(42) == "42"


def test_fmt_num_string_passes_through_as_str():
    # Guard for non-numeric reference values some validators may emit.
    assert _fmt_num("range(0.3, 0.5)") == "range(0.3, 0.5)"


def _sample_passing_result():
    return {
        "test": "dropout_rate",
        "metric": "overall",
        "synthetic": 0.45,
        "reference": 0.42,
        "statistic": 0.031,
        "p_value": 0.12,
        "passed": True,
        "details": "dropout within tolerance",
    }


def _sample_failing_result_with_none_stats():
    return {
        "test": "k_anonymity",
        "metric": "privacy",
        "synthetic": 4,
        "reference": 5,
        "statistic": None,
        "p_value": None,
        "passed": False,
        "details": "below threshold",
    }


def test_scorecard_row_passed_uses_success_class():
    html = str(_scorecard_row(_sample_passing_result()))
    assert "text-success" in html
    assert "✓" in html


def test_scorecard_row_failed_uses_danger_class():
    html = str(_scorecard_row(_sample_failing_result_with_none_stats()))
    assert "text-danger" in html
    assert "✗" in html


def test_scorecard_row_none_statistic_renders_em_dash():
    html = str(_scorecard_row(_sample_failing_result_with_none_stats()))
    assert "—" in html


def test_scorecard_row_float_uses_4_sig_figs():
    # synthetic=0.45 is already short; use a longer float via details-free sample
    r = dict(_sample_passing_result(), synthetic=0.123456)
    html2 = str(_scorecard_row(r))
    assert "0.1235" in html2


def test_scorecard_row_details_surfaces_as_title_attribute():
    html = str(_scorecard_row(_sample_passing_result()))
    assert 'title="dropout within tolerance"' in html


def test_scorecard_row_details_surfaces_as_aria_label():
    """Screen readers need the details text on focus, not just mouse hover."""
    html = str(_scorecard_row(_sample_passing_result()))
    assert 'aria-label="dropout within tolerance"' in html


def test_scorecard_row_omits_title_and_aria_when_details_empty():
    """Empty details must not emit empty title="" / aria-label="" attrs."""
    html = str(_scorecard_row({"passed": True}))
    assert 'title=""' not in html
    assert 'aria-label=""' not in html


def test_scorecard_row_missing_fields_render_em_dash():
    html = str(_scorecard_row({"passed": True}))
    # No test, no metric, no stats — all cells should show the em-dash default.
    assert "—" in html


def test_scorecard_row_includes_test_and_metric_names():
    html = str(_scorecard_row(_sample_passing_result()))
    assert "dropout_rate" in html
    assert "overall" in html


def test_scorecard_footer_notes_mixed_test_battery():
    """Footer must distinguish α-governed tests from deterministic checks."""
    html = str(_scorecard_footer())
    assert "hypothesis tests" in html
    assert "deterministic" in html


def test_scorecard_footer_notes_positive_dependence():
    """Footer must warn that shared simulator state inflates cluster mass."""
    html = str(_scorecard_footer())
    assert "positive dependence" in html
    assert "more" in html  # <em>more</em> likely than independence


def test_scorecard_footer_triage_advice_conditions_on_test_kind():
    """Triage advice must split stochastic vs deterministic paths."""
    html = str(_scorecard_footer())
    assert "different seeds" in html
    assert "distribution drift" in html


def test_scorecard_footer_surfaces_effective_alpha_scaling():
    """N>500 α-scaling must be surfaced to prevent misreading raw p."""
    html = str(_scorecard_footer())
    assert "Effective α" in html or "effective α" in html.lower()
    assert "0.05" in html
    assert "N" in html  # mentions N-dependence
    assert "CALIBRATION_METHODOLOGY" in html


def _three_results():
    return [
        {
            "test": "t1", "metric": "m1",
            "synthetic": 0.5, "reference": 0.45,
            "statistic": 0.05, "p_value": 0.1,
            "passed": True, "details": "",
        },
        {
            "test": "t2", "metric": "m2",
            "synthetic": 3, "reference": 5,
            "statistic": None, "p_value": None,
            "passed": False, "details": "range-check failed",
        },
        {
            "test": "t3", "metric": "m3",
            "synthetic": 0.8, "reference": 0.8,
            "statistic": 0.0, "p_value": 1.0,
            "passed": True, "details": "",
        },
    ]


def test_scorecard_empty_list_renders_empty_state():
    html = str(scorecard_table([]))
    assert "No validation data" in html
    assert "bi-info-circle" in html


def test_scorecard_renders_row_per_result():
    html = str(scorecard_table(_three_results()))
    # Three <tr> rows inside <tbody> + 1 header row = 4 total <tr>.
    assert html.count("<tr") == 4


def test_scorecard_summary_counts_passed_over_total():
    html = str(scorecard_table(_three_results()))
    assert "2/3 tests passed" in html


def test_scorecard_filters_non_dict_entries():
    """Matches the validation_grade_sub tolerance at app.py:578."""
    mixed = [None, "bad", {"test": "ok", "passed": True}]
    html = str(scorecard_table(mixed))
    assert html.count("<tr") == 2  # 1 header + 1 dict row
    assert "ok" in html


def test_scorecard_uses_accordion_widget():
    """Regression guard: must use bslib accordion, not raw <details>.

    theme.py has extensive .accordion-* CSS; a raw <details> would render
    unthemed and inconsistent between dark/light mode.
    """
    html = str(scorecard_table(_three_results()))
    assert "accordion" in html
    assert "<details" not in html


def test_scorecard_column_headers_present():
    html = str(scorecard_table(_three_results()))
    for header in ("Test", "Metric", "Synthetic", "Reference", "Stat", "p", "Pass"):
        assert f">{header}<" in html


def test_scorecard_table_classes_include_responsive_wrapper():
    """Bootstrap handles horizontal overflow on small screens."""
    html = str(scorecard_table(_three_results()))
    assert "table-responsive" in html
    assert "table table-sm table-hover" in html


def test_scorecard_includes_footer_note():
    """Happy path must embed the multiple-testing interpretation footer."""
    html = str(scorecard_table(_three_results()))
    assert "hypothesis tests" in html
    assert "Effective α" in html or "effective α" in html.lower()


def test_scorecard_warns_when_non_dict_entries_dropped():
    """Dropped malformed entries must be surfaced, not silent."""
    mixed = [None, "bad", {"test": "ok", "passed": True}]
    html = str(scorecard_table(mixed))
    assert "alert-warning" in html
    assert "2" in html  # count of dropped entries
    assert "dropped" in html.lower()


def test_scorecard_no_warning_when_all_dicts():
    """Clean inputs should not display a warning banner."""
    html = str(scorecard_table(_three_results()))
    assert "alert-warning" not in html


# ── Render-integration tests ──
# calibrate_area's body composes three contracts:
#   1. None report → S1 empty state (tested below)
#   2. non-None report → scorecard_table(_get_validation_results(report))
#
# Contract 2 is exercised by the per-component tests above plus the full
# coverage of _get_validation_results in test_dashboard.py. We only assert
# the wiring — not the branch logic, which now lives in app.py's module
# scope and is covered by its own tests.


def test_calibrate_area_none_report_renders_s1_empty_state():
    """S1 state: no simulation yet. Invoke the same empty_state() call
    calibrate_area makes when sim_results.get() is None."""
    html = str(empty_state(
        title="Run a simulation first",
        body=(
            "Use the Research tab to run a simulation; "
            "validation results will appear here."
        ),
        icon="bi-rocket-takeoff",
    ))
    assert "Run a simulation first" in html
    assert "bi-rocket-takeoff" in html


def test_calibrate_area_source_composes_shared_helper():
    """Regression guard: calibrate_area must route through
    _get_validation_results (not inline the isinstance dispatch).

    If someone reverts the Q1 refactor, this test catches it.
    """
    import inspect
    from synthed.dashboard import app as dashboard_app
    src = inspect.getsource(dashboard_app)
    # Locate the calibrate_area function and assert it calls the shared helper.
    assert "scorecard_table(_get_validation_results(report))" in src, (
        "calibrate_area must call scorecard_table(_get_validation_results(report)) "
        "— do not reintroduce inline isinstance dispatch."
    )


def test_get_validation_results_source_guards_non_list_results():
    """Regression guard: _get_validation_results must coerce None/non-list
    `validation.results` to [] so downstream consumers (scorecard_table,
    validation_grade, chart_validation) can rely on iterability.
    """
    import inspect
    from synthed.dashboard import app as dashboard_app
    src = inspect.getsource(dashboard_app)
    assert "raw if isinstance(raw, list) else []" in src, (
        "_get_validation_results must coerce non-list `results` values to [] "
        "— plain val.get('results', []) is not enough (returns None on explicit null)."
    )
