"""
DataExporter: Converts simulation records into research-ready datasets.

Exports interaction records and student states into CSV format,
structured for compatibility with common educational data mining tools.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..agents.persona import StudentPersona
from ..simulation.engine import InteractionRecord, SimulationState


class DataExporter:
    """
    Export simulation outputs to research-ready file formats.

    Generates three primary datasets:
    1. students.csv — Student demographics and persona attributes
    2. interactions.csv — Timestamped LMS interaction logs
    3. outcomes.csv — Per-student outcome summary (dropout, GPA, engagement)
    """

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self,
        students: list[StudentPersona],
        records: list[InteractionRecord],
        states: dict[str, SimulationState],
    ) -> dict[str, str]:
        """
        Export all datasets and return file paths.

        Returns:
            Dictionary mapping dataset name to file path.
        """
        paths = {}
        paths["students"] = self.export_students(students)
        paths["interactions"] = self.export_interactions(records)
        paths["outcomes"] = self.export_outcomes(students, states)
        paths["weekly_engagement"] = self.export_weekly_engagement(students, states)
        return paths

    def export_students(self, students: list[StudentPersona]) -> str:
        """Export student demographics and persona attributes."""
        filepath = self.output_dir / "students.csv"
        fieldnames = [
            "student_id", "name", "age", "gender",
            "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism",
            "is_employed", "weekly_work_hours", "has_family_responsibilities",
            "socioeconomic_level", "prior_gpa", "prior_education_level",
            "years_since_last_education", "enrolled_courses",
            "digital_literacy", "preferred_learning_style",
            "has_reliable_internet", "device_type",
            "motivation_type", "goal_orientation", "self_efficacy",
            "base_engagement_probability", "base_dropout_risk",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in students:
                row = {
                    "student_id": s.id,
                    "name": s.name,
                    "age": s.age,
                    "gender": s.gender,
                    "openness": round(s.personality.openness, 3),
                    "conscientiousness": round(s.personality.conscientiousness, 3),
                    "extraversion": round(s.personality.extraversion, 3),
                    "agreeableness": round(s.personality.agreeableness, 3),
                    "neuroticism": round(s.personality.neuroticism, 3),
                    "is_employed": int(s.is_employed),
                    "weekly_work_hours": s.weekly_work_hours,
                    "has_family_responsibilities": int(s.has_family_responsibilities),
                    "socioeconomic_level": s.socioeconomic_level,
                    "prior_gpa": s.prior_gpa,
                    "prior_education_level": s.prior_education_level,
                    "years_since_last_education": s.years_since_last_education,
                    "enrolled_courses": s.enrolled_courses,
                    "digital_literacy": s.digital_literacy,
                    "preferred_learning_style": s.preferred_learning_style,
                    "has_reliable_internet": int(s.has_reliable_internet),
                    "device_type": s.device_type,
                    "motivation_type": s.motivation_type,
                    "goal_orientation": s.goal_orientation,
                    "self_efficacy": s.self_efficacy,
                    "base_engagement_probability": round(s.base_engagement_probability, 3),
                    "base_dropout_risk": round(s.base_dropout_risk, 3),
                }
                writer.writerow(row)

        return str(filepath)

    def export_interactions(self, records: list[InteractionRecord]) -> str:
        """Export interaction logs as a timestamped event log."""
        filepath = self.output_dir / "interactions.csv"
        fieldnames = [
            "student_id", "week", "course_id", "interaction_type",
            "timestamp_offset_hours", "duration_minutes", "quality_score",
            "device", "is_late", "exam_type", "post_length",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                row = {
                    "student_id": r.student_id,
                    "week": r.week,
                    "course_id": r.course_id,
                    "interaction_type": r.interaction_type,
                    "timestamp_offset_hours": round(r.timestamp_offset_hours, 2),
                    "duration_minutes": r.duration_minutes,
                    "quality_score": r.quality_score if r.quality_score > 0 else "",
                    "device": r.metadata.get("device", ""),
                    "is_late": r.metadata.get("is_late", ""),
                    "exam_type": r.metadata.get("exam_type", ""),
                    "post_length": r.metadata.get("post_length", ""),
                }
                writer.writerow(row)

        return str(filepath)

    def export_outcomes(
        self,
        students: list[StudentPersona],
        states: dict[str, SimulationState],
    ) -> str:
        """Export per-student outcome summary."""
        filepath = self.output_dir / "outcomes.csv"
        fieldnames = [
            "student_id", "has_dropped_out", "dropout_week",
            "final_engagement", "courses_active_count", "courses_dropped_count",
            "engagement_trend",  # positive, negative, stable
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
                    first_quarter = sum(history[:len(history)//4]) / (len(history)//4)
                    last_quarter = sum(history[-len(history)//4:]) / (len(history)//4)
                    diff = last_quarter - first_quarter
                    trend = "positive" if diff > 0.05 else "negative" if diff < -0.05 else "stable"
                else:
                    trend = "unknown"

                row = {
                    "student_id": student.id,
                    "has_dropped_out": int(state.has_dropped_out),
                    "dropout_week": state.dropout_week or "",
                    "final_engagement": round(history[-1], 3) if history else "",
                    "courses_active_count": len(state.courses_active),
                    "courses_dropped_count": len(state.courses_dropped),
                    "engagement_trend": trend,
                }
                writer.writerow(row)

        return str(filepath)

    def export_weekly_engagement(
        self,
        students: list[StudentPersona],
        states: dict[str, SimulationState],
    ) -> str:
        """Export week-by-week engagement trajectories for all students."""
        filepath = self.output_dir / "weekly_engagement.csv"

        # Determine max weeks
        max_weeks = max(
            (len(s.weekly_engagement_history) for s in states.values()),
            default=0,
        )

        fieldnames = ["student_id"] + [f"week_{w}" for w in range(1, max_weeks + 1)]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for student in students:
                state = states.get(student.id)
                if not state:
                    continue
                row = {"student_id": student.id}
                for w, eng in enumerate(state.weekly_engagement_history, 1):
                    row[f"week_{w}"] = round(eng, 3)
                writer.writerow(row)

        return str(filepath)
