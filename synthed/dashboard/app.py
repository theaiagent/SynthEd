"""SynthEd Dashboard — Shiny for Python application."""

from __future__ import annotations

import json
import logging
import os
import tempfile

import numpy as np
from scipy import stats

from shiny import App, reactive, render, ui

from ..pipeline import SynthEdPipeline
from ..pipeline_config import PipelineConfig

from .theme import CUSTOM_CSS
from .config_bridge import (
    config_to_dict,
    dict_to_config,
    validate_output_dir,
    DISTRIBUTION_FIELDS,
    PRESETS,
    MAX_IMPORT_SIZE_BYTES,
    MAX_N_STUDENTS,
)
from .components.param_panel import config_accordion
from .components.results_panel import results_layout
from .components.warnings import validate_config, preflight_checklist_ui
from . import charts

logger = logging.getLogger(__name__)


# ── UI Layout ──

app_ui = ui.page_navbar(
    ui.head_content(
        ui.busy_indicators.use(spinners=True, pulse=True),
        ui.tags.style(CUSTOM_CSS),
        ui.tags.link(
            rel="stylesheet",
            href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        ),
        ui.tags.script(src="https://cdn.plot.ly/plotly-2.35.0.min.js"),
    ),
    ui.nav_panel(
        "Configure",
        ui.layout_sidebar(
            ui.sidebar(
                config_accordion(),
                # Distribution editors for PersonaConfig
                ui.hr(style="border-color:var(--border,#1E2130);"),
                ui.h6("Distributions", class_="text-secondary"),
                ui.output_ui("distribution_editors"),
                width="420px",
                bg="#12141C",
            ),
            # Main content area
            ui.div(
                # Top bar — sticky
                ui.div(
                    ui.row(
                        ui.column(
                            4,
                            ui.input_action_button(
                                "run_simulation",
                                ui.span(
                                    ui.tags.i(class_="bi bi-play-fill me-1"),
                                    "Run Simulation",
                                ),
                                class_="btn btn-primary",
                            ),
                            ui.output_ui("sim_status_indicator"),
                        ),
                        ui.column(4, ui.output_ui("preflight_status")),
                        ui.column(4, ui.output_text("status_text", inline=True),
                                  class_="text-end text-secondary"),
                    ),
                    class_="run-bar-sticky p-3 mb-3",
                    style="background:var(--surface,#1A1D27);border-radius:10px;border:1px solid var(--border,#1E2130);",
                ),
                # Results area (shown after simulation)
                ui.output_ui("results_area"),
            ),
        ),
    ),
    title=ui.span(
        ui.tags.span("S", class_="badge bg-primary me-2",
                      style="font-size:14px;border-radius:6px;"),
        "SynthEd Dashboard",
    ),
    bg="#0A0C10",
    inverse=True,
)


# ── Utilities ──


def _approximate_weekly_dropouts(
    dropout_count: int,
    mean_week: float,
    std_week: float,
    total_weeks: int,
) -> list[int]:
    """Approximate weekly dropout distribution from summary statistics."""
    spread = max(std_week, 2.0)
    weekly: list[int] = []
    for w in range(1, total_weeks + 1):
        cdf_val = stats.norm.cdf(w + 0.5, loc=mean_week, scale=spread)
        weekly.append(int(round(cdf_val * dropout_count)) - sum(weekly))
    weekly = [max(0, w) for w in weekly]
    total_approx = sum(weekly)
    if total_approx > 0 and total_approx != dropout_count:
        scale = dropout_count / total_approx
        weekly = [max(0, int(round(w * scale))) for w in weekly]
    return weekly


# ── Server Logic ──

def server(input, output, session):
    # Reactive values
    sim_results = reactive.value(None)
    active_preset = reactive.value("default")
    default_config = PipelineConfig()

    # ── Preset buttons (reactive active state) ──
    @render.ui
    def preset_buttons_ui():
        current = active_preset.get()
        def _cls(name: str) -> str:
            base = "btn preset-btn me-1"
            return f"{base} btn-primary active" if name == current else f"{base} btn-outline-secondary"
        return ui.div(
            ui.input_action_button("preset_default", "Default", class_=_cls("default")),
            ui.input_action_button("preset_high_risk", "High Risk", class_=_cls("high_risk")),
            ui.input_action_button("preset_low_dropout", "Low Dropout", class_=_cls("low_dropout")),
            class_="d-flex",
        )

    # ── Status text ──
    @render.text
    def status_text():
        n = input.n_students() or 200
        seed = input.seed() or 42
        sem = input.n_semesters() or 1
        return f"N={n}, seed={seed}, {sem} sem"

    # ── Pre-flight validation ──
    @render.ui
    def preflight_status():
        vals = _collect_current_values()
        issues = validate_config(vals)
        return preflight_checklist_ui(issues)

    # ── Dual hurdle conditional thresholds ──
    @render.ui
    def dual_hurdle_thresholds():
        if not input.grading_dual_hurdle():
            return ui.div()
        return ui.div(
            ui.h6("Component Pass Thresholds", class_="text-secondary mt-2", style="font-size:12px;"),
            ui.input_slider("grading_component_exam_threshold", "Exam threshold",
                            min=0.0, max=1.0, value=0.40, step=0.01),
            ui.input_slider("grading_component_assignment_threshold", "Assignment threshold",
                            min=0.0, max=1.0, value=0.40, step=0.01),
        )

    # ── Distribution editors + reactive sums ──
    _pc = default_config.persona_config
    _dist_registry = {
        f"persona_{fn}": list(getattr(_pc, fn, {}).keys())
        for fn in DISTRIBUTION_FIELDS
    }

    @render.ui
    def distribution_editors():
        from .components.distribution_editor import distribution_editor
        pc = default_config.persona_config
        editors = []
        for field_name, label in DISTRIBUTION_FIELDS.items():
            dist_val = getattr(pc, field_name, {})
            editors.append(distribution_editor(f"persona_{field_name}", label, dist_val))
        return ui.div(*editors)

    # ── Sync slider <-> numeric for distributions ──
    _sync_pairs: list[tuple[str, str]] = []
    for _oid, _ks in _dist_registry.items():
        for _k in _ks:
            _sync_pairs.append((f"{_oid}_{_k}", f"{_oid}_{_k}_num"))

    def _make_sync(slider_id: str, num_id: str):
        @reactive.effect
        @reactive.event(input[slider_id])
        def _sync_to_num():
            try:
                slider_val = float(input[slider_id]())
                num_val = float(input[num_id]())
                if abs(slider_val - num_val) > 0.001:
                    ui.update_numeric(num_id, value=slider_val)
            except (ValueError, TypeError) as exc:
                logger.debug("Sync slider->num skipped for %s: %s", slider_id, exc)

        @reactive.effect
        @reactive.event(input[num_id])
        def _sync_to_slider():
            try:
                num_val = float(input[num_id]())
                slider_val = float(input[slider_id]())
                if abs(num_val - slider_val) > 0.001:
                    ui.update_slider(slider_id, value=num_val)
            except (ValueError, TypeError) as exc:
                logger.debug("Sync num->slider skipped for %s: %s", num_id, exc)

    for _sid, _nid in _sync_pairs:
        _make_sync(_sid, _nid)

    def _dist_sum_ui(input_id: str, keys: list[str]):
        total = 0.0
        for key in keys:
            try:
                total += float(input[f"{input_id}_{key}"]())
            except Exception:
                logger.debug("Distribution sum: could not read %s_%s", input_id, key)
        ok = abs(total - 1.0) <= 0.01
        color = "var(--success,#2DD4A0)" if ok else "var(--warning,#F5A623)"
        symbol = "\u2713" if ok else "\u2717"
        return ui.div(
            f"\u2211 = {total:.2f} {symbol}",
            class_="text-end",
            style=f"font-family:'JetBrains Mono',monospace;font-size:11px;color:{color};",
        )

    @render.ui
    def persona_gender_distribution_sum():
        return _dist_sum_ui("persona_gender_distribution", _dist_registry["persona_gender_distribution"])

    @render.ui
    def persona_motivation_levels_sum():
        return _dist_sum_ui("persona_motivation_levels", _dist_registry["persona_motivation_levels"])

    @render.ui
    def persona_socioeconomic_distribution_sum():
        return _dist_sum_ui("persona_socioeconomic_distribution", _dist_registry["persona_socioeconomic_distribution"])

    @render.ui
    def persona_prior_education_distribution_sum():
        return _dist_sum_ui("persona_prior_education_distribution", _dist_registry["persona_prior_education_distribution"])

    @render.ui
    def persona_device_distribution_sum():
        return _dist_sum_ui("persona_device_distribution", _dist_registry["persona_device_distribution"])

    @render.ui
    def persona_goal_orientation_distribution_sum():
        return _dist_sum_ui("persona_goal_orientation_distribution", _dist_registry["persona_goal_orientation_distribution"])

    @render.ui
    def persona_learning_style_distribution_sum():
        return _dist_sum_ui("persona_learning_style_distribution", _dist_registry["persona_learning_style_distribution"])

    # ── Simulation status indicator ──
    sim_running = reactive.value(False)

    @render.ui
    def sim_status_indicator():
        if sim_running.get():
            return ui.div(
                ui.tags.span(
                    class_="spinner-border spinner-border-sm me-2",
                    role="status",
                ),
                "Running...",
                class_="text-secondary mt-2",
                style="font-size:13px;",
            )
        return ui.div()

    # ── Run simulation ──
    @reactive.effect
    @reactive.event(input.run_simulation)
    def _run_simulation():
        vals = _collect_current_values()
        issues = validate_config(vals)
        errors = [i for i in issues if i["level"] == "error"]
        if errors:
            ui.notification_show(
                f"{len(errors)} validation error(s) — fix before running",
                type="error",
                duration=5,
            )
            return

        n_students = min(input.n_students() or 200, MAX_N_STUDENTS)
        sim_running.set(True)

        try:
            output_dir = vals.get("output_dir") or ""
            if not output_dir:
                vals["output_dir"] = tempfile.mkdtemp(prefix="synthed_dash_")
            else:
                vals["output_dir"] = validate_output_dir(output_dir)
            config = dict_to_config(vals)
            pipeline = SynthEdPipeline(config=config)
            report = pipeline.run(n_students=n_students)

            sim_results.set(report)
            ui.notification_show("Simulation complete!", type="message", duration=3)
        except Exception:
            logger.exception("Simulation failed")
            ui.notification_show(
                "Simulation failed. Check server logs for details.",
                type="error",
                duration=10,
            )
        finally:
            sim_running.set(False)

    # ── Results area ──
    @render.ui
    def results_area():
        report = sim_results.get()
        if report is None:
            return ui.div(
                ui.div(
                    ui.tags.i(class_="bi bi-gear", style="font-size:48px;opacity:0.2;"),
                    ui.p("Configure parameters and click ", ui.strong("Run Simulation"),
                         class_="mt-2 text-secondary"),
                    ui.p("Results will appear here", class_="text-secondary", style="font-size:13px;"),
                    class_="text-center py-5",
                ),
                style="min-height:400px;display:flex;align-items:center;justify-content:center;",
            )
        return results_layout()

    # ── Summary card renders ──
    @render.text
    def dropout_rate():
        report = sim_results.get()
        if not report:
            return "—"
        rate = report.get("simulation_summary", {}).get("dropout_rate", 0)
        return f"{rate:.1%}"

    @render.text
    def dropout_rate_sub():
        report = sim_results.get()
        if not report:
            return ""
        summary = report.get("simulation_summary", {})
        n = summary.get("total_students", 0)
        dropped = int(n * summary.get("dropout_rate", 0))
        return f"{dropped} / {n}"

    @render.text
    def mean_engagement():
        report = sim_results.get()
        if not report:
            return "—"
        val = report.get("simulation_summary", {}).get("mean_final_engagement", 0)
        return f"{val:.3f}"

    @render.text
    def mean_engagement_sub():
        return "final week avg"

    @render.text
    def mean_gpa():
        report = sim_results.get()
        if not report:
            return "—"
        val = report.get("simulation_summary", {}).get("mean_final_gpa", 0)
        return f"{val:.2f}"

    @render.text
    def mean_gpa_sub():
        return "cumulative"

    @render.text
    def validation_grade():
        report = sim_results.get()
        if not report:
            return "—"
        results = _get_validation_results(report)
        if not results:
            return "—"
        passed = sum(1 for r in results if isinstance(r, dict) and r.get("passed"))
        total = len(results)
        if total == 0:
            return "—"
        ratio = passed / total
        if ratio >= 0.85:
            return "A"
        if ratio >= 0.70:
            return "B"
        if ratio >= 0.55:
            return "C"
        return "D"

    @render.text
    def validation_grade_sub():
        report = sim_results.get()
        if not report:
            return ""
        results = _get_validation_results(report)
        if not results:
            return ""
        passed = sum(1 for r in results if isinstance(r, dict) and r.get("passed"))
        return f"{passed}/{len(results)} passed"

    # ── Chart renders ──
    @render.ui
    def chart_dropout():
        report = sim_results.get()
        if not report:
            return ui.div()
        summary = report.get("simulation_summary", {})
        dropout_count = summary.get("dropout_count", 0)
        n = summary.get("total_students", 200)
        if dropout_count == 0 or n == 0:
            return ui.div("No dropouts recorded", class_="text-secondary")
        mean_week = summary.get("mean_dropout_week", 7)
        std_week = summary.get("std_dropout_week", 3)
        total_weeks = report.get("config", {}).get("semester_weeks", 14)
        weekly = _approximate_weekly_dropouts(
            dropout_count, mean_week, std_week, total_weeks,
        )
        fig = charts.dropout_timeline(weekly, n)
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs=False))

    @render.ui
    def chart_engagement():
        report = sim_results.get()
        if not report:
            return ui.div()
        summary = report.get("simulation_summary", {})
        mean_eng = summary.get("mean_final_engagement", 0)
        std_eng = summary.get("std_final_engagement", 0.05)
        n = summary.get("retained_students", 50)
        if mean_eng == 0:
            return ui.div("No engagement data", class_="text-secondary")
        # Approximate distribution from summary stats
        rng = np.random.default_rng(0)
        engagements = np.clip(rng.normal(mean_eng, max(std_eng, 0.01), n), 0.01, 0.99).tolist()
        fig = charts.engagement_distribution(engagements)
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs=False))

    @render.ui
    def chart_gpa():
        report = sim_results.get()
        if not report:
            return ui.div()
        summary = report.get("simulation_summary", {})
        mean_gpa = summary.get("mean_final_gpa", 0)
        n = summary.get("total_students", 100)
        if mean_gpa == 0:
            return ui.div("No GPA data", class_="text-secondary")
        # Approximate GPA distribution from summary stats
        std_gpa = summary.get("std_final_gpa", 0.6)
        rng = np.random.default_rng(0)
        gpas = np.clip(rng.normal(mean_gpa, max(std_gpa, 0.1), n), 0.0, 4.0).tolist()
        # Convert [0,1] thresholds to GPA scale [0,4]
        gpa_scale = 4.0
        pass_t = 0.64
        dist_t = 0.73
        try:
            pass_t = input.grading_pass_threshold()
            dist_t = input.grading_distinction_threshold()
        except (KeyError, TypeError):
            logger.debug("GPA chart: using default thresholds (inputs not yet available)")
        fig = charts.gpa_distribution(gpas, pass_t * gpa_scale, dist_t * gpa_scale)
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs=False))

    @render.ui
    def chart_validation():
        report = sim_results.get()
        if not report:
            return ui.div()
        results = _get_validation_results(report)
        if not results:
            return ui.div("No validation data", class_="text-secondary")
        # Group by test name prefix as proxy for levels
        categories = {"Demographics": [], "Correlations": [], "Temporal": [],
                      "Privacy": [], "Other": []}
        for r in results:
            if not isinstance(r, dict):
                continue
            test = r.get("test", "")
            if any(k in test for k in ("age", "gender", "employment", "dropout_rate", "gpa")):
                categories["Demographics"].append(r)
            elif "correlation" in test or "engagement" in test:
                categories["Correlations"].append(r)
            elif "timing" in test or "attrition" in test or "temporal" in test:
                categories["Temporal"].append(r)
            elif "privacy" in test or "backstory" in test:
                categories["Privacy"].append(r)
            else:
                categories["Other"].append(r)
        scores = {}
        for cat, items in categories.items():
            if items:
                scores[cat] = sum(1 for i in items if i.get("passed")) / len(items)
        if not scores:
            return ui.div("No validation categories", class_="text-secondary")
        fig = charts.validation_radar(scores)
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs=False))

    def _get_validation_results(report: dict) -> list:
        """Extract validation results from report (handles nested structure)."""
        val = report.get("validation", {})
        if isinstance(val, dict):
            return val.get("results", [])
        if isinstance(val, list):
            return val
        return []

    # ── Config export ──
    @render.download(filename="synthed_config.json")
    def export_config():
        vals = _collect_current_values()
        try:
            config = dict_to_config(vals)
            config_dict = config.to_dict()
        except Exception:
            logger.exception("Config export: dict_to_config failed, using raw values")
            config_dict = {**vals, "__bridge_fallback": True}
        yield json.dumps(config_dict, indent=2, default=str)

    # ── Config import ──
    @reactive.effect
    @reactive.event(input.import_config)
    def _import_config():
        file_info = input.import_config()
        if not file_info:
            return
        try:
            path = file_info[0]["datapath"]
            file_size = os.path.getsize(path)
            if file_size > MAX_IMPORT_SIZE_BYTES:
                ui.notification_show(
                    f"Import failed: file exceeds {MAX_IMPORT_SIZE_BYTES // 1024}KB limit",
                    type="error",
                    duration=5,
                )
                return
            with open(path, "r") as f:
                config_dict = json.load(f)
            if "n_students" in config_dict:
                config_dict["n_students"] = min(config_dict["n_students"], MAX_N_STUDENTS)
            PipelineConfig.from_dict(config_dict)  # validate
            # TODO Phase 2: apply imported values to UI inputs via session.send_input_message
            ui.notification_show(
                "Config validated (UI update deferred to Phase 2)",
                type="message",
                duration=3,
            )
        except Exception:
            logger.exception("Config import failed")
            ui.notification_show(
                "Import failed: invalid configuration file",
                type="error",
                duration=5,
            )

    # ── Preset handlers ──
    def _apply_preset(preset_name: str) -> None:
        overrides = PRESETS.get(preset_name, {})
        defaults = config_to_dict(default_config)
        merged = {**defaults, **overrides}
        for key, val in merged.items():
            try:
                if isinstance(val, (int, float)):
                    ui.update_slider(key, value=val)
                elif isinstance(val, str):
                    ui.update_text(key, value=val)
            except Exception as exc:
                logger.debug("Preset update skipped for key=%s: %s", key, exc)

    @reactive.effect
    @reactive.event(input.preset_default)
    def _preset_default():
        active_preset.set("default")
        _apply_preset("default")

    @reactive.effect
    @reactive.event(input.preset_high_risk)
    def _preset_high_risk():
        active_preset.set("high_risk")
        _apply_preset("high_risk")

    @reactive.effect
    @reactive.event(input.preset_low_dropout)
    def _preset_low_dropout():
        active_preset.set("low_dropout")
        _apply_preset("low_dropout")

    # ── Helper: collect current UI values ──
    def _collect_current_values() -> dict:
        """Collect current values from all UI inputs into a flat dict."""
        vals = config_to_dict(default_config)

        # Override with current input values where available
        for key in list(vals.keys()):
            try:
                input_val = input[key]()
                if input_val is not None:
                    vals[key] = input_val
            except Exception:
                pass

        # Pipeline scalars
        for key in ("seed", "n_semesters", "output_dir", "export_oulad", "cost_threshold"):
            try:
                val = input[key]()
                if val is not None:
                    vals[key] = val
            except Exception:
                pass

        # Distribution dicts: read individual slider values
        for input_id, keys in _dist_registry.items():
            dist = {}
            for sub_key in keys:
                try:
                    dist[sub_key] = float(input[f"{input_id}_{sub_key}"]())
                except Exception:
                    dist[sub_key] = vals.get(input_id, {}).get(sub_key, 0.0)
            vals[input_id] = dist

        return vals


# ── App ──

app = App(app_ui, server)
