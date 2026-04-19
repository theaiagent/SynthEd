"""Tests for the Calibrate tab UI components (PR B scorecard)."""

from __future__ import annotations

from synthed.dashboard.components.calibrate_panel import (
    calibrate_panel_ui,
)


def test_calibrate_panel_ui_has_swap_point_id():
    """PR #79 contract: outer shell must expose id=calibrate_content_area."""
    html = str(calibrate_panel_ui())
    assert 'id="calibrate_content_area"' in html


def test_calibrate_panel_ui_renders_output_ui_binding():
    """Server render binds calibrate_area; shell must reserve that output id."""
    html = str(calibrate_panel_ui())
    assert "calibrate_area" in html
