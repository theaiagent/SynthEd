"""Structural tests for the two-tab mode-split skeleton (PR A).

These tests assert on the module source of synthed.dashboard.app. They do not
run the dashboard; they just confirm the `page_navbar(...)` call wires two
panels and exposes the PR B swap-point anchor.
"""
from __future__ import annotations

import inspect

from synthed.dashboard import app as dashboard_app


def test_navbar_has_two_panels():
    """PR A regression guard: Research + Calibrate nav panels must both exist."""
    src = inspect.getsource(dashboard_app)
    assert 'ui.nav_panel("Research"' in src, "Research nav panel missing"
    assert 'ui.nav_panel("Calibrate"' in src, "Calibrate nav panel missing"


def test_calibrate_tab_has_swap_point_id():
    """PR B swap target: the Calibrate component must expose id=calibrate_content_area."""
    from synthed.dashboard.components import calibrate_panel
    src = inspect.getsource(calibrate_panel)
    assert 'id="calibrate_content_area"' in src, (
        "calibrate_panel_ui must expose id=calibrate_content_area for PR B swap"
    )


def test_calibrate_panel_swap_uses_new_component():
    """PR B regression guard: the Calibrate nav panel must call the new
    component, not the deleted placeholder function."""
    src = inspect.getsource(dashboard_app)
    assert 'calibrate_panel_ui()' in src, (
        "Calibrate nav panel should call calibrate_panel_ui() after PR B swap"
    )
    assert 'calibrate_placeholder_ui' not in src, (
        "Dead code: calibrate_placeholder_ui should be removed after PR B"
    )
