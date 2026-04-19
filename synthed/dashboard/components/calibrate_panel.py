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
        icon: Bootstrap Icons class name including the ``bi-`` prefix,
              e.g. ``"bi-rocket-takeoff"``. The renderer also adds the
              required base ``bi`` class, producing ``class="bi bi-rocket-takeoff"``.
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


def _scorecard_row(r: dict):
    """Render a single validation result as a table row.

    Missing fields fall back to "—". ``r["details"]`` is surfaced as the
    row's ``title=`` attribute — Bootstrap tooltips use this for accessible
    hover text without requiring extra JS wiring.
    """
    passed = r.get("passed", False)
    mark = (
        ui.tags.span("✓", class_="text-success fw-bold")
        if passed
        else ui.tags.span("✗", class_="text-danger fw-bold")
    )

    return ui.tags.tr(
        ui.tags.td(r.get("test", "—")),
        ui.tags.td(r.get("metric", "—")),
        ui.tags.td(_fmt_num(r.get("synthetic"))),
        ui.tags.td(_fmt_num(r.get("reference"))),
        ui.tags.td(_fmt_num(r.get("statistic"))),
        ui.tags.td(_fmt_num(r.get("p_value"))),
        ui.tags.td(mark),
        title=str(r.get("details", "")),
    )


def _scorecard_footer():
    """Interpretive footnote printed below the scorecard table.

    Reflects the statistician round-4 review: the battery is heterogeneous
    (α-governed hypothesis tests mixed with deterministic range/threshold/
    sign checks), and validator._effective_alpha scales α down for N>500,
    so the raw p column cannot be read against a fixed α=0.05.
    """
    return ui.div(
        ui.tags.p(
            ui.tags.strong("Interpretation: "),
            "The battery mixes α-governed hypothesis tests (KS, χ², z, t, "
            "correlation) with deterministic range, threshold, and sign "
            "checks. For the hypothesis-test subset, a handful of false-"
            "positive flips per run is expected even under a correct "
            "simulator; positive dependence between tests (shared "
            "simulator state) inflates variance so clusters of flips are ",
            ui.tags.em("more"),
            " likely than independence would predict — a cluster is not "
            "by itself evidence of real regression.",
            class_="small text-muted mb-1",
        ),
        ui.tags.p(
            ui.tags.strong("Triage: "),
            "For hypothesis tests, investigate flips that persist across ",
            ui.tags.strong("different seeds"),
            "; for deterministic checks, persistence is tautological — "
            "investigate distribution drift instead.",
            class_="small text-muted mb-1",
        ),
        ui.tags.p(
            ui.tags.strong("Effective α: "),
            "for N > 500, α is scaled down to ",
            ui.tags.code("max(0.05·√(200/N), 0.001)"),
            " (see ",
            ui.tags.code("CALIBRATION_METHODOLOGY.md"),
            " §5); the ",
            ui.tags.code("Pass"),
            " column compares against the scaled threshold, not the raw "
            "0.05 you see in the ",
            ui.tags.code("p"),
            " column.",
            class_="small text-muted mb-1",
        ),
        class_="mt-2",
    )


def scorecard_table(results: list[dict]):
    """Collapsible Bootstrap table of validation tests.

    Each dict in ``results`` is rendered as one row with columns:
    Test | Metric | Synthetic | Reference | Stat | p | Pass. Missing or
    None values display as "—" (handled by :func:`_scorecard_row`).
    ``details`` surfaces as the row's ``title=`` attribute for accessible
    hover text.

    Non-dict entries are filtered out and surfaced via a warning row at
    the top of the panel so the user knows a malformed entry was dropped.

    An empty result list renders the "No validation data" empty state
    instead of an empty table.

    Uses bslib ``ui.accordion`` / ``ui.accordion_panel`` for collapsibility.
    A raw ``<details>`` element would bypass theme.py's ``.accordion-*``
    CSS and render inconsistently between dark and light mode — param_panel
    uses the same widget for the sidebar panels, so this is the
    project-consistent choice.
    """
    original_len = len(results)
    results = [r for r in results if isinstance(r, dict)]
    dropped = original_len - len(results)

    if not results:
        return empty_state(
            title="No validation data",
            body="This run did not produce validation results.",
            icon="bi-info-circle",
        )

    rows = [_scorecard_row(r) for r in results]
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)

    panel_children = []
    if dropped > 0:
        panel_children.append(
            ui.div(
                ui.tags.i(class_="bi bi-exclamation-triangle me-2"),
                ui.tags.strong("Warning: "),
                f"{dropped} result{'s' if dropped != 1 else ''} "
                "dropped from this report (malformed entries). "
                "Displayed counts exclude them.",
                class_="alert alert-warning py-2 mb-2",
                role="alert",
            )
        )
    panel_children.append(
        ui.div(
            ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("Test"),
                        ui.tags.th("Metric"),
                        ui.tags.th("Synthetic"),
                        ui.tags.th("Reference"),
                        ui.tags.th("Stat"),
                        ui.tags.th("p"),
                        ui.tags.th("Pass"),
                    ),
                ),
                ui.tags.tbody(*rows),
                class_="table table-sm table-hover",
            ),
            class_="table-responsive",
        )
    )
    panel_children.append(_scorecard_footer())

    return ui.accordion(
        ui.accordion_panel(
            f"{passed}/{total} tests passed",
            *panel_children,
            value="scorecard_panel",
        ),
        open="scorecard_panel",
    )
