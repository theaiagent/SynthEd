"""Tests for the Calibrate tab UI components (PR B scorecard)."""

from __future__ import annotations

from synthed.dashboard.components.calibrate_panel import (
    calibrate_panel_ui,
)
from synthed.dashboard.components.calibrate_panel import empty_state
from synthed.dashboard.components.calibrate_panel import _fmt_num
from synthed.dashboard.components.calibrate_panel import _scorecard_row
from synthed.dashboard.components.calibrate_panel import _scorecard_footer


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


def test_scorecard_row_missing_fields_render_em_dash():
    html = str(_scorecard_row({"passed": True}))
    # No test, no metric, no stats — all cells should show the em-dash default.
    assert "—" in html


def test_scorecard_row_includes_test_and_metric_names():
    html = str(_scorecard_row(_sample_passing_result()))
    assert "dropout_rate" in html
    assert "overall" in html


def test_scorecard_footer_mentions_expected_false_positives():
    html = str(_scorecard_footer())
    assert "false positives" in html
    assert "α=0.05" in html
    assert "~22 tests" in html


def test_scorecard_footer_notes_positive_dependence():
    """The revised stat-honest wording: variance under dependence is inflated,
    so clusters are MORE likely under the null than independence suggests."""
    html = str(_scorecard_footer())
    assert "positive dependence" in html
    assert "more" in html  # <em>more</em> likely under the null


def test_scorecard_footer_notes_different_seeds():
    """Persistent flips must mean seed-varying reruns, not re-renders."""
    html = str(_scorecard_footer())
    assert "different seeds" in html
