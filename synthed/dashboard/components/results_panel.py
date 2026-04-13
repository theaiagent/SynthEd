"""Results drawer panel with summary cards and chart containers."""

from __future__ import annotations

from shiny import ui


def summary_card(
    card_id: str,
    label: str,
    color_class: str = "text-primary",
    accent_class: str = "",
) -> ui.Tag:
    """A single summary metric card with semantic accent border."""
    return ui.div(
        ui.div(label, class_="card-label"),
        ui.div(
            ui.output_text(card_id, inline=True),
            class_=f"card-value {color_class}",
        ),
        ui.div(
            ui.output_text(f"{card_id}_sub", inline=True),
            style="font-size:10px;color:var(--text-muted);font-family:'JetBrains Mono',monospace;",
        ),
        class_=f"summary-card {accent_class}".strip(),
    )


def summary_cards_row() -> ui.Tag:
    """4 summary cards in a 2x2 grid."""
    return ui.row(
        ui.column(6, summary_card("dropout_rate", "Dropout Rate", "text-danger", "summary-card--dropout")),
        ui.column(6, summary_card("mean_engagement", "Engagement", "text-warning", "summary-card--warning")),
        ui.column(6, summary_card("mean_gpa", "Mean GPA", "text-info", "summary-card--info"), class_="mt-2"),
        ui.column(6, summary_card("validation_grade", "Validation", "text-success", "summary-card--success"), class_="mt-2"),
    )


def _chart_settings_offcanvas() -> ui.Tag:
    """Offcanvas panel with chart customization controls."""
    return ui.TagList(
        ui.tags.button(
            ui.tags.i(class_="bi bi-gear me-1"),
            "Chart Settings",
            type="button",
            class_="btn btn-outline-secondary btn-sm",
            **{"data-bs-toggle": "offcanvas", "data-bs-target": "#chart_settings"},
        ),
        ui.tags.div(
            ui.tags.div(
                ui.tags.div(
                    ui.tags.h5("Chart Settings", class_="offcanvas-title"),
                    ui.tags.button(
                        type="button", class_="btn-close btn-close-white",
                        **{"data-bs-dismiss": "offcanvas"},
                    ),
                    class_="offcanvas-header",
                ),
                ui.tags.div(
                    # Histogram settings
                    ui.h6("Histograms"),
                    ui.input_slider("chart_bins", "Bin Count", min=5, max=50, value=30, step=1),
                    ui.input_slider("chart_bar_opacity", "Bar Opacity", min=0.3, max=1.0, value=0.8, step=0.05),
                    ui.input_checkbox("chart_bar_edge", "Bar Edge", value=True),
                    ui.input_slider("chart_bar_edge_width", "Edge Width", min=0.5, max=3.0, value=1.0, step=0.5),
                    ui.hr(style="border-color:var(--border);"),
                    # Engagement chart
                    ui.h6("Engagement"),
                    ui.input_checkbox("chart_show_mean", "Show Mean Line", value=True),
                    ui.input_checkbox("chart_show_median", "Show Median Line", value=True),
                    ui.input_text("chart_eng_x_label", "X Axis Label", value="Final Engagement"),
                    ui.input_text("chart_eng_y_label", "Y Axis Label", value="Count"),
                    ui.hr(style="border-color:var(--border);"),
                    # GPA chart
                    ui.h6("GPA"),
                    ui.input_checkbox("chart_show_pass_line", "Show Pass Threshold", value=True),
                    ui.input_checkbox("chart_show_dist_line", "Show Distinction Threshold", value=True),
                    ui.input_text("chart_gpa_x_label", "X Axis Label", value="Cumulative GPA"),
                    ui.input_text("chart_gpa_y_label", "Y Axis Label", value="Count"),
                    ui.hr(style="border-color:var(--border);"),
                    # Dropout timeline
                    ui.h6("Dropout Timeline"),
                    ui.input_slider("chart_line_width", "Line Width", min=1, max=5, value=3, step=1),
                    ui.input_slider("chart_marker_size", "Marker Size", min=3, max=12, value=7, step=1),
                    ui.input_text("chart_dropout_x_label", "X Axis Label", value="Week"),
                    ui.input_text("chart_dropout_y_label", "Y Axis Label", value="Cumulative Dropout %"),
                    ui.hr(style="border-color:var(--border);"),
                    # General
                    ui.h6("General"),
                    ui.input_checkbox("chart_show_legend", "Show Legend", value=False),
                    class_="offcanvas-body",
                ),
                class_="offcanvas offcanvas-end",
                tabindex="-1",
                id="chart_settings",
                style="width:350px;background:var(--bg,#0F1117);color:var(--text-primary,#F1F5F9);",
                **{"data-bs-backdrop": "true"},
            ),
        ),
    )


def results_layout() -> ui.Tag:
    """Full results panel layout."""
    return ui.div(
        ui.div(
            ui.h5("Results", style="display:inline;"),
            ui.span(_chart_settings_offcanvas(), class_="float-end"),
            class_="mb-3",
        ),
        summary_cards_row(),
        ui.hr(class_="my-3", style="border-color:var(--border,#1E2130);"),
        # Charts
        ui.div(
            ui.h6("Dropout Timeline"),
            ui.output_ui("chart_dropout"),
            class_="mb-3",
        ),
        ui.row(
            ui.column(
                6,
                ui.div(
                    ui.h6("Engagement Distribution"),
                    ui.output_ui("chart_engagement"),
                    class_="mb-3",
                ),
            ),
            ui.column(
                6,
                ui.div(
                    ui.h6("GPA Distribution"),
                    ui.output_ui("chart_gpa"),
                    class_="mb-3",
                ),
            ),
        ),
        ui.div(
            ui.h6("Validation Radar"),
            ui.output_ui("chart_validation"),
            class_="mb-3",
        ),
    )
