"""UI components for the Calibrate tab (PR B).

All functions in this module are pure: they take plain Python inputs and
return Shiny UI nodes. Reactive reads happen only in app.py's server body.
This keeps the module unit-testable without a live Shiny session.
"""

from __future__ import annotations

from shiny import ui


def calibrate_panel_ui():
    """Outer shell for the Calibrate tab.

    Content is rendered server-side into ``ui.output_ui("calibrate_area")``.
    The id ``calibrate_content_area`` is the PR #79 swap point — do not rename.
    """
    return ui.div(
        ui.output_ui("calibrate_area"),
        id="calibrate_content_area",
        class_="p-3",
    )
