"""Dark theme configuration for SynthEd Dashboard."""

from __future__ import annotations

# ── Color Palette (single source of truth) ──
BG = "#0F1117"
SURFACE = "#1A1D27"
ELEVATED = "#242838"
BORDER = "#1E2130"
BORDER_HOVER = "#2A2D3A"

TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

ACCENT = "#6366F1"
ACCENT_LIGHT = "#818CF8"
ACCENT_DARK = "#4F46E5"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#F43F5E"
INFO = "#3B82F6"

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
    "accent-light": ACCENT_LIGHT,
    "accent-dark": ACCENT_DARK,
    "success": SUCCESS,
    "warning": WARNING,
    "error": ERROR,
    "info": INFO,
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

/* Navbar — glassmorphism */
.navbar, .navbar-default {
    background: rgba(10, 12, 16, 0.75) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border) !important;
    position: sticky;
    top: 0;
    z-index: 1030;
}
.navbar-brand { color: var(--text-primary) !important; font-weight: 700; }
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
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15) !important;
}

/* Labels */
.control-label, .shiny-input-container > label, label {
    color: var(--text-secondary) !important;
    font-size: 12px !important;
    font-weight: 500;
}

/* Heading contrast — WCAG AA */
h5, .h5 { color: var(--text-primary) !important; font-weight: 600; }
h6, .h6 { color: var(--text-secondary) !important; font-weight: 600; }

/* Sliders — gradient track */
.irs--shiny .irs-bar { background: linear-gradient(90deg, var(--accent), var(--accent-light)); }
.irs--shiny .irs-handle { border-color: var(--accent); background: #fff; box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }
.irs--shiny .irs-line { background: var(--border-hover); }
.irs--shiny .irs-single { background: var(--accent); font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.irs--shiny .irs-min, .irs--shiny .irs-max { color: var(--text-muted); }

/* Buttons — gradient + glow */
.btn-primary {
    background: linear-gradient(135deg, var(--accent) 0%, #7C3AED 100%) !important;
    border: none !important;
    font-weight: 600;
    transition: box-shadow 0.2s ease, transform 0.15s ease;
}
.btn-primary:hover {
    box-shadow: 0 0 16px rgba(99, 102, 241, 0.4) !important;
    background: linear-gradient(135deg, var(--accent-light) 0%, #8B5CF6 100%) !important;
    transform: translateY(-1px);
}
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

/* JetBrains Mono for numeric inputs */
.value-display, .metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
}

/* Summary card — glassmorphism + semantic accent */
.summary-card {
    background: linear-gradient(135deg, var(--surface) 0%, var(--elevated) 100%);
    border: 1px solid rgba(148, 163, 184, 0.08);
    border-left: 3px solid var(--accent);
    border-radius: 12px;
    padding: 20px 24px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.summary-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}
.summary-card--dropout  { border-left-color: var(--error); }
.summary-card--warning  { border-left-color: var(--warning); }
.summary-card--success  { border-left-color: var(--success); }
.summary-card--info     { border-left-color: var(--info, var(--accent)); }
.summary-card .card-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 500;
}
.summary-card .card-value {
    font-family: 'Inter', sans-serif;
    font-size: 28px;
    font-weight: 700;
}
.card-value.text-danger { color: var(--error) !important; }
.card-value.text-warning { color: var(--warning) !important; }
.card-value.text-success { color: var(--success) !important; }
.card-value.text-info { color: var(--info) !important; }

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
