"""Print-friendly chart builders for SynthEd reports.

All charts render with white backgrounds and dark text,
optimized for PDF/print output rather than on-screen display.
"""

from __future__ import annotations

import logging

import numpy as np
import plotly.graph_objects as go

from .translations import TRANSLATIONS

logger = logging.getLogger(__name__)

# ── Print-friendly color constants ──
_BG_WHITE = "#FFFFFF"
_TEXT_DARK = "#1F2937"
_TEXT_SECONDARY = "#6B7280"
_GRID_COLOR = "rgba(209, 213, 219, 0.5)"
_ACCENT = "#6366F1"
_SUCCESS = "#10B981"
_WARNING = "#F59E0B"
_ERROR = "#F43F5E"
_INFO = "#3B82F6"

_PRINT_LAYOUT: dict = dict(
    paper_bgcolor=_BG_WHITE,
    plot_bgcolor=_BG_WHITE,
    font=dict(family="Inter, system-ui, sans-serif", color=_TEXT_DARK, size=12),
    margin=dict(l=50, r=30, t=40, b=50),
    xaxis=dict(gridcolor=_GRID_COLOR, zerolinecolor=_GRID_COLOR),
    yaxis=dict(gridcolor=_GRID_COLOR, zerolinecolor=_GRID_COLOR),
    hoverlabel=dict(bgcolor=_BG_WHITE, font_color=_TEXT_DARK, bordercolor=_GRID_COLOR),
    colorway=[_ACCENT, _SUCCESS, _WARNING, _ERROR, _INFO],
    height=400,
)


def _print_layout(**overrides) -> dict:
    layout = {**_PRINT_LAYOUT}
    layout.update(overrides)
    return layout


def figure_to_png(fig: go.Figure, width: int = 700, height: int = 400) -> bytes:
    """Convert a Plotly figure to PNG bytes.

    Uses Playwright Chromium to render charts as PNG images.
    This avoids kaleido compatibility issues across platforms.
    """
    fig.update_layout(
        paper_bgcolor=_BG_WHITE,
        plot_bgcolor=_BG_WHITE,
        **{k: v for k, v in _PRINT_LAYOUT.items()
           if k not in ("paper_bgcolor", "plot_bgcolor")},
    )
    return _figure_to_png_playwright(fig, width, height)


def _figure_to_png_playwright(
    fig: go.Figure,
    width: int = 700,
    height: int = 400,
) -> bytes:
    """Render a Plotly figure to PNG via Playwright (fallback)."""
    from playwright.sync_api import sync_playwright

    html = fig.to_html(full_html=True, include_plotlyjs=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.set_content(html, wait_until="networkidle")
            page.wait_for_selector(".js-plotly-plot", timeout=10000)
            element = page.query_selector(".js-plotly-plot")
            png_bytes = element.screenshot(type="png") if element else page.screenshot(type="png")
        finally:
            browser.close()
    return png_bytes


def age_distribution_chart(
    population_summary: dict,
    lang: str = "en",
) -> go.Figure:
    """Histogram approximating age distribution from summary statistics."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    mean_age = population_summary.get("age_mean", 30)
    std_age = population_summary.get("age_std", 8)
    n = population_summary.get("total_students", 200)

    rng = np.random.default_rng(0)
    ages = rng.normal(mean_age, max(std_age, 1.0), n)
    ages = np.clip(ages, 18, 65)

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=ages,
        nbinsx=20,
        marker_color=_ACCENT,
        opacity=0.85,
        marker_line_color=_BG_WHITE,
        marker_line_width=1,
        name=t.get("age", "Age"),
    ))
    fig.add_vline(
        x=mean_age, line_dash="dash", line_color=_WARNING,
        annotation_text=f"{t.get('mean', 'Mean')}: {mean_age:.1f}",
        annotation_font_color=_WARNING,
    )
    fig.update_layout(**_print_layout(
        xaxis_title=t.get("age", "Age"),
        yaxis_title=t.get("count", "Count"),
        showlegend=False,
    ))
    return fig


def gender_distribution_chart(
    population_summary: dict,
    lang: str = "en",
) -> go.Figure:
    """Bar chart of gender distribution."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    gender_dist = population_summary.get("gender_distribution", {"male": 0.55, "female": 0.45})
    male_pct = gender_dist.get("male", 0.55)
    female_pct = gender_dist.get("female", 0.45)
    n = population_summary.get("total_students", 200)

    labels = [t["male"], t["female"]]
    counts = [int(round(male_pct * n)), int(round(female_pct * n))]
    colors = [_INFO, _ERROR]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=counts,
        marker_color=colors,
        opacity=0.85,
        text=[f"{c} ({p:.0%})" for c, p in zip(counts, [male_pct, female_pct])],
        textposition="auto",
    ))
    fig.update_layout(**_print_layout(
        xaxis_title="",
        yaxis_title=t.get("count", "Count"),
        showlegend=False,
    ))
    return fig


def employment_chart(
    population_summary: dict,
    lang: str = "en",
) -> go.Figure:
    """Bar chart of employment status."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    emp_rate = population_summary.get("employment_intensity_mean", 0.69)
    n = population_summary.get("total_students", 200)

    labels = [t["employed"], t["not_employed"]]
    counts = [int(round(emp_rate * n)), int(round((1 - emp_rate) * n))]
    colors = [_SUCCESS, _TEXT_SECONDARY]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=counts,
        marker_color=colors,
        opacity=0.85,
        text=[f"{c} ({p:.0%})" for c, p in zip(counts, [emp_rate, 1 - emp_rate])],
        textposition="auto",
    ))
    fig.update_layout(**_print_layout(
        xaxis_title="",
        yaxis_title=t.get("count", "Count"),
        showlegend=False,
    ))
    return fig
