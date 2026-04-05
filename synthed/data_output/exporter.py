"""
DataExporter: Converts simulation records into research-ready datasets.

Exports are structured around four theoretical factor clusters (Rovai, 2003)
plus Bäulke et al.'s dropout phase model for outcome tracking.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..agents.persona import StudentPersona
from ..simulation.engine import InteractionRecord, SimulationState
from ..simulation.social_network import SocialNetwork


class DataExporter:
    """
    Export simulation outputs to research-ready CSV files.

    Generates four datasets:
    1. students.csv — Full persona attributes organized by factor cluster
    2. interactions.csv — Timestamped LMS interaction logs
    3. outcomes.csv — Per-student outcome (dropout phase, engagement trend)
    4. weekly_engagement.csv — Week-by-week engagement trajectories
    """

    def __init__(self, output_dir: str | None = "./output"):
        self.output_dir = Path(output_dir) if output_dir is not None else None

    def _ensure_output_dir(self) -> None:
        """Create the output directory if it does not yet exist."""
        if self.output_dir is None:
            raise RuntimeError("DataExporter.output_dir is None — cannot write files")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self, students: list[StudentPersona],
        records: list[InteractionRecord],
        states: dict[str, SimulationState],
        network: SocialNetwork | None = None,
    ) -> dict[str, str]:
        self._ensure_output_dir()
        paths = {}
        display_id_map = {s.id: s.display_id for s in students}
        paths["students"] = self.export_students(students)
        paths["interactions"] = self.export_interactions(records, display_id_map=display_id_map)
        paths["outcomes"] = self.export_outcomes(students, states, network)
        paths["weekly_engagement"] = self.export_weekly_engagement(students, states)
        return paths

    def export_students(self, students: list[StudentPersona]) -> str:
        """Export initial/baseline persona attributes (pre-simulation values).

        Note: Values like academic_integration, social_integration, and
        perceived_cost_benefit reflect the student's initial state before
        simulation. For evolved/final values, see outcomes.csv.
        """
        filepath = self.output_dir / "students.csv"
        fieldnames = [
            # Identity
            "student_id", "display_id", "name", "age", "gender",
            # Big Five
            "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism",
            # Cluster 1: Student Characteristics (Tinto, Kember)
            "prior_gpa", "prior_education_level", "years_since_last_education",
            "enrolled_courses", "goal_commitment", "ode_beliefs",
            "motivation_type", "goal_orientation",
            # Cluster 2: Student Skills (Rovai, Moore)
            "digital_literacy", "self_regulation", "time_management",
            "learner_autonomy",
            "academic_reading_writing", "has_reliable_internet", "disability_severity",
            "device_type",
            "preferred_learning_style",
            # Cluster 3: External Factors (Bean & Metzner)
            "is_employed", "weekly_work_hours", "has_family_responsibilities",
            "financial_stress", "socioeconomic_level", "perceived_cost_benefit",
            # Cluster 4: Internal Factors (Tinto, Rovai)
            "academic_integration", "social_integration",
            "institutional_support_access", "self_efficacy",
            # Derived
            "base_engagement_probability", "base_dropout_risk",
            # LLM-generated (optional)
            "backstory",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in students:
                row = {
                    "student_id": s.id, "display_id": s.display_id,
                    "name": s.name, "age": s.age, "gender": s.gender,
                    "openness": round(s.personality.openness, 3),
                    "conscientiousness": round(s.personality.conscientiousness, 3),
                    "extraversion": round(s.personality.extraversion, 3),
                    "agreeableness": round(s.personality.agreeableness, 3),
                    "neuroticism": round(s.personality.neuroticism, 3),
                    "prior_gpa": s.prior_gpa, "prior_education_level": s.prior_education_level,
                    "years_since_last_education": s.years_since_last_education,
                    "enrolled_courses": s.enrolled_courses,
                    "goal_commitment": s.goal_commitment, "ode_beliefs": s.ode_beliefs,
                    "motivation_type": s.motivation_type, "goal_orientation": s.goal_orientation,
                    "digital_literacy": s.digital_literacy, "self_regulation": s.self_regulation,
                    "time_management": s.time_management,
                    "learner_autonomy": round(s.learner_autonomy, 3),
                    "academic_reading_writing": s.academic_reading_writing,
                    "has_reliable_internet": int(s.has_reliable_internet),
                    "disability_severity": s.disability_severity,
                    "device_type": s.device_type,
                    "preferred_learning_style": s.preferred_learning_style,
                    "is_employed": int(s.is_employed),
                    "weekly_work_hours": s.weekly_work_hours,
                    "has_family_responsibilities": int(s.has_family_responsibilities),
                    "financial_stress": s.financial_stress,
                    "socioeconomic_level": s.socioeconomic_level,
                    "perceived_cost_benefit": s.perceived_cost_benefit,
                    "academic_integration": s.academic_integration,
                    "social_integration": s.social_integration,
                    "institutional_support_access": s.institutional_support_access,
                    "self_efficacy": s.self_efficacy,
                    "base_engagement_probability": round(s.base_engagement_probability, 3),
                    "base_dropout_risk": round(s.base_dropout_risk, 3),
                    "backstory": s.backstory or "",
                }
                writer.writerow(row)
        return str(filepath)

    def export_interactions(
        self, records: list[InteractionRecord],
        display_id_map: dict[str, str] | None = None,
    ) -> str:
        filepath = self.output_dir / "interactions.csv"
        _display_map = display_id_map or {}
        fieldnames = [
            "student_id", "display_id", "week", "course_id", "interaction_type",
            "timestamp_offset_hours", "duration_minutes", "quality_score",
            "device", "is_late", "exam_type", "post_length",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow({
                    "student_id": r.student_id,
                    "display_id": _display_map.get(r.student_id, ""),
                    "week": r.week,
                    "course_id": r.course_id, "interaction_type": r.interaction_type,
                    "timestamp_offset_hours": round(r.timestamp_offset_hours, 2),
                    "duration_minutes": r.duration_minutes,
                    "quality_score": r.quality_score if r.quality_score > 0 else "",
                    "device": r.metadata.get("device", ""),
                    "is_late": r.metadata.get("is_late", ""),
                    "exam_type": r.metadata.get("exam_type", ""),
                    "post_length": r.metadata.get("post_length", ""),
                })
        return str(filepath)

    def export_outcomes(
        self, students: list[StudentPersona], states: dict[str, SimulationState],
        network: SocialNetwork | None = None,
    ) -> str:
        filepath = self.output_dir / "outcomes.csv"
        fieldnames = [
            "student_id", "display_id", "has_dropped_out", "dropout_week", "withdrawal_reason", "final_dropout_phase",
            "final_engagement", "final_gpa", "final_academic_integration", "final_social_integration",
            "final_perceived_cost_benefit", "courses_active_count",
            "engagement_trend",
            # Garrison et al. (2000): Community of Inquiry
            "final_social_presence", "final_cognitive_presence", "final_teaching_presence",
            # Deci & Ryan (1985): Self-Determination Theory
            "final_motivation_type",
            "final_autonomy_need", "final_competence_need", "final_relatedness_need",
            # Gonzalez et al. (2025): Academic exhaustion
            "final_exhaustion_level",
            # Epstein & Axtell (1996): Network properties
            "network_degree",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for student in students:
                state = states.get(student.id)
                if not state:
                    continue
                history = state.weekly_engagement_history
                if len(history) >= 4:
                    q = len(history) // 4
                    diff = sum(history[-q:]) / q - sum(history[:q]) / q
                    trend = "positive" if diff > 0.05 else "negative" if diff < -0.05 else "stable"
                else:
                    trend = "unknown"
                writer.writerow({
                    "student_id": student.id,
                    "display_id": student.display_id,
                    "has_dropped_out": int(state.has_dropped_out),
                    "dropout_week": state.dropout_week or "",
                    "withdrawal_reason": state.withdrawal_reason or "",
                    "final_dropout_phase": state.dropout_phase,
                    "final_engagement": round(history[-1], 3) if history else "",
                    "final_gpa": round(state.cumulative_gpa, 2) if state.gpa_count > 0 else "",
                    "final_academic_integration": round(state.academic_integration, 3),
                    "final_social_integration": round(state.social_integration, 3),
                    "final_perceived_cost_benefit": round(state.perceived_cost_benefit, 3),
                    "courses_active_count": len(state.courses_active),
                    "engagement_trend": trend,
                    # CoI (Garrison et al., 2000)
                    "final_social_presence": round(state.coi_state.social_presence, 3),
                    "final_cognitive_presence": round(state.coi_state.cognitive_presence, 3),
                    "final_teaching_presence": round(state.coi_state.teaching_presence, 3),
                    # SDT (Deci & Ryan, 1985)
                    "final_motivation_type": state.current_motivation_type,
                    "final_autonomy_need": round(state.sdt_needs.autonomy, 3),
                    "final_competence_need": round(state.sdt_needs.competence, 3),
                    "final_relatedness_need": round(state.sdt_needs.relatedness, 3),
                    # Gonzalez et al. (2025)
                    "final_exhaustion_level": round(state.exhaustion.exhaustion_level, 3),
                    # Network (Epstein & Axtell, 1996)
                    "network_degree": network.get_degree(student.id) if network else 0,
                })
        return str(filepath)

    def export_weekly_engagement(
        self, students: list[StudentPersona], states: dict[str, SimulationState],
    ) -> str:
        filepath = self.output_dir / "weekly_engagement.csv"
        max_weeks = max((len(s.weekly_engagement_history) for s in states.values()), default=0)
        fieldnames = ["student_id", "display_id"] + [f"week_{w}" for w in range(1, max_weeks + 1)]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for student in students:
                state = states.get(student.id)
                if not state:
                    continue
                row = {"student_id": student.id, "display_id": student.display_id}
                for w, eng in enumerate(state.weekly_engagement_history, 1):
                    row[f"week_{w}"] = round(eng, 3)
                writer.writerow(row)
        return str(filepath)
