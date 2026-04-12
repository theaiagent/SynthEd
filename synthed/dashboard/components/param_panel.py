"""Parameter accordion panels for the configuration sidebar."""

from __future__ import annotations

from shiny import ui

from ..config_bridge import (
    get_description,
)


def _tooltip_icon(field_name: str) -> ui.Tag | str:
    """Create an info tooltip icon for a parameter."""
    desc = get_description(field_name)
    if not desc:
        return ""
    return ui.tooltip(
        ui.span("?", class_="badge rounded-pill bg-secondary", style="font-size:10px;cursor:help;"),
        desc,
        placement="right",
    )


def _slider_input(
    input_id: str,
    label: str,
    value: float,
    min_val: float = 0.0,
    max_val: float = 1.0,
    step: float = 0.01,
) -> ui.Tag:
    """Slider + numeric input for a float parameter."""
    return ui.input_slider(
        input_id,
        ui.span(label, " ", _tooltip_icon(input_id)),
        min=min_val, max=max_val, value=value, step=step,
    )


def pipeline_controls() -> ui.Tag:
    """Pipeline Controls panel — always visible at top."""
    return ui.accordion_panel(
        "Pipeline Controls",
        ui.row(
            ui.column(4, ui.input_numeric("n_students", ui.span("n_students ", _tooltip_icon("n_students")),
                                          value=200, min=10, max=10000, step=10)),
            ui.column(4, ui.input_numeric("seed", ui.span("seed ", _tooltip_icon("seed")),
                                          value=42, min=0)),
            ui.column(4, ui.input_numeric("n_semesters", ui.span("n_semesters ", _tooltip_icon("n_semesters")),
                                          value=1, min=1, max=8)),
        ),
        ui.row(
            ui.column(6, ui.input_checkbox("export_oulad", "Export OULAD format", value=False)),
            ui.column(6, ui.input_text("output_dir", "Output dir", value="./output")),
        ),
        value="pipeline",
        icon=ui.tags.i(class_="bi bi-gear"),
    )


def persona_config_panel() -> ui.Tag:
    """PersonaConfig parameter panel."""
    return ui.accordion_panel(
        "PersonaConfig",
        # Demographics
        ui.h6("Demographics", class_="text-secondary mt-2"),
        _slider_input("persona_employment_rate", "employment_rate", 0.78),
        _slider_input("persona_has_family_rate", "has_family_rate", 0.52),
        _slider_input("persona_financial_stress_mean", "financial_stress_mean", 0.55),
        _slider_input("persona_disability_rate", "disability_rate", 0.10),

        # Academic
        ui.h6("Academic", class_="text-secondary mt-3"),
        ui.row(
            ui.column(6, ui.input_numeric("persona_prior_gpa_mean",
                                          ui.span("prior_gpa_mean ", _tooltip_icon("prior_gpa_mean")),
                                          value=2.3, min=0.0, max=4.0, step=0.1)),
            ui.column(6, ui.input_numeric("persona_prior_gpa_std", "prior_gpa_std",
                                          value=0.8, min=0.0, max=2.0, step=0.1)),
        ),
        ui.row(
            ui.column(6, _slider_input("persona_digital_literacy_mean", "digital_literacy_mean", 0.50)),
            ui.column(6, _slider_input("persona_self_regulation_mean", "self_regulation_mean", 0.42)),
        ),

        # Risk
        ui.h6("Risk", class_="text-secondary mt-3"),
        _slider_input("persona_dropout_base_rate", "dropout_base_rate", 0.80, min_val=0.01),
        _slider_input("persona_unavoidable_withdrawal_rate", "unavoidable_withdrawal_rate", 0.003,
                      max_val=0.05, step=0.001),

        ui.input_checkbox("persona_generate_names", "Generate names", value=False),

        value="persona",
        icon=ui.tags.i(class_="bi bi-people"),
    )


def institutional_config_panel() -> ui.Tag:
    """InstitutionalConfig — 5 quality sliders."""
    inst_fields = [
        ("inst_instructional_design_quality", "instructional_design_quality", 0.5),
        ("inst_teaching_presence_baseline", "teaching_presence_baseline", 0.5),
        ("inst_support_services_quality", "support_services_quality", 0.5),
        ("inst_technology_quality", "technology_quality", 0.5),
        ("inst_curriculum_flexibility", "curriculum_flexibility", 0.5),
    ]
    return ui.accordion_panel(
        "InstitutionalConfig",
        *[_slider_input(fid, label, val) for fid, label, val in inst_fields],
        value="institutional",
        icon=ui.tags.i(class_="bi bi-building"),
    )


def grading_config_panel() -> ui.Tag:
    """GradingConfig — modes, weights, thresholds."""
    return ui.accordion_panel(
        "GradingConfig",
        # Modes
        ui.row(
            ui.column(4, ui.input_select("grading_assessment_mode", "Assessment mode",
                                         {"mixed": "Mixed", "exam_only": "Exam only", "continuous": "Continuous"})),
            ui.column(4, ui.input_select("grading_grading_method", "Grading method",
                                         {"absolute": "Absolute", "relative": "Relative"})),
            ui.column(4, ui.input_select("grading_distribution", "Distribution",
                                         {"beta": "Beta", "normal": "Normal", "uniform": "Uniform"})),
        ),
        # Weights
        ui.h6("Weights", class_="text-secondary mt-3"),
        _slider_input("grading_midterm_weight", "midterm_weight", 0.40),
        _slider_input("grading_final_weight", "final_weight", 0.60),
        # Thresholds
        ui.h6("Thresholds", class_="text-secondary mt-3"),
        _slider_input("grading_grade_floor", "grade_floor", 0.45),
        _slider_input("grading_pass_threshold", "pass_threshold", 0.64),
        _slider_input("grading_distinction_threshold", "distinction_threshold", 0.73),
        # Dual hurdle
        ui.input_checkbox("grading_dual_hurdle", "Dual hurdle", value=False),
        ui.output_ui("dual_hurdle_thresholds"),
        # Other
        _slider_input("grading_late_penalty", "late_penalty", 0.05),
        _slider_input("grading_noise_std", "noise_std", 0.05),
        ui.input_select("grading_missing_policy", "Missing policy",
                        {"zero": "Zero", "redistribute": "Redistribute"}),
        value="grading",
        icon=ui.tags.i(class_="bi bi-mortarboard"),
    )


def _engine_group(group_name: str, field_names: list[tuple[str, float]]) -> ui.Tag:
    """Render a sub-group of EngineConfig fields."""
    inputs = []
    for field_id, default_val in field_names:
        clean_name = field_id.removeprefix("engine_")
        inputs.append(
            ui.row(
                ui.column(7, ui.tags.label(clean_name, class_="text-secondary",
                                           style="font-size:11px;font-family:'JetBrains Mono',monospace;")),
                ui.column(5, ui.input_numeric(field_id, None, value=default_val, step=0.001,
                                              width="100%")),
                class_="mb-1",
            )
        )
    return ui.div(
        ui.h6(group_name, class_="text-secondary mt-2", style="font-size:12px;"),
        *inputs,
    )


def engine_config_panel() -> ui.Tag:
    """EngineConfig — 70 constants behind a locked gate."""
    from dataclasses import fields as dc_fields
    from ...simulation.engine_config import EngineConfig

    ec = EngineConfig()
    groups: dict[str, list[tuple[str, float]]] = {}
    for f in dc_fields(ec):
        name = f.name
        fid = f"engine_{name}"
        val = getattr(ec, name)
        if "LOGIN" in name:
            g = "Login"
        elif "FORUM" in name:
            g = "Forum"
        elif "ASSIGN" in name and "MISSED" not in name:
            g = "Assignment Quality"
        elif "EXAM" in name:
            g = "Exam Quality"
        elif "ENGAGE" in name or "DECAY" in name or "CLIP" in name:
            g = "Engagement"
        elif "LIVE" in name:
            g = "Live Sessions"
        elif any(k in name for k in ("TINTO", "SDT", "CB", "MISSED", "STREAK")):
            g = "Theory Weights"
        elif "QUALITY" in name or "INST" in name:
            g = "Quality Thresholds"
        else:
            g = "Other"
        groups.setdefault(g, []).append((fid, val))

    sub_groups = [_engine_group(g, fs) for g, fs in groups.items()]

    return ui.accordion_panel(
        "EngineConfig (Advanced)",
        ui.div(
            ui.tags.i(class_="bi bi-shield-lock me-2"),
            "70 frozen engine constants. Edit with caution.",
            class_="text-secondary mb-3",
            style="font-size:12px;",
        ),
        *sub_groups,
        value="engine",
        icon=ui.tags.i(class_="bi bi-sliders"),
    )


def config_accordion() -> ui.Tag:
    """Full configuration accordion with all panels."""
    return ui.accordion(
        pipeline_controls(),
        persona_config_panel(),
        institutional_config_panel(),
        grading_config_panel(),
        engine_config_panel(),
        id="config_accordion",
        open=["pipeline", "persona"],
        multiple=True,
    )
