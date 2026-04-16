"""SynthEd HTML/PDF report generator."""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from .charts import (
    age_distribution_chart,
    employment_chart,
    figure_to_png,
    gender_distribution_chart,
)
from .translations import TRANSLATIONS

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_EM_DASH = "\u2014"

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate HTML and PDF reports from SynthEd pipeline output.

    Parameters
    ----------
    report_data:
        The dict returned by ``SynthEdPipeline.run()``.
    lang:
        Language code for translations (``"en"`` or ``"tr"``).
    detailed:
        Reserved for future use (include per-student details).
    calibration_data:
        Optional calibration metadata to include in the report.
    """

    def __init__(
        self,
        report_data: dict,
        lang: str = "en",
        detailed: bool = False,
        calibration_data: dict | None = None,
    ) -> None:
        self._data = report_data
        self._lang = lang
        self._detailed = detailed
        self._calibration_data = calibration_data

    # ── Public API ──────────────────────────────────────────────────────

    def render_html(self) -> str:
        """Render the report as an HTML string."""
        from jinja2 import Environment, FileSystemLoader

        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        template = env.get_template("report.html")
        context = self._build_context()
        return template.render(**context)

    def render_pdf(self) -> bytes:
        """Render the report as PDF bytes using Playwright Chromium."""
        from playwright.sync_api import sync_playwright

        html = self.render_html()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.set_default_timeout(60000)
                page.set_default_navigation_timeout(60000)
                page.set_content(html, wait_until="networkidle")
                pdf = page.pdf(
                    format="A4",
                    margin={
                        "top": "20mm",
                        "bottom": "20mm",
                        "left": "15mm",
                        "right": "15mm",
                    },
                )
            finally:
                browser.close()
        return pdf

    def save_html(self, path: str) -> None:
        """Render and save the report as an HTML file."""
        html = self.render_html()
        Path(path).write_text(html, encoding="utf-8")

    def save_pdf(self, path: str) -> None:
        """Render and save the report as a PDF file."""
        pdf = self.render_pdf()
        Path(path).write_bytes(pdf)

    # ── Private helpers ─────────────────────────────────────────────────

    def _build_context(self) -> dict[str, Any]:
        """Build template context from report_data."""
        t = TRANSLATIONS.get(self._lang, TRANSLATIONS["en"])

        config = self._data.get("config", {})
        pop = self._data.get("population_summary", {})
        sim = self._data.get("simulation_summary", {})
        val = self._data.get("validation", {})
        timing = self._data.get("timing", {})

        # Timing
        total_sec = sum(timing.values()) if timing else 0

        # Validation
        val_summary = val.get("summary", {})
        val_results = val.get("results", [])
        val_passed = val_summary.get("passed", 0)
        val_total = val_summary.get("total_tests", 0)
        val_grade = val_summary.get("overall_quality", _EM_DASH)

        # KPI formatting
        dropout_rate = sim.get("dropout_rate")
        mean_eng = sim.get("mean_final_engagement")
        mean_gpa = sim.get("mean_final_gpa")

        # Charts
        chart_data = self._render_charts(pop, sim, val)

        # Config groups
        config_groups = self._build_config_groups(t)

        return {
            "t": _DotDict(t),
            "lang": self._lang,
            "generated_on": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "version": self._data.get("pipeline", "SynthEd"),
            "n_students": config.get("n_students", _EM_DASH),
            "seed": config.get("seed", _EM_DASH),
            "n_semesters": config.get("semester_weeks", 14) // 14 or 1,
            "duration_sec": round(total_sec, 1),
            # KPIs
            "dropout_rate": f"{dropout_rate:.1%}" if dropout_rate is not None else _EM_DASH,
            "mean_engagement": f"{mean_eng:.3f}" if mean_eng is not None else _EM_DASH,
            "mean_gpa": f"{mean_gpa:.2f}" if mean_gpa is not None else _EM_DASH,
            "validation_grade_value": val_grade,
            # Validation
            "validation_passed": val_passed,
            "validation_total": val_total,
            "validation_results": val_results,
            # Charts (base64)
            **chart_data,
            # Config
            "config_groups": config_groups,
        }

    def _render_charts(
        self,
        pop: dict,
        sim: dict,
        val: dict,
    ) -> dict[str, str]:
        """Render all charts as base64-encoded PNG strings."""
        import plotly.graph_objects as go

        from ..dashboard.charts import (
            dropout_timeline,
            engagement_distribution,
            gpa_distribution,
            validation_radar,
        )

        t = TRANSLATIONS.get(self._lang, TRANSLATIONS["en"])
        result: dict[str, str] = {}

        # Demographics charts
        result["chart_age"] = _fig_to_b64(
            age_distribution_chart(pop, lang=self._lang),
        )
        result["chart_gender"] = _fig_to_b64(
            gender_distribution_chart(pop, lang=self._lang),
        )
        result["chart_employment"] = _fig_to_b64(
            employment_chart(pop, lang=self._lang),
        )

        # Simulation charts — dropout timeline
        dropout_count = sim.get("dropout_count", 0)
        n_students = sim.get("total_students", 1)
        mean_week = sim.get("mean_dropout_week") or 7
        std_week = sim.get("std_dropout_week") or 3
        total_weeks = self._data.get("config", {}).get("semester_weeks", 14)

        weekly = self._approximate_weekly_dropouts(
            dropout_count, mean_week, std_week, total_weeks,
        )
        fig_dropout = dropout_timeline(weekly, n_students)
        result["chart_dropout"] = _fig_to_b64(fig_dropout)

        # Engagement distribution
        mean_eng = sim.get("mean_final_engagement")
        std_eng = sim.get("std_final_engagement", 0.05)
        n_retained = sim.get("retained_students", 50)
        if mean_eng is not None and n_retained > 0:
            rng = np.random.default_rng(0)
            engagements = np.clip(
                rng.normal(mean_eng, max(std_eng, 0.01), n_retained),
                0.01, 0.99,
            ).tolist()
            fig_eng = engagement_distribution(engagements)
        else:
            fig_eng = go.Figure()
        result["chart_engagement"] = _fig_to_b64(fig_eng)

        # GPA distribution
        mean_gpa_val = sim.get("mean_final_gpa")
        n_total = sim.get("total_students", 100)
        if mean_gpa_val is not None and n_total > 0:
            std_gpa = 0.6
            rng = np.random.default_rng(0)
            gpas = np.clip(
                rng.normal(mean_gpa_val, max(std_gpa, 0.1), n_total),
                0.0, 4.0,
            ).tolist()
            fig_gpa = gpa_distribution(gpas)
        else:
            fig_gpa = go.Figure()
        result["chart_gpa"] = _fig_to_b64(fig_gpa)

        # Validation radar
        val_results = val.get("results", [])
        if val_results:
            categories: dict[str, list[dict]] = {
                t["radar_demographics"]: [],
                t["radar_correlations"]: [],
                t["radar_temporal"]: [],
                t["radar_privacy"]: [],
                t["radar_other"]: [],
            }
            for r in val_results:
                if not isinstance(r, dict):
                    continue
                test = r.get("test", "")
                if any(k in test for k in ("age", "gender", "employment", "dropout_rate", "gpa")):
                    categories[t["radar_demographics"]].append(r)
                elif "correlation" in test or "engagement" in test:
                    categories[t["radar_correlations"]].append(r)
                elif "timing" in test or "attrition" in test or "temporal" in test:
                    categories[t["radar_temporal"]].append(r)
                elif "privacy" in test or "backstory" in test:
                    categories[t["radar_privacy"]].append(r)
                else:
                    categories[t["radar_other"]].append(r)

            scores: dict[str, float] = {}
            for cat, items in categories.items():
                if items:
                    scores[cat] = sum(1 for i in items if i.get("passed")) / len(items)

            if scores:
                fig_radar = validation_radar(scores)
                result["chart_radar"] = _fig_to_b64(fig_radar)
            else:
                result["chart_radar"] = ""
        else:
            result["chart_radar"] = ""

        return result

    def _build_config_groups(self, t: dict[str, str]) -> dict[str, list[dict]]:
        """Build grouped configuration summary for template rendering."""
        pop = self._data.get("population_summary", {})

        demographics = [
            {"name": t["age_mean"], "value": _fmt(pop, "age_mean", ".1f")},
            {"name": t["age_std"], "value": _fmt(pop, "age_std", ".1f")},
            {"name": t["gender_dist"], "value": _format_dict(pop.get("gender_distribution", {}), t)},
            {"name": t["employment_intensity"], "value": _fmt(pop, "employment_intensity_mean", ".2f")},
            {"name": t["family_responsibility"], "value": _fmt(pop, "family_responsibility_mean", ".2f")},
        ]

        academic = [
            {"name": t["prior_gpa"], "value": _fmt(pop, "gpa_mean", ".2f")},
            {"name": t["digital_literacy"], "value": _fmt(pop, "digital_literacy_mean", ".2f")},
            {"name": t["self_regulation"], "value": _fmt(pop, "self_regulation_mean", ".2f")},
            {"name": t["motivation_dist"], "value": _format_dict(pop.get("motivation_distribution", {}), t)},
        ]

        risk_factors = [
            {"name": t["financial_stress"], "value": _fmt(pop, "financial_stress_mean", ".2f")},
            {"name": t["self_efficacy"], "value": _fmt(pop, "self_efficacy_mean", ".2f")},
            {"name": t["base_dropout_risk"], "value": _fmt(pop, "base_dropout_risk_mean", ".3f")},
            {"name": t["base_engagement"], "value": _fmt(pop, "base_engagement_mean", ".3f")},
        ]

        return {
            t["demographics"]: demographics,
            t["academic"]: academic,
            t["risk_factors"]: risk_factors,
        }

    @staticmethod
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
            delta = dropout_count - sum(weekly)
            if delta > 0:
                # Add to largest buckets first
                while delta > 0 and weekly:
                    peak_idx = max(range(len(weekly)), key=weekly.__getitem__)
                    weekly[peak_idx] += 1
                    delta -= 1
            elif delta < 0:
                # Subtract from largest buckets first (never below 0)
                while delta < 0 and any(w > 0 for w in weekly):
                    peak_idx = max(range(len(weekly)), key=weekly.__getitem__)
                    if weekly[peak_idx] > 0:
                        weekly[peak_idx] -= 1
                        delta += 1
        return weekly


class _DotDict(dict):
    """Dict subclass allowing attribute-style access for Jinja2 templates."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None


def _fmt(pop: dict, key: str, spec: str) -> str:
    """Format a numeric population value, returning em-dash if missing."""
    val = pop.get(key)
    if isinstance(val, (int, float)):
        return format(val, spec)
    return _EM_DASH


def _fig_to_b64(fig: Any) -> str:
    """Convert a Plotly figure to a base64-encoded PNG string."""
    try:
        png_bytes = figure_to_png(fig)
    except Exception:
        logger.exception("Failed to render report chart")
        return ""
    return base64.b64encode(png_bytes).decode("ascii")


def _format_dict(d: dict, t: dict[str, str] | None = None) -> str:
    """Format a dict as 'key: value%' pairs for config display."""
    if not d:
        return _EM_DASH
    parts = []
    for k, v in d.items():
        label = t.get(str(k), str(k)) if t else str(k)
        if isinstance(v, float):
            parts.append(f"{label}: {v:.0%}")
        else:
            parts.append(f"{label}: {v}")
    return ", ".join(parts)
