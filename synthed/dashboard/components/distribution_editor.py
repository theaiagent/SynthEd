"""Sum-to-1 probability distribution editor component."""

from __future__ import annotations

from shiny import ui


def distribution_editor(input_id: str, label: str, values: dict[str, float]) -> ui.Tag:
    """Render a distribution editor with sliders that must sum to 1.0.

    Sum indicator is rendered via output_ui (reactive, server-side).
    """
    sliders = []
    for key, val in values.items():
        slider_id = f"{input_id}_{key}"
        sliders.append(
            ui.div(
                ui.row(
                    ui.column(5, ui.tags.label(key, class_="text-secondary",
                                               style="font-size:12px;line-height:32px;")),
                    ui.column(4, ui.input_slider(slider_id, None, min=0.0, max=1.0,
                                                 value=round(val, 2), step=0.01,
                                                 width="100%")),
                    ui.column(3, ui.input_numeric(f"{slider_id}_num", None,
                                                  value=round(val, 2), min=0.0, max=1.0,
                                                  step=0.01, width="100%")),
                ),
                class_="mb-1",
            )
        )

    return ui.div(
        ui.tags.label(label, class_="section-heading", style="font-size:12px;"),
        *sliders,
        ui.output_ui(f"{input_id}_sum"),
        class_="mb-3 p-2",
        style="background:var(--bg, #0F1117);border-radius:6px;",
    )
