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
    """PR B swap target: the placeholder wrapper must carry id=calibrate_content_area."""
    src = inspect.getsource(dashboard_app)
    assert 'id="calibrate_content_area"' in src, (
        "Calibrate placeholder must expose id=calibrate_content_area for PR B swap"
    )


def test_calibrate_placeholder_has_no_run_button():
    """Regression guard: Calibrate tab must not share the Research run button input ID.

    If this fails, the placeholder copied reactive machinery — a sign someone
    accidentally duplicated the Research content instead of placing a static placeholder.
    """
    src = inspect.getsource(dashboard_app)
    assert "def calibrate_placeholder_ui" in src, (
        "calibrate_placeholder_ui() factory must exist"
    )
    func_src = src.split("def calibrate_placeholder_ui")[1].split("\ndef ")[0]
    assert "run_simulation" not in func_src, (
        "Calibrate placeholder must not reference run_simulation (tab is inert in PR A)"
    )
