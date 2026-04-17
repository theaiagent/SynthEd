# Dashboard UI/UX Audit — 2026-04-17

> Comprehensive UI/UX review of SynthEd Shiny dashboard. Findings verified via Playwright automation (contrast ratios measured, DOM state captured, 4 responsive breakpoints tested).
> Viewport baseline: 1745×828 · Theme tested: dark + light · Browser: Chromium
> **Calibration context**: PR #76 merged, full calibration started 2026-04-17 17:22.

## Executive Summary

Dashboard design quality is **high** (Phase 3 redesign PR #71 delivered indigo glassmorphism, semantic summary cards, chart polish). Configuration/results flow works end-to-end. Two production-blocker bugs and several accessibility/UX gaps remain.

**P0 (must fix before v1.7.0):** 2 bugs — light theme navbar invisibility, tablet breakpoint overlap.
**P1 (high priority):** 10 items — research UX gaps (validation detail, reference comparison, export), accessibility (focus visibility, tooltip semantics), display bugs (locale).
**P2/P3 (polish):** 17 items — consistency, copy, minor layout.

---

## 🔴 P0 — Production Blockers

### P0-3: Light theme navbar invisible (contrast 1.1:1)

**Evidence (Playwright computed styles):**

```text
Light mode:
  .navbar-brand color: rgb(15, 23, 42)    [dark]
  .navbar background: rgb(10, 12, 16)     [still dark — NOT overridden]
  Contrast ratio: 1.1:1  (WCAG AA min: 4.5:1)

Dark mode:
  .navbar-brand color: rgb(241, 245, 249)
  .navbar background: rgb(10, 12, 16)
  Contrast ratio: 17.87:1  ✓
```

**Root cause:** `theme.py:62-66` base `.navbar` sets `background: rgba(10,12,16,0.75) !important;`. Override at `theme.py:339-342` `body.light-mode .navbar { background: rgba(248,250,252,0.85) !important }` should win on specificity (body class adds one selector weight), **but** Shiny `page_navbar()` emits `data-bs-theme="dark"` on the navbar element which invokes Bootstrap 5's `[data-bs-theme="dark"]` variable scoping and defeats the override.

**Files:**
- `synthed/dashboard/theme.py:62-66, 339-342`
- `synthed/dashboard/app.py` (page_navbar call — verify `bg`/`inverse`/`navbar_options`)

### P0-5: Tablet (768px) run-bar content overlap

**Evidence:** `ui_audit_results/05_responsive_tablet_768.png` — "Run Simulation" button + "✓ All checks passed" + "N=200, seed=42, 1 sem" overlap each other; status text truncated.

**Breakpoint summary:**

| Width | Sidebar | Run-bar | Horizontal scroll |
|-------|---------|---------|-------------------|
| 360 | stacked | below fold | ❌ none |
| **768** | side-by-side | **overlap** 🔴 | ❌ none |
| 1024 | side-by-side | OK | ❌ none |
| 1920 | side-by-side | OK | ❌ none |

**Root cause:** `app.py:130-142` `ui.row(ui.column(4, run_button), ui.column(4, preflight), ui.column(4, status))` uses fixed 4-4-4 columns. At 768px with sidebar occupying ~50%, main area ~400px → each column ~133px, insufficient for button + status.

---

## 🟠 P1 — High Priority

### Research UX Gaps
- **P1-1**: Validation test list missing — "14/21 passed" shown but the 7 failed tests are not named. Blocks researcher diagnosis. Add collapsible table (test name, expected, actual, pass/fail).
- **P1-2**: Synthetic vs OULAD reference comparison missing. Only radar chart shows 3 aggregate scores. Overlay OULAD dashed target on each histogram + diff %.
- **P1-4**: Run metadata missing. Results panel shows no config summary (seed, N, commit hash, timestamp) → reproducibility hard.
- **P1-5**: No "Export Results" button. Users cannot download JSON/CSV.
- **P1-8**: Chart Settings offcanvas has no Validation Radar config (Histograms + Dropout Timeline + GPA + Engagement configurable, radar not).

### Accessibility
- **P1-3** (resolved in this PR): Status text "N=200, seed=42, 1 sem" was ~2.5:1 at audit time (WCAG AA FAIL). Uses `class="text-end text-secondary"`, which maps to `TEXT_SECONDARY` in `theme.py:13`. This PR raises the dark-mode value from `#94A3B8` (3.2:1) to `#B0BCC8` (4.6:1 on `--bg`). Light-mode secondary text at `#475569` on `#F8FAFC` is ~7.2:1 (already passing).
- **P1-6**: Keyboard focus visibility 14/20 (70%). 6 interactive elements have `outline: 0` with barely-visible `box-shadow: 0.9px @ 0.12 opacity`. Accordion buttons worst (`rgba(0,123,194,0.024)`).
- **P1-7**: `?` tooltip span is keyboard-focusable (10+ in tab order) but has empty text content → screen reader announces "nothing." Add `aria-label` or make non-focusable wrapper.

### Display Bugs (data layer OK)
- **P1-9** (downgraded from P0): Slider ↔ numeric input *display* diverges at step=0.05 (slider shows `0.15`, input shows `0,1`) in Turkish Chrome. DOM `valueAsNumber = 0.15` for both — backend unaffected. Cause: `<input type=number step="0.01">` + Chrome TR locale rendering.
- **P1-10** (downgraded from P0): Prior GPA Mean / distribution numeric inputs have `lang=""` and `inputmode=""` empty. Display "2,3" while value is "2.3". Set `lang="en"` + `inputmode="decimal"` on numeric inputs.

---

## 🟡 P2 — Medium

- **P2-1**: Institutional accordion — 5 sliders single-column; Persona uses 2-column for Digital/Self Regulation. Inconsistent; group as 2+2+1.
- **P2-2**: Distributions section is outside the accordion system, breaking visual rhythm (Persona/Institutional/Grading accordion → Distributions free section).
- **P2-3**: Engine Constants label use `_UPPERCASE_CONST_NAME`. Add UI-friendly labels + tooltip per constant.
- **P2-4**: Dual Hurdle checkbox has no `?` tooltip; every other label in Grading does.
- **P2-5**: Empty results state ("Results will appear here") too ghost-like. Add illustration + CTA.
- **P2-6**: Validation Radar uses only 3 axes (Temporal/Demographics/Other) → shallow 2D triangle. Expand to 6+ categories.
- **P2-7**: Radar axis label "Other" is non-descriptive.
- **P2-10**: Engine Constants offcanvas backdrop transparent/weak — doesn't feel modal.

## 🟢 P3 — Polish

- **P3-1**: Distribution labels (`high_school`, `prior_education`) shown in `snake_case`. Use Title Case in UI.
- **P3-2**: Section headings "Presets", "Distributions", "Gender" very muted — font-weight + color up.
- **P3-3**: Engagement Mean/Median dashed-line labels overlap when values are close (0.140 vs 0.138).
- **P3-5**: Import file input + Export Config button have inconsistent styling — both should be icon+label buttons.
- **P3-6**: No search box for 70 engine constants.
- **P3-8**: "Generate Names" checkbox has no explanation — tooltip should mention LLM requirement.
- **P3-9**: Slider value badge sticks to left edge when handle is at minimum (e.g. Late Penalty 0.05). Consider floating label.

---

## ✅ Strengths (What's Working Well)

**Design:** Indigo + glassmorphism palette, semantic summary cards (Dropout red / Engagement amber / GPA blue / Validation green) with border-left accent, preflight check amber banner, ∑=1.00 ✓ distribution normalization indicator, threshold overlay dashed lines on histograms, preset active glow, chart line+markers, progressive disclosure ("Chart Settings" offcanvas).

**Behavior:** Accordion multiple=False, sticky run-bar at scroll, independent sidebar scroll, responsive no-horizontal-scroll at all tested widths, preset active state reactive.

**Accessibility partial:** Tab order logical for first 20 elements; `?` tooltips exist; ARIA roles on tablist/separator.

---

## Verification Methodology

1. Manual exploration via `Claude-in-Chrome` MCP (click limited by extension conflict) + user-assisted clicks
2. Desktop screenshots via `computer-use` MCP at each state
3. Playwright headless automation script (`tmp_ui_audit.py`, deleted post-audit) captured:
   - Computed CSS colors for contrast-ratio math
   - DOM `valueAsNumber` to distinguish display bugs from data bugs
   - Tab order of first 20 focusable elements with focus styles
   - Full-page screenshots at 360/768/1024/1920 widths
   - Theme toggle state verification

## Next Steps

- Spec: `docs/superpowers/specs/2026-04-17-dashboard-ui-fixes-design.md` — focuses on P0-3 and P0-5 (v1.7.0 blockers)
- P1 items tracked for Phase 4 UX iteration
- P2/P3 added to existing `project_phase2_ux_audit.md` backlog
