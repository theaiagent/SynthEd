"""SynthEd Dashboard — Shiny for Python application."""

from __future__ import annotations

import json
import tempfile

import numpy as np
from scipy import stats

from shiny import App, reactive, render, ui

from ..pipeline import SynthEdPipeline
from ..pipeline_config import PipelineConfig

from .theme import CUSTOM_CSS
from .config_bridge import config_to_dict, dict_to_config, DISTRIBUTION_FIELDS
from .components.param_panel import config_accordion
from .components.results_panel import results_layout
from .components.warnings import validate_config, preflight_checklist_ui
from . import charts


# ── UI Layout ──

app_ui = ui.page_navbar(
    ui.head_content(
        ui.tags.style(CUSTOM_CSS),
        ui.tags.link(
            rel="stylesheet",
            href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        ),
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
                # Top bar
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
                        ),
                        ui.column(4, ui.output_ui("preflight_status")),
                        ui.column(4, ui.output_text("status_text", inline=True),
                                  class_="text-end text-secondary"),
                    ),
                    class_="p-3 mb-3",
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


# ── Server Logic ──

def server(input, output, session):
    # Reactive values
    sim_results = reactive.value(None)
    default_config = PipelineConfig()

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

    # ── Distribution editors ──
    @render.ui
    def distribution_editors():
        from .components.distribution_editor import distribution_editor
        pc = default_config.persona_config
        editors = []
        for field_name, label in DISTRIBUTION_FIELDS.items():
            dist_val = getattr(pc, field_name, {})
            editors.append(distribution_editor(f"persona_{field_name}", label, dist_val))
        return ui.div(*editors)

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

        n_students = input.n_students() or 200
        ui.notification_show("Simulation running...", type="message", duration=None, id="sim_progress")

        try:
            vals["output_dir"] = tempfile.mkdtemp(prefix="synthed_dash_")
            config = dict_to_config(vals)
            pipeline = SynthEdPipeline(config=config)
            report = pipeline.run(n_students=n_students)

            sim_results.set(report)
            ui.notification_remove("sim_progress")
            ui.notification_show("Simulation complete!", type="message", duration=3)
        except Exception as e:
            ui.notification_remove("sim_progress")
            ui.notification_show(f"Simulation failed: {e}", type="error", duration=10)

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
        val = report.get("simulation_summary", {}).get("mean_gpa", 0)
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
        # Build weekly dropout from dropout_phase_distribution or mean_dropout_week
        dropout_count = summary.get("dropout_count", 0)
        n = summary.get("total_students", 200)
        mean_week = summary.get("mean_dropout_week", 7)
        std_week = summary.get("std_dropout_week", 3)
        total_weeks = report.get("config", {}).get("semester_weeks", 14)
        if dropout_count == 0:
            return ui.div("No dropouts recorded", class_="text-secondary")
        # Approximate weekly dropout distribution using normal CDF
        weekly = []
        spread = max(std_week, 2.0)
        for w in range(1, total_weeks + 1):
            cdf_val = stats.norm.cdf(w + 0.5, loc=mean_week, scale=spread)
            weekly.append(int(round(cdf_val * dropout_count)) - sum(weekly))
        weekly = [max(0, w) for w in weekly]
        # Rescale to match actual dropout count
        total_approx = sum(weekly)
        if total_approx > 0 and total_approx != dropout_count:
            scale = dropout_count / total_approx
            weekly = [max(0, int(round(w * scale))) for w in weekly]
        fig = charts.dropout_timeline(weekly, n)
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs="cdn"))

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
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs="cdn"))

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
        pass_t = 0.64
        dist_t = 0.73
        try:
            pass_t = input.grading_pass_threshold()
            dist_t = input.grading_distinction_threshold()
        except Exception:
            pass
        fig = charts.gpa_distribution(gpas, pass_t, dist_t)
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs="cdn"))

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
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs="cdn"))

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
            config_dict = vals
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
            with open(path, "r") as f:
                config_dict = json.load(f)
            PipelineConfig.from_dict(config_dict)  # validate
            ui.notification_show("Config imported successfully", type="message", duration=3)
        except Exception as e:
            ui.notification_show(f"Import failed: {e}", type="error", duration=5)

    # ── Helper: collect current UI values ──
    def _collect_current_values() -> dict:
        """Collect current values from all UI inputs into a flat dict."""
        vals = config_to_dict(default_config)

        # Override with current input values where available
        for key in list(vals.keys()):
            input_key = key
            try:
                input_val = input[input_key]()
                if input_val is not None:
                    vals[key] = input_val
            except (KeyError, TypeError):
                pass

        # Pipeline scalars
        for key in ("seed", "n_semesters", "output_dir", "export_oulad", "cost_threshold"):
            try:
                val = input[key]()
                if val is not None:
                    vals[key] = val
            except (KeyError, TypeError):
                pass

        return vals


# ── App ──

app = App(app_ui, server)
