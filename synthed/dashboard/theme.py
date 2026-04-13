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
    border-radius: 12px !important;
    font-weight: 600;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    transition: box-shadow 0.2s ease, transform 0.15s ease;
}
.btn-primary:hover {
    box-shadow: 0 6px 25px rgba(99, 102, 241, 0.5) !important;
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

/* Shiny value-box overrides (KPI cards use bslib internally) */
.bslib-value-box .card {
    border-radius: 12px !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.bslib-value-box .card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
}
.bslib-value-box .value-box-value {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 28px !important;
}

/* Main content scroll fix */
[role="tabpanel"] > .container-fluid {
    overflow-y: auto;
    scroll-behavior: smooth;
}

/* Status text overflow fix */
.text-end.text-secondary {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 12px;
}

/* Chart containers — subtle card frame + display fix for Shiny's display:contents */
div.shiny-html-output[id^="chart_"] {
    display: block !important;
    min-height: 400px;
}
.js-plotly-plot {
    border: 1px solid rgba(148, 163, 184, 0.08);
    border-radius: 12px;
    overflow: hidden;
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
    background: linear-gradient(135deg, var(--accent), #8B5CF6) !important;
    border: none !important;
    color: #fff !important;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
}
.preset-btn:not(.active) {
    background: var(--elevated) !important;
    border: 1px solid rgba(148, 163, 184, 0.12) !important;
}
.preset-btn:not(.active):hover {
    border-color: rgba(99, 102, 241, 0.4) !important;
}

/* Sub-section headings inside accordion (Demographics, Academic, Risk) */
.accordion-body h6 {
    color: var(--text-primary) !important;
    font-size: 13px !important;
    font-weight: 600;
    letter-spacing: 0.3px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 4px;
    margin-top: 12px !important;
}

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

/* ── Light Mode Override ── */
body.light-mode {
    --bg: #F8FAFC;
    --surface: #FFFFFF;
    --elevated: #F1F5F9;
    --border: #E2E8F0;
    --border-hover: #CBD5E1;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #94A3B8;
}
body.light-mode .navbar, body.light-mode .navbar-default {
    background: rgba(248, 250, 252, 0.85) !important;
    border-bottom-color: #E2E8F0 !important;
}
body.light-mode .navbar-brand { color: #0F172A !important; }
body.light-mode .sidebar { background: #FFFFFF !important; }
body.light-mode .accordion-item { background: #FFFFFF !important; }
body.light-mode .accordion-button { background: #FFFFFF !important; color: #0F172A !important; }
body.light-mode .accordion-body { background: #F8FAFC !important; }
body.light-mode .form-control, body.light-mode .form-select {
    background: #FFFFFF !important;
    border-color: #E2E8F0 !important;
    color: #0F172A !important;
}
body.light-mode .summary-card {
    background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%);
    border-color: #E2E8F0;
}
body.light-mode .run-bar-sticky { background: #F8FAFC; }
body.light-mode .shiny-notification { background: #FFFFFF !important; color: #0F172A !important; border-color: #E2E8F0 !important; }
body.light-mode .offcanvas { background: #F8FAFC !important; color: #0F172A !important; }
body.light-mode .btn-outline-secondary { border-color: #CBD5E1 !important; color: #475569 !important; }
body.light-mode .irs--shiny .irs-line { background: #E2E8F0; }
body.light-mode .irs--shiny .irs-handle { background: var(--accent); box-shadow: 0 0 0 3px rgba(99,102,241,0.15); }
"""

# Combine generated :root with static CSS
CUSTOM_CSS = _build_root_block() + "\n" + _CSS_STATIC
