"""Results drawer panel with summary cards and chart containers."""

from __future__ import annotations

from shiny import ui


def summary_card(card_id: str, label: str, color_class: str = "text-primary") -> ui.Tag:
    """A single summary metric card."""
    return ui.div(
        ui.div(label, class_="card-label",
               style="font-size:11px;color:var(--text-secondary,#8B90A0);text-transform:uppercase;letter-spacing:0.5px;"),
        ui.div(
            ui.output_text(card_id, inline=True),
            class_=f"card-value value-display {color_class}",
            style="font-size:24px;font-weight:600;",
        ),
        ui.div(
            ui.output_text(f"{card_id}_sub", inline=True),
            style="font-size:10px;color:var(--text-muted,#4A4F63);font-family:'JetBrains Mono',monospace;",
        ),
        class_="summary-card p-3",
    )


def summary_cards_row() -> ui.Tag:
    """4 summary cards in a 2x2 grid."""
    return ui.row(
        ui.column(6, summary_card("dropout_rate", "Dropout Rate", "text-primary")),
        ui.column(6, summary_card("mean_engagement", "Engagement", "text-warning")),
        ui.column(6, summary_card("mean_gpa", "Mean GPA", "text-success"), class_="mt-2"),
        ui.column(6, summary_card("validation_grade", "Validation", "text-success"), class_="mt-2"),
    )


def results_layout() -> ui.Tag:
    """Full results panel layout."""
    return ui.div(
        ui.h5("Results", class_="mb-3"),
        summary_cards_row(),
        ui.hr(class_="my-3", style="border-color:var(--border,#1E2130);"),
        # Charts
        ui.div(
            ui.h6("Dropout Timeline"),
            ui.output_ui("chart_dropout"),
            class_="mb-3",
        ),
        ui.div(
            ui.h6("Engagement Distribution"),
            ui.output_ui("chart_engagement"),
            class_="mb-3",
        ),
        ui.div(
            ui.h6("GPA Distribution"),
            ui.output_ui("chart_gpa"),
            class_="mb-3",
        ),
        ui.div(
            ui.h6("Validation Radar"),
            ui.output_ui("chart_validation"),
            class_="mb-3",
        ),
        # Export
        ui.hr(class_="my-3", style="border-color:var(--border,#1E2130);"),
        ui.row(
            ui.column(6, ui.download_button("export_config", "Export Config JSON",
                                            class_="btn btn-outline-secondary btn-sm w-100")),
            ui.column(6, ui.input_file("import_config", "Import configuration",
                                       accept=[".json"], button_label="Import Config")),
        ),
    )
