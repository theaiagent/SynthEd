"""Dark theme configuration for SynthEd Dashboard."""

from __future__ import annotations

# ── Color Palette (single source of truth) ──
BG = "#0F1117"
SURFACE = "#1A1D27"
ELEVATED = "#242838"
BORDER = "#1E2130"
BORDER_HOVER = "#2A2D3A"

TEXT_PRIMARY = "#E8EAF0"
TEXT_SECONDARY = "#8B90A0"
TEXT_MUTED = "#4A4F63"

ACCENT = "#4F8EF7"
SUCCESS = "#2DD4A0"
WARNING = "#F5A623"
ERROR = "#E84545"

_COLOR_VARS: dict[str, str] = {
    "bg": BG,
    "surface": SURFACE,
    "elevated": ELEVATED,
    "border": BORDER,
    "border-hover": BORDER_HOVER,
    "text-primary": TEXT_PRIMARY,
    "text-secondary": TEXT_SECONDARY,
    "text-muted": TEXT_MUTED,
    "accent": ACCENT,
    "success": SUCCESS,
    "warning": WARNING,
    "error": ERROR,
}


def _build_root_block() -> str:
    """Generate CSS :root block from Python color constants."""
    lines = [":root {"]
    for k, v in _COLOR_VARS.items():
        lines.append("    --" + k + ": " + v + ";")
    lines.append("}")
    return "\n".join(lines)


_CSS_STATIC = """\
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600&display=swap');

body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    background: var(--bg) !important;
    color: var(--text-primary) !important;
}

/* Navbar */
.navbar, .navbar-default {
    background: #0A0C10 !important;
    border-bottom: 1px solid var(--border) !important;
}
.navbar-brand { color: var(--text-primary) !important; font-weight: 600; }
.nav-link { color: var(--text-secondary) !important; }
.nav-link.active, .nav-link:hover { color: var(--accent) !important; }

/* Cards */
.card, .well {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}

/* Accordion */
.accordion { --bs-accordion-bg: var(--surface); }
.accordion-item {
    background: var(--surface) !important;
    border-color: var(--border) !important;
}
.accordion-button {
    background: var(--surface) !important;
    color: var(--text-primary) !important;
    font-weight: 600;
    font-size: 13px;
}
.accordion-button:not(.collapsed) { color: var(--accent) !important; }
.accordion-body { background: var(--bg) !important; padding: 8px 16px !important; }

/* Inputs */
.form-control, .form-select {
    background: var(--surface) !important;
    border-color: var(--border-hover) !important;
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
}
.form-control:focus, .form-select:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(79, 142, 247, 0.15) !important;
}

/* Labels */
.control-label, .shiny-input-container > label, label {
    color: var(--text-secondary) !important;
    font-size: 12px !important;
    font-weight: 500;
}

/* Heading contrast fix — WCAG AA min 4.5:1 */
h5, .h5 { color: #A0A5B4 !important; }
h6, .h6 { color: #8B90A0 !important; }

/* Sliders */
.irs--shiny .irs-bar { background: var(--accent); }
.irs--shiny .irs-handle { border-color: var(--accent); background: var(--accent); }
.irs--shiny .irs-line { background: var(--border-hover); }
.irs--shiny .irs-single { background: var(--accent); font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.irs--shiny .irs-min, .irs--shiny .irs-max { color: var(--text-muted); }

/* Buttons */
.btn-primary {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    font-weight: 600;
}
.btn-primary:hover { background: #3D7AE0 !important; }
.btn-outline-secondary {
    border-color: var(--border-hover) !important;
    color: var(--text-secondary) !important;
}
.btn-outline-secondary:hover {
    background: var(--surface) !important;
    color: var(--text-primary) !important;
}

/* Checkboxes */
.form-check-input { background-color: var(--surface); border-color: var(--border-hover); }
.form-check-input:checked { background-color: var(--accent); border-color: var(--accent); }

/* Badges */
.badge-success { background: #1A3A2A !important; color: var(--success) !important; }
.badge-warning { background: #3A2A1A !important; color: var(--warning) !important; }
.badge-info { background: #1E2640 !important; color: var(--accent) !important; }

/* Notification */
.shiny-notification { background: var(--elevated) !important; color: var(--text-primary) !important; border: 1px solid var(--border) !important; }

/* Tooltip */
.tooltip-inner { background: var(--elevated); color: var(--text-secondary); font-size: 12px; max-width: 280px; text-align: left; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-hover); border-radius: 3px; }

/* JetBrains Mono for numeric outputs */
.value-display, .metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
}

/* Summary card styling */
.summary-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
}
.summary-card .card-label {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.summary-card .card-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 24px;
    font-weight: 600;
}

/* Warning border */
.param-warning { border-left: 3px solid var(--warning) !important; }

/* Disabled group */
.group-disabled { opacity: 0.4; pointer-events: none; }

/* Sidebar independent scroll */
.bslib-sidebar-layout > .sidebar {
    overflow-y: auto;
    max-height: calc(100vh - 56px);
}

/* Sticky run button bar */
.run-bar-sticky {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--bg);
}

/* Hint text below inputs */
.param-hint {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
    line-height: 1.3;
}

/* Preset buttons */
.preset-btn {
    font-size: 12px;
    padding: 4px 12px;
}
.preset-btn.active {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #fff !important;
}

/* Card value contrast fix */
.card-value.text-primary { color: #3CA0E6 !important; }
.card-value.text-warning { color: #F5A623 !important; }
.card-value.text-success { color: #2DD4A0 !important; }

/* Import file input placeholder fix */
.shiny-input-container .form-control::file-selector-button {
    color: var(--text-secondary) !important;
}

/* Select dropdown min-width */
.form-select { min-width: 100px; }

/* Sidebar scroll fix — ensure independent scroll */
.bslib-sidebar-layout > .sidebar,
.bslib-sidebar-layout > .sidebar > .sidebar-content {
    overflow-y: auto !important;
    max-height: calc(100vh - 56px) !important;
}

/* Offcanvas backdrop */
.offcanvas-backdrop { background-color: rgba(0,0,0,0.6); }
"""

# Combine generated :root with static CSS
CUSTOM_CSS = _build_root_block() + "\n" + _CSS_STATIC
