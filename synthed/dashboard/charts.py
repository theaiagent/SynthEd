"""Plotly chart builders for SynthEd Dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import plotly.graph_objects as go

from .theme import (
    SURFACE, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_LIGHT, SUCCESS, WARNING, ERROR, INFO,
)


@dataclass(frozen=True)
class ChartSettings:
    """User-configurable chart appearance settings."""

    bins: int = 30
    bar_opacity: float = 0.8
    bar_edge: bool = True
    bar_edge_width: float = 1.0
    show_mean: bool = True
    show_median: bool = True
    show_pass_line: bool = True
    show_dist_line: bool = True
    show_legend: bool = False
    line_width: int = 3
    marker_size: int = 7
    eng_x_label: str = "Final Engagement"
    eng_y_label: str = "Count"
    gpa_x_label: str = "Cumulative GPA"
    gpa_y_label: str = "Count"
    dropout_x_label: str = "Week"
    dropout_y_label: str = "Cumulative Dropout %"

_GRID_COLOR = "rgba(30, 33, 48, 0.5)"

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color=TEXT_SECONDARY, size=12),
    margin=dict(l=40, r=20, t=30, b=40),
    xaxis=dict(gridcolor=_GRID_COLOR, zerolinecolor=_GRID_COLOR),
    yaxis=dict(gridcolor=_GRID_COLOR, zerolinecolor=_GRID_COLOR),
    hoverlabel=dict(bgcolor=SURFACE, font_color=TEXT_PRIMARY, bordercolor=BORDER),
    colorway=[ACCENT, ACCENT_LIGHT, SUCCESS, WARNING, ERROR, INFO],
    height=400,
)


def _base_layout(**overrides: Any) -> dict:
    layout = {**_LAYOUT_DEFAULTS}
    layout.update(overrides)
    return layout


def dropout_timeline(
    weekly_dropouts: list[int],
    n_students: int,
    settings: ChartSettings | None = None,
) -> go.Figure:
    """Cumulative dropout percentage by week — line chart."""
    s = settings or ChartSettings()
    if n_students <= 0 or not weekly_dropouts:
        fig = go.Figure()
        fig.update_layout(**_base_layout(
            xaxis_title=s.dropout_x_label,
            yaxis_title=s.dropout_y_label,
            showlegend=s.show_legend,
        ))
        fig.add_annotation(
            text="No dropout data", showarrow=False,
            font=dict(color=TEXT_MUTED, size=14),
        )
        return fig

    cumulative = _cumulative_percentages(weekly_dropouts, n_students)
    weeks = list(range(1, len(cumulative) + 1))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks, y=cumulative,
        mode="lines+markers",
        line=dict(color=ACCENT, width=s.line_width),
        marker=dict(size=s.marker_size, color=ACCENT),
        name="Cumulative Dropout %",
        hovertemplate="Week %{x}: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout(
        xaxis_title=s.dropout_x_label,
        yaxis_title=s.dropout_y_label,
        yaxis_range=[0, max(cumulative[-1] * 1.15, 10) if cumulative else 100],
        showlegend=s.show_legend,
    ))
    return fig


def _cumulative_percentages(weekly: list[int], n_students: int) -> list[float]:
    """Convert weekly dropout counts to cumulative percentage list."""
    result = []
    total = 0
    for count in weekly:
        total += count
        result.append(total / n_students * 100)
    return result


def engagement_distribution(
    engagements: list[float],
    settings: ChartSettings | None = None,
) -> go.Figure:
    """Final engagement histogram with mean/median markers."""
    import numpy as np

    s = settings or ChartSettings()
    mean_val = float(np.mean(engagements))
    median_val = float(np.median(engagements))

    edge_kwargs: dict[str, Any] = {}
    if s.bar_edge:
        edge_kwargs = dict(marker_line_color=SURFACE, marker_line_width=s.bar_edge_width)

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=engagements,
        nbinsx=s.bins,
        marker_color=ACCENT,
        opacity=s.bar_opacity,
        name="Engagement",
        hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>",
        **edge_kwargs,
    ))
    if s.show_mean:
        fig.add_vline(x=mean_val, line_dash="dash", line_color=WARNING,
                      annotation_text=f"Mean: {mean_val:.3f}",
                      annotation_font_color=WARNING,
                      annotation_yshift=10)
    if s.show_median:
        fig.add_vline(x=median_val, line_dash="dot", line_color=SUCCESS,
                      annotation_text=f"Median: {median_val:.3f}",
                      annotation_font_color=SUCCESS,
                      annotation_yshift=-10)
    fig.update_layout(**_base_layout(
        xaxis_title=s.eng_x_label,
        yaxis_title=s.eng_y_label,
        showlegend=s.show_legend,
    ))
    return fig


def gpa_distribution(
    gpas: list[float],
    pass_threshold: float = 0.64,
    distinction_threshold: float = 0.73,
    settings: ChartSettings | None = None,
) -> go.Figure:
    """GPA distribution histogram with pass/distinction threshold lines."""
    s = settings or ChartSettings()

    edge_kwargs: dict[str, Any] = {}
    if s.bar_edge:
        edge_kwargs = dict(marker_line_color=SURFACE, marker_line_width=s.bar_edge_width)

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=gpas,
        nbinsx=s.bins,
        marker_color=SUCCESS,
        opacity=s.bar_opacity,
        name="GPA",
        hovertemplate="GPA: %{x:.2f}<br>Count: %{y}<extra></extra>",
        **edge_kwargs,
    ))
    if s.show_pass_line:
        fig.add_vline(x=pass_threshold, line_dash="dash", line_color=WARNING,
                      annotation_text=f"Pass: {pass_threshold:.2f}",
                      annotation_font_color=WARNING,
                      annotation_yshift=10)
    if s.show_dist_line:
        fig.add_vline(x=distinction_threshold, line_dash="dash", line_color=ACCENT,
                      annotation_text=f"Distinction: {distinction_threshold:.2f}",
                      annotation_font_color=ACCENT,
                      annotation_yshift=-10)
    fig.update_layout(**_base_layout(
        xaxis_title=s.gpa_x_label,
        yaxis_title=s.gpa_y_label,
        showlegend=s.show_legend,
    ))
    return fig


def validation_radar(level_scores: dict[str, float]) -> go.Figure:
    """5-level validation scores as radar chart."""
    categories = list(level_scores.keys())
    values = list(level_scores.values())
    # Close the polygon
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor="rgba(99, 102, 241, 0.15)",
        line=dict(color=ACCENT, width=2),
        marker=dict(size=6, color=ACCENT),
        name="Validation Score",
        hovertemplate="%{theta}: %{r:.0%}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(
        polar=dict(
            bgcolor=SURFACE,
            radialaxis=dict(
                visible=True, range=[0, 1],
                gridcolor=BORDER, linecolor=BORDER,
                tickfont=dict(color=TEXT_MUTED, size=10),
            ),
            angularaxis=dict(
                gridcolor=BORDER, linecolor=BORDER,
                tickfont=dict(color=TEXT_SECONDARY, size=11),
            ),
        ),
        showlegend=False,
    ))
    return fig
