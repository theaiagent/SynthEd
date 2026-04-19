"""UI components for the Calibrate tab (PR B).

All functions in this module are pure: they take plain Python inputs and
return Shiny UI nodes. Reactive reads happen only in app.py's server body.
This keeps the module unit-testable without a live Shiny session.
"""

from __future__ import annotations

from shiny import ui


def empty_state(*, title: str, body: str, icon: str):
    """Full-panel message used for S1 (no simulation yet) and S4 (no validation data).

    Args:
        title: Heading text (rendered as h3).
        body: Paragraph text (rendered with text-muted).
        icon: Bootstrap-icons class name (e.g. "bi-rocket-takeoff") without
              the leading "bi" prefix space — the renderer prefixes it.
    """
    return ui.div(
        ui.tags.i(
            class_=f"bi {icon}",
            style="font-size:56px;color:var(--text-muted);",
        ),
        ui.tags.h3(title, class_="mt-3"),
        ui.tags.p(body, class_="text-muted mt-2"),
        class_="text-center py-5",
    )


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


def _fmt_num(v):
    """Format a numeric cell value for display.

    None renders as em-dash (matches how `—` is used elsewhere in the
    dashboard for absent values). Floats use 4 significant figures.
    Anything else (int, string, bool) falls through to ``str(v)``.
    """
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)
