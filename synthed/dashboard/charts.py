"""Plotly chart builders for SynthEd Dashboard."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from .theme import (
    BG, SURFACE, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, WARNING,
)


_LAYOUT_DEFAULTS = dict(
    paper_bgcolor=BG,
    plot_bgcolor=SURFACE,
    font=dict(family="Inter, system-ui, sans-serif", color=TEXT_SECONDARY, size=12),
    margin=dict(l=40, r=20, t=30, b=40),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    hoverlabel=dict(bgcolor=SURFACE, font_color=TEXT_PRIMARY, bordercolor=BORDER),
)


def _base_layout(**overrides: Any) -> dict:
    layout = {**_LAYOUT_DEFAULTS}
    layout.update(overrides)
    return layout


def dropout_timeline(weekly_dropouts: list[int], n_students: int) -> go.Figure:
    """Cumulative dropout percentage by week — line chart."""
    cumulative = []
    total = 0
    for count in weekly_dropouts:
        total += count
        cumulative.append(total / n_students * 100)

    weeks = list(range(1, len(cumulative) + 1))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weeks, y=cumulative,
        mode="lines+markers",
        line=dict(color=ACCENT, width=2),
        marker=dict(size=5, color=ACCENT),
        name="Cumulative Dropout %",
        hovertemplate="Week %{x}: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout(
        xaxis_title="Week",
        yaxis_title="Cumulative Dropout %",
        yaxis_range=[0, max(cumulative[-1] * 1.15, 10) if cumulative else 100],
        showlegend=False,
    ))
    return fig


def engagement_distribution(engagements: list[float]) -> go.Figure:
    """Final engagement histogram with mean/median markers."""
    import numpy as np

    mean_val = float(np.mean(engagements))
    median_val = float(np.median(engagements))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=engagements,
        nbinsx=30,
        marker_color=ACCENT,
        opacity=0.8,
        name="Engagement",
        hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=mean_val, line_dash="dash", line_color=WARNING,
                  annotation_text=f"Mean: {mean_val:.3f}", annotation_font_color=WARNING)
    fig.add_vline(x=median_val, line_dash="dot", line_color=SUCCESS,
                  annotation_text=f"Median: {median_val:.3f}", annotation_font_color=SUCCESS)
    fig.update_layout(**_base_layout(
        xaxis_title="Final Engagement",
        yaxis_title="Count",
        showlegend=False,
    ))
    return fig


def gpa_distribution(
    gpas: list[float],
    pass_threshold: float = 0.64,
    distinction_threshold: float = 0.73,
) -> go.Figure:
    """GPA distribution histogram with pass/distinction threshold lines."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=gpas,
        nbinsx=25,
        marker_color=SUCCESS,
        opacity=0.8,
        name="GPA",
        hovertemplate="GPA: %{x:.2f}<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=pass_threshold, line_dash="dash", line_color=WARNING,
                  annotation_text=f"Pass: {pass_threshold:.2f}", annotation_font_color=WARNING)
    fig.add_vline(x=distinction_threshold, line_dash="dash", line_color=ACCENT,
                  annotation_text=f"Distinction: {distinction_threshold:.2f}", annotation_font_color=ACCENT)
    fig.update_layout(**_base_layout(
        xaxis_title="Cumulative GPA",
        yaxis_title="Count",
        showlegend=False,
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
        fillcolor="rgba(79, 142, 247, 0.15)",
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
