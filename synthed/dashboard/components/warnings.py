"""Validation warnings and pre-flight checklist."""

from __future__ import annotations

from typing import Any

from ..config_bridge import check_warning


def validate_config(values: dict[str, Any]) -> list[dict[str, str]]:
    """Run all validation checks and return list of warning/error dicts.

    Returns:
        List of {"field": str, "message": str, "level": "warning"|"error"}.
    """
    issues: list[dict[str, str]] = []

    # Field-level warnings
    for field_name, value in values.items():
        msg = check_warning(field_name, value)
        if msg:
            clean_name = field_name.split("_", 1)[-1] if "_" in field_name else field_name
            issues.append({"field": clean_name, "message": msg, "level": "warning"})

    # Cross-field: distinction > pass
    pass_val = values.get("grading_pass_threshold", 0.64)
    dist_val = values.get("grading_distinction_threshold", 0.73)
    if pass_val >= dist_val:
        issues.append({
            "field": "pass/distinction",
            "message": f"pass_threshold ({pass_val}) must be < distinction_threshold ({dist_val})",
            "level": "error",
        })

    # Cross-field: midterm + final = 1.0
    mw = values.get("grading_midterm_weight", 0.4)
    fw = values.get("grading_final_weight", 0.6)
    if abs(mw + fw - 1.0) > 0.01:
        issues.append({
            "field": "midterm/final weights",
            "message": f"midterm_weight + final_weight = {mw + fw:.2f} (must be 1.0)",
            "level": "error",
        })

    # Cross-field: CLIP_LO < CLIP_HI
    clip_lo = values.get("engine__ENGAGEMENT_CLIP_LO", 0.01)
    clip_hi = values.get("engine__ENGAGEMENT_CLIP_HI", 0.99)
    if clip_lo >= clip_hi:
        issues.append({
            "field": "CLIP_LO/CLIP_HI",
            "message": f"CLIP_LO ({clip_lo}) must be < CLIP_HI ({clip_hi})",
            "level": "error",
        })

    # Distribution sums must equal 1.0
    from ..config_bridge import DISTRIBUTION_FIELDS
    for field_name, label in DISTRIBUTION_FIELDS.items():
        dist = values.get(f"persona_{field_name}")
        if isinstance(dist, dict) and dist:
            total = sum(dist.values())
            if abs(total - 1.0) > 0.01:
                issues.append({
                    "field": label,
                    "message": f"{label} distribution sums to {total:.2f} (must be 1.0)",
                    "level": "error",
                })

    return issues


def preflight_checklist_ui(issues: list[dict[str, str]]):
    """Render the pre-flight checklist as inline UI."""
    from shiny import ui

    if not issues:
        return ui.div(
            ui.span("\u2714 ", style="color:var(--success,#2DD4A0);"),
            "All checks passed",
            style="font-size:12px;color:var(--text-secondary,#8B90A0);",
        )

    items = []
    for issue in issues:
        color = "var(--error,#E84545)" if issue["level"] == "error" else "var(--warning,#F5A623)"
        icon = "\u2716" if issue["level"] == "error" else "\u26A0"
        items.append(
            ui.div(
                ui.span(f"{icon} ", style=f"color:{color};"),
                ui.span(issue["field"], style="font-weight:600;"),
                f": {issue['message']}",
                style=f"font-size:12px;color:{color};padding:3px 0;",
            )
        )

    return ui.div(
        ui.div("Pre-flight Check", style="font-weight:600;font-size:12px;margin-bottom:6px;"),
        *items,
    )


def warning_badge_count(issues: list[dict[str, str]]) -> int:
    """Count warnings for Run button badge."""
    return len(issues)
