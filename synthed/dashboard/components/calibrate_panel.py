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

    Wording rationale (from statistician round-3 review): the ~22 validation
    tests share simulator state, which induces positive dependence. Under
    positive dependence, Var(total false positives) is inflated vs the
    independent-tests case, so clusters of flips are MORE likely under the
    null than a Binomial(22, 0.05) would predict. "Persistent across runs"
    means seed-varying reruns — a deterministic re-render of the same
    report would trivially reproduce the same flip.
    """
    return ui.div(
        ui.tags.p(
            ui.tags.strong("Interpretation: "),
            "Expected ≈1.1 false positives at α=0.05 across ~22 tests. "
            "Tests share simulator state (positive dependence), so "
            "clusters of flips are ",
            ui.tags.em("more"),
            " likely under the null than independence would suggest — a "
            "cluster is not by itself evidence of a real regression. "
            "Investigate flips that persist across runs with ",
            ui.tags.strong("different seeds"),
            "; dismiss single-run flips.",
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

    Non-dict entries in the list are silently filtered — matches the
    validation_grade_sub tolerance in app.py:578, guarding against loosely
    serialized validation reports.

    An empty result list renders the "No validation data" empty state
    instead of an empty table.

    Uses bslib ``ui.accordion`` / ``ui.accordion_panel`` for collapsibility.
    A raw ``<details>`` element would bypass theme.py's ``.accordion-*``
    CSS and render inconsistently between dark and light mode — param_panel
    uses the same widget for the sidebar panels, so this is the
    project-consistent choice.
    """
    # Guard against non-dict entries. Same pattern as app.py:578.
    results = [r for r in results if isinstance(r, dict)]

    if not results:
        return empty_state(
            title="No validation data",
            body="This run did not produce validation results.",
            icon="bi-info-circle",
        )

    rows = [_scorecard_row(r) for r in results]
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)

    return ui.accordion(
        ui.accordion_panel(
            f"{passed}/{total} tests passed",
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
            ),
            _scorecard_footer(),
            value="scorecard_panel",
        ),
        open="scorecard_panel",
    )
