"""Accessibility regression guards for the dashboard (audit P1-6/P1-7/P1-10/P3-2).

Static checks against rendered Shiny tag trees and the `synthed.dashboard.app`
module source. No live-server / Playwright dependency — these run in <1 s.
"""
from __future__ import annotations

import inspect

from synthed.dashboard import app as dashboard_app
from synthed.dashboard.components.param_panel import _tooltip_icon


def test_tooltip_icon_has_aria_label():
    """P1-7: the `?` tooltip span must carry an `aria-label` so screen readers
    announce the help text instead of just 'question mark' / nothing.
    """
    icon = _tooltip_icon("dropout_base_rate")
    assert icon != "", "test fixture broken — dropout_base_rate description is missing"
    rendered = str(icon)
    assert 'aria-label="Help:' in rendered, (
        f"tooltip span missing aria-label. Rendered HTML:\n{rendered[:400]}"
    )
    assert 'role="img"' in rendered, (
        "tooltip span should expose role=img so the literal '?' glyph isn't read as the name"
    )


def test_tooltip_icon_no_description_returns_empty_string():
    """Sanity guard: when a field has no help text, no DOM is produced (avoids
    a phantom focusable element with empty aria-label).
    """
    icon = _tooltip_icon("__field_that_does_not_exist__")
    assert icon == "", "fields without descriptions must not render a tooltip span"


def test_app_includes_numeric_locale_script():
    """P1-10: head must include the JS that sets `lang='en'` + `inputmode='decimal'`
    on every `<input type=number>`, and re-applies on dynamic editor mounts.

    Note: this is a deliberately source-coupled regression guard. If the JS is
    ever extracted to a separate file (`synthed/dashboard/static/locale.js`
    served via `pkg_resources`), update this test to point at that file
    instead of the module source.
    """
    src = inspect.getsource(dashboard_app)
    assert "applyNumericLocale" in src, "numeric locale helper script missing from head"
    assert "inputmode" in src, "inputmode attribute setter missing"
    assert "MutationObserver" in src, (
        "MutationObserver missing — dynamically-rendered editors won't get locale attrs"
    )


def test_app_sets_root_lang_to_en():
    """P1-10: root `<html>` should be tagged `lang='en'` so number inputs and
    screen readers do not inherit the OS locale.
    """
    src = inspect.getsource(dashboard_app)
    assert "documentElement.lang = 'en'" in src, "root lang must be set to 'en'"
