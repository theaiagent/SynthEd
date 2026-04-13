"""Sum-to-1 probability distribution editor component."""

from __future__ import annotations

from shiny import ui


def distribution_editor(input_id: str, label: str, values: dict[str, float]) -> ui.Tag:
    """Render a distribution editor with sliders that must sum to 1.0.

    Each key gets a slider [0, 1]. Sum indicator shown as static text
    (actual sum validation is handled server-side via config_bridge.normalize_distribution).
    """
    sliders = []
    for key, val in values.items():
        slider_id = f"{input_id}_{key}"
        sliders.append(
            ui.div(
                ui.row(
                    ui.column(4, ui.tags.label(key, class_="text-secondary",
                                               style="font-size:12px;")),
                    ui.column(8, ui.input_slider(slider_id, None, min=0.0, max=1.0,
                                                 value=round(val, 2), step=0.01,
                                                 width="100%")),
                ),
                class_="mb-1",
            )
        )

    # Static sum indicator — reactive update deferred to Phase 2
    total = round(sum(values.values()), 2)
    sum_indicator = ui.div(
        f"\u2211 = {total:.2f} \u2713" if abs(total - 1.0) < 0.01 else f"\u2211 = {total:.2f} \u2717",
        class_="text-end",
        style=f"font-family:'JetBrains Mono',monospace;font-size:11px;"
              f"color:{'var(--success,#2DD4A0)' if abs(total - 1.0) < 0.01 else 'var(--warning,#F5A623)'};",
    )

    return ui.div(
        ui.tags.label(label, class_="text-secondary fw-bold", style="font-size:12px;"),
        *sliders,
        sum_indicator,
        class_="mb-3 p-2",
        style="background:var(--bg, #0F1117);border-radius:6px;",
    )
