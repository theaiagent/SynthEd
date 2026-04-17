"""Structural tests for dashboard theme & layout fixes (v1.7.0).

These are static checks against the generated CSS string and the
`synthed.dashboard.app` module, so they run without a live server or
browser. Visual regression (Playwright) is intentionally scoped out;
if added later, use the `chromium_available` fixture pattern already
established in `tests/test_report.py`.
"""
from __future__ import annotations

import re

from synthed.dashboard import theme
from synthed.dashboard.theme import CUSTOM_CSS, TEXT_SECONDARY


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(rgb: tuple[int, int, int]) -> float:
    def chan(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast(fg: str, bg: str) -> float:
    l1 = _luminance(_hex_to_rgb(fg))
    l2 = _luminance(_hex_to_rgb(bg))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_text_secondary_meets_wcag_aa_on_dark_bg():
    """P1-3: TEXT_SECONDARY must have ≥4.5:1 contrast on --bg."""
    ratio = _contrast(TEXT_SECONDARY, theme.BG)
    assert ratio >= 4.5, (
        f"TEXT_SECONDARY={TEXT_SECONDARY} on BG={theme.BG} has contrast {ratio:.2f}, "
        f"which fails WCAG AA (min 4.5:1)"
    )


def test_light_mode_navbar_rule_covers_adaptive_class():
    """P0-3: light-mode navbar CSS must target both legacy .navbar and
    the new .navbar-adaptive class used with navbar_options.
    """
    # Strip whitespace differences by normalising runs of whitespace
    css = re.sub(r"\s+", " ", CUSTOM_CSS)
    assert "body.light-mode .navbar.navbar-adaptive" in css, (
        "Light-mode CSS must target .navbar.navbar-adaptive (see P0-3 fix)"
    )
    assert "body.light-mode .navbar.navbar-adaptive .navbar-brand" in css, (
        "Light-mode CSS must scope .navbar-brand under .navbar-adaptive"
    )


def test_light_mode_navbar_brand_has_dark_text_color():
    """P0-3: light-mode navbar-brand must be dark text (#0F172A or similar)."""
    css = re.sub(r"\s+", " ", CUSTOM_CSS)
    # Accept the canonical slate-900 or any explicit dark color rule
    match = re.search(
        r"body\.light-mode[^{]*\.navbar-brand[^{]*\{[^}]*color:\s*(#[0-9A-Fa-f]{6})",
        css,
    )
    assert match, "Light-mode navbar-brand must explicitly set color"
    ratio = _contrast(match.group(1), "#F8FAFC")
    assert ratio >= 4.5, (
        f"Light-mode navbar-brand color {match.group(1)} fails WCAG AA on light bg"
    )


def test_app_uses_navbar_options_not_legacy_inverse():
    """P0-3: app must use navbar_options() instead of deprecated bg=/inverse=.

    Regression guard: if someone re-adds inverse=True, Shiny re-emits
    data-bs-theme="dark" on the navbar and the light-mode fix breaks.
    """
    import inspect

    from synthed.dashboard import app as dashboard_app

    src = inspect.getsource(dashboard_app)
    assert "navbar_options=ui.navbar_options" in src or "ui.navbar_options(" in src, (
        "Dashboard must use ui.navbar_options() to avoid data-bs-theme='dark' leak"
    )
    # Hard guard against regression to the broken state. Strip comments &
    # docstrings before matching so historical notes about the old API
    # (like this test's own docstring) don't trigger a false positive.
    src_no_comments = re.sub(r"#[^\n]*", "", src)
    src_no_strings = re.sub(r'"""[\s\S]*?"""', "", src_no_comments)
    assert "inverse=True" not in src_no_strings, (
        "page_navbar(inverse=True) emits data-bs-theme='dark' which defeats "
        "the light-mode override. Use navbar_options(class_='navbar-adaptive') instead."
    )


def test_run_bar_uses_responsive_layout_columns():
    """P0-5: run-bar must use layout_columns with col_widths stacking at <lg.

    At 768px, sidebar stays side-by-side (no collapse), main area ≈400px, and
    a fixed 4/4/4 split overlaps. layout_columns with col_widths={"sm":12,"lg":4}
    stacks below 992px.
    """
    import inspect

    from synthed.dashboard import app as dashboard_app

    src = inspect.getsource(dashboard_app)
    assert "layout_columns" in src, "Run-bar should use ui.layout_columns, not ui.row+ui.column"
    # The col_widths dict must carry both sm and lg entries
    assert re.search(r"col_widths\s*=\s*\{[^}]*['\"]sm['\"]\s*:\s*12", src), (
        "layout_columns must set col_widths['sm']=12 so the run-bar stacks on narrow viewports"
    )
    assert re.search(r"col_widths\s*=\s*\{[^}]*['\"]lg['\"]\s*:\s*4", src), (
        "layout_columns must set col_widths['lg']=4 for the horizontal desktop layout"
    )
