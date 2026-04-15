"""Tests for SynthEd report generation module."""

from __future__ import annotations

import pytest

pytest.importorskip("jinja2", reason="Report tests require jinja2 (pip install -e '.[report]')")
pytest.importorskip("plotly", reason="Report tests require plotly (pip install -e '.[report]')")
pytest.importorskip("playwright", reason="Report tests require playwright (pip install -e '.[report]')")

import plotly.graph_objects as go

from synthed.report.charts import age_distribution_chart, employment_chart, figure_to_png, gender_distribution_chart
from synthed.report.generator import ReportGenerator


def _make_report_data() -> dict:
    """Minimal pipeline.run() return dict for testing."""
    return {
        "pipeline": "SynthEd v0.1.0-test",
        "config": {
            "n_students": 100,
            "seed": 42,
            "llm_enabled": False,
            "semester_weeks": 14,
            "courses": 4,
        },
        "timing": {
            "generation_sec": 0.5,
            "simulation_sec": 1.2,
            "export_sec": 0.3,
            "validation_sec": 0.8,
        },
        "population_summary": {
            "total_students": 100,
            "age_mean": 30.5,
            "age_std": 8.2,
            "gender_distribution": {"male": 0.55, "female": 0.45},
            "employment_intensity_mean": 0.69,
            "family_responsibility_mean": 0.35,
            "financial_stress_mean": 0.55,
            "gpa_mean": 2.3,
            "gpa_std": 0.8,
            "digital_literacy_mean": 0.50,
            "self_regulation_mean": 0.42,
            "learner_autonomy_mean": 0.50,
            "self_efficacy_mean": 0.55,
            "base_dropout_risk_mean": 0.25,
            "base_engagement_mean": 0.60,
            "motivation_distribution": {"intrinsic": 0.25, "extrinsic": 0.45, "amotivation": 0.30},
        },
        "simulation_summary": {
            "total_students": 100,
            "dropout_count": 28,
            "dropout_rate": 0.28,
            "mean_dropout_week": 8.5,
            "std_dropout_week": 3.2,
            "mean_final_engagement": 0.612,
            "std_final_engagement": 0.15,
            "mean_final_gpa": 2.45,
            "retained_students": 72,
        },
        "validation": {
            "summary": {
                "total_tests": 21,
                "passed": 17,
                "failed": 4,
                "pass_rate": 0.81,
                "overall_quality": "B",
            },
            "results": [
                {"test": "age_distribution", "metric": "KS-test", "synthetic": 30.2, "reference": 30.0, "p_value": 0.85, "passed": True},
                {"test": "gender_distribution", "metric": "chi-squared", "synthetic": 0.55, "reference": 0.55, "p_value": 0.92, "passed": True},
                {"test": "employment_distribution", "metric": "binomial", "synthetic": 0.68, "reference": 0.69, "p_value": 0.78, "passed": True},
                {"test": "dropout_rate_range", "metric": "range-check", "synthetic": 0.28, "reference": 0.31, "p_value": None, "passed": True},
                {"test": "gpa_mean", "metric": "t-test", "synthetic": 2.45, "reference": 2.30, "p_value": 0.12, "passed": True},
                {"test": "correlation_engagement_gpa", "metric": "Pearson-r", "synthetic": 0.45, "reference": 0.50, "p_value": 0.03, "passed": True},
                {"test": "correlation_self_reg_dropout", "metric": "Point-biserial", "synthetic": -0.30, "reference": -0.35, "p_value": 0.05, "passed": True},
                {"test": "engagement_trend", "metric": "slope-sign", "synthetic": -0.02, "reference": None, "p_value": None, "passed": True},
                {"test": "timing_dropout_peak", "metric": "range-check", "synthetic": 8.5, "reference": 7.0, "p_value": None, "passed": True},
                {"test": "attrition_curve", "metric": "shape", "synthetic": 0.85, "reference": 0.80, "p_value": 0.15, "passed": True},
                {"test": "temporal_engagement_decay", "metric": "monotone", "synthetic": -0.01, "reference": None, "p_value": None, "passed": True},
                {"test": "privacy_uniqueness", "metric": "k-anonymity", "synthetic": 5.0, "reference": 5.0, "p_value": None, "passed": True},
                {"test": "privacy_reidentification", "metric": "risk-score", "synthetic": 0.02, "reference": 0.05, "p_value": None, "passed": True},
                {"test": "motivation_distribution", "metric": "chi-squared", "synthetic": 0.25, "reference": 0.25, "p_value": 0.88, "passed": True},
                {"test": "self_regulation_mean", "metric": "t-test", "synthetic": 0.42, "reference": 0.42, "p_value": 0.95, "passed": True},
                {"test": "financial_stress_mean", "metric": "t-test", "synthetic": 0.55, "reference": 0.55, "p_value": 0.90, "passed": True},
                {"test": "goal_commitment_correlation", "metric": "Pearson-r", "synthetic": 0.35, "reference": 0.40, "p_value": 0.08, "passed": True},
                {"test": "coi_composite_correlation", "metric": "Pearson-r", "synthetic": 0.28, "reference": 0.30, "p_value": 0.12, "passed": False},
                {"test": "network_degree_correlation", "metric": "Pearson-r", "synthetic": 0.15, "reference": 0.20, "p_value": 0.04, "passed": False},
                {"test": "exhaustion_correlation", "metric": "Pearson-r", "synthetic": -0.22, "reference": -0.25, "p_value": 0.06, "passed": False},
                {"test": "sdt_needs_correlation", "metric": "Pearson-r", "synthetic": 0.32, "reference": 0.35, "p_value": 0.09, "passed": False},
            ],
        },
    }


class TestFigureToPng:
    """figure_to_png returns valid PNG bytes."""

    def test_returns_png_bytes(self):
        fig = go.Figure()
        fig.add_trace(go.Bar(x=["A", "B"], y=[1, 2]))
        result = figure_to_png(fig)
        assert isinstance(result, bytes)
        assert result[:8] == b"\x89PNG\r\n\x1a\n"


class TestDemographicsCharts:
    """Demographics chart functions return go.Figure."""

    def test_age_distribution_returns_figure(self):
        pop = {"age_mean": 30, "age_std": 8, "total_students": 100}
        fig = age_distribution_chart(pop)
        assert isinstance(fig, go.Figure)

    def test_gender_distribution_returns_figure(self):
        pop = {
            "gender_distribution": {"male": 0.55, "female": 0.45},
            "total_students": 100,
        }
        fig = gender_distribution_chart(pop)
        assert isinstance(fig, go.Figure)

    def test_employment_chart_returns_figure(self):
        pop = {"employment_intensity_mean": 0.69, "total_students": 100}
        fig = employment_chart(pop)
        assert isinstance(fig, go.Figure)


class TestReportGenerator:
    """ReportGenerator produces valid HTML and PDF output."""

    def test_render_html_returns_string(self):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data)
        html = gen.render_html()
        assert isinstance(html, str)
        assert "<html" in html
        assert "SynthEd" in html

    def test_render_html_contains_sections(self):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data)
        html = gen.render_html()
        assert "Executive Summary" in html
        assert "Population Demographics" in html
        assert "Simulation Results" in html
        assert "Validation Report" in html
        assert "Configuration" in html

    def test_render_html_turkish(self):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data, lang="tr")
        html = gen.render_html()
        assert "Yonetici Ozeti" in html
        assert "Populasyon Demografisi" in html
        assert "Simulasyon Sonuclari" in html
        assert "Dogrulama Raporu" in html
        assert "Yapilandirma" in html

    def test_render_html_contains_dynamic_values(self):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data)
        html = gen.render_html()
        assert "28.0%" in html  # dropout rate
        assert "100" in html    # n_students
        assert "B" in html      # validation grade

    def test_render_pdf_returns_bytes(self):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data)
        pdf = gen.render_pdf()
        assert isinstance(pdf, bytes)
        assert pdf[:5] == b"%PDF-"

    def test_save_html(self, tmp_path):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data)
        path = str(tmp_path / "report.html")
        gen.save_html(path)
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE")

    def test_save_pdf(self, tmp_path):
        data = _make_report_data()
        gen = ReportGenerator(report_data=data)
        path = str(tmp_path / "report.pdf")
        gen.save_pdf(path)
        content = (tmp_path / "report.pdf").read_bytes()
        assert content[:5] == b"%PDF-"
