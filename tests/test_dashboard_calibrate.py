"""Tests for the Calibrate tab UI components (PR B scorecard)."""

from __future__ import annotations

from synthed.dashboard.components.calibrate_panel import (
    calibrate_panel_ui,
)
from synthed.dashboard.components.calibrate_panel import empty_state


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
