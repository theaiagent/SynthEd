"""Tests for the Calibrate tab UI components (PR B scorecard)."""

from __future__ import annotations

from synthed.dashboard.components.calibrate_panel import (
    calibrate_panel_ui,
)
from synthed.dashboard.components.calibrate_panel import empty_state
from synthed.dashboard.components.calibrate_panel import _fmt_num


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
