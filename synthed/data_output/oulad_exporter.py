"""
OuladExporter: Export simulation data in OULAD-compatible 7-table format.

Produces CSV files matching the Open University Learning Analytics Dataset
schema for drop-in compatibility with EDM research pipelines.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .oulad_mappings import (
    COURSES_COLUMNS, ASSESSMENTS_COLUMNS, VLE_COLUMNS,
    STUDENT_INFO_COLUMNS, STUDENT_REGISTRATION_COLUMNS,
    STUDENT_ASSESSMENT_COLUMNS, STUDENT_VLE_COLUMNS,
    semester_to_presentation, age_to_band, gender_to_oulad,
    education_to_oulad, select_region, select_imd_band,
    map_final_result, map_activity_type, click_heuristic,
    student_id_to_int,
)

if TYPE_CHECKING:
    from ..agents.persona import StudentPersona
    from ..simulation.engine import InteractionRecord, SimulationState
    from ..simulation.environment import ODLEnvironment

logger = logging.getLogger(__name__)


class OuladExporter:
    """Export simulation data in OULAD-compatible 7-table format."""

    def __init__(self, output_dir: str, seed: int = 42):
        self.output_dir = Path(output_dir) / "oulad"
        self.rng = np.random.default_rng(seed)

    def export_all(
        self,
        students: list[StudentPersona],
        records: list[InteractionRecord],
        states: dict[str, SimulationState],
        environment: ODLEnvironment,
    ) -> dict[str, str]:
        """Export all 7 OULAD tables. Returns dict of table_name -> filepath."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        presentation = semester_to_presentation(environment.semester_name)

        # Build catalogs (assessment IDs, VLE site IDs)
        assessment_catalog = self._build_assessment_catalog(environment, presentation)
        vle_catalog = self._build_vle_catalog(environment, presentation)

        # Build student ID map (UUIDv7 -> integer)
        id_map = {s.id: student_id_to_int(s.display_id) for s in students}

        paths = {}
        paths["courses"] = self._export_courses(environment, presentation)
        paths["assessments"] = self._export_assessments(assessment_catalog)
        paths["vle"] = self._export_vle(vle_catalog)
        paths["studentInfo"] = self._export_student_info(
            students, states, environment, presentation, id_map,
        )
        paths["studentRegistration"] = self._export_student_registration(
            students, states, environment, presentation, id_map,
        )
        paths["studentAssessment"] = self._export_student_assessment(
            records, assessment_catalog, id_map,
        )
        paths["studentVle"] = self._export_student_vle(
            records, vle_catalog, presentation, id_map,
        )

        logger.info("OULAD export: 7 tables written to %s", self.output_dir)
        return paths

    # -----------------------------------------
    # Catalog builders
    # -----------------------------------------

    def _build_assessment_catalog(
        self, env: ODLEnvironment, presentation: str,
    ) -> list[dict]:
        """Build assessment catalog with unique IDs for each assessment."""
        catalog = []
        assessment_id = 1
        for course in env.courses:
            # TMA assessments (assignments)
            n_assignments = len(course.assignment_weeks)
            tma_weight = round(100 / n_assignments) if n_assignments > 0 else 0
            for i, week in enumerate(course.assignment_weeks):
                catalog.append({
                    "code_module": course.id,
                    "code_presentation": presentation,
                    "id_assessment": assessment_id,
                    "assessment_type": "TMA",
                    "date": (week - 1) * 7,
                    "weight": tma_weight,
                    "_week": week,
                    "_type": "assignment_submit",
                })
                assessment_id += 1
            # Midterm as TMA (if distinct from final)
            if course.midterm_week != course.final_week:
                catalog.append({
                    "code_module": course.id,
                    "code_presentation": presentation,
                    "id_assessment": assessment_id,
                    "assessment_type": "TMA",
                    "date": (course.midterm_week - 1) * 7,
                    "weight": 0,  # midterm often separate from TMA weights
                    "_week": course.midterm_week,
                    "_type": "exam",
                })
                assessment_id += 1
            # Final exam
            catalog.append({
                "code_module": course.id,
                "code_presentation": presentation,
                "id_assessment": assessment_id,
                "assessment_type": "Exam",
                "date": "",  # OULAD convention: final exam date often empty
                "weight": 100,
                "_week": course.final_week,
                "_type": "exam",
            })
            assessment_id += 1
        return catalog

    def _build_vle_catalog(
        self, env: ODLEnvironment, presentation: str,
    ) -> list[dict]:
        """Build VLE material catalog with unique site IDs."""
        catalog = []
        site_id = 1
        for course in env.courses:
            # One VLE entry per interaction type per course
            activity_types = ["homepage", "forumng", "oucontent", "resource", "subpage"]
            if course.has_live_sessions:
                activity_types.append("oucollaborate")
            for activity in activity_types:
                catalog.append({
                    "id_site": site_id,
                    "code_module": course.id,
                    "code_presentation": presentation,
                    "activity_type": activity,
                    "week_from": 1,
                    "week_to": env.total_weeks,
                })
                site_id += 1
        return catalog

    # -----------------------------------------
    # Export methods (one per OULAD table)
    # -----------------------------------------

    def _export_courses(self, env: ODLEnvironment, presentation: str) -> str:
        filepath = self.output_dir / "courses.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COURSES_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for course in env.courses:
                writer.writerow({
                    "code_module": course.id,
                    "code_presentation": presentation,
                    "module_presentation_length": env.total_weeks * 7,
                })
        return str(filepath)

    def _export_assessments(self, catalog: list[dict]) -> str:
        filepath = self.output_dir / "assessments.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ASSESSMENTS_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for entry in catalog:
                writer.writerow({
                    "code_module": entry["code_module"],
                    "code_presentation": entry["code_presentation"],
                    "id_assessment": entry["id_assessment"],
                    "assessment_type": entry["assessment_type"],
                    "date": entry["date"],
                    "weight": entry["weight"],
                })
        return str(filepath)

    def _export_vle(self, catalog: list[dict]) -> str:
        filepath = self.output_dir / "vle.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=VLE_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for entry in catalog:
                writer.writerow(entry)
        return str(filepath)

    def _export_student_info(
        self,
        students: list[StudentPersona],
        states: dict[str, SimulationState],
        env: ODLEnvironment,
        presentation: str,
        id_map: dict[str, int],
    ) -> str:
        filepath = self.output_dir / "studentInfo.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=STUDENT_INFO_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for student in students:
                state = states.get(student.id)
                if state is None:
                    continue
                student_int_id = id_map.get(student.id, 0)
                region = select_region(self.rng)
                imd_band = select_imd_band(self.rng, student.socioeconomic_level)
                final_result = map_final_result(
                    state.has_dropped_out, state.withdrawal_reason,
                    state.cumulative_gpa, state.gpa_count,
                )
                disability = "Y" if student.disability_severity > 0 else "N"
                # One row per (student, course) -- OULAD convention
                for course in env.courses:
                    writer.writerow({
                        "code_module": course.id,
                        "code_presentation": presentation,
                        "id_student": student_int_id,
                        "gender": gender_to_oulad(student.gender),
                        "region": region,
                        "highest_education": education_to_oulad(student.prior_education_level),
                        "imd_band": imd_band,
                        "age_band": age_to_band(student.age),
                        "num_of_prev_attempts": 0,
                        "studied_credits": student.enrolled_courses * 30,
                        "disability": disability,
                        "final_result": final_result,
                    })
        return str(filepath)

    def _export_student_registration(
        self,
        students: list[StudentPersona],
        states: dict[str, SimulationState],
        env: ODLEnvironment,
        presentation: str,
        id_map: dict[str, int],
    ) -> str:
        filepath = self.output_dir / "studentRegistration.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=STUDENT_REGISTRATION_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for student in students:
                state = states.get(student.id)
                if state is None:
                    continue
                student_int_id = id_map.get(student.id, 0)
                reg_date = int(self.rng.integers(-180, -10))
                unreg_date = ""
                if state.has_dropped_out and state.dropout_week is not None:
                    unreg_date = state.dropout_week * 7
                elif state.withdrawal_reason is not None and state.dropout_week is not None:
                    unreg_date = state.dropout_week * 7
                for course in env.courses:
                    writer.writerow({
                        "code_module": course.id,
                        "code_presentation": presentation,
                        "id_student": student_int_id,
                        "date_registration": reg_date,
                        "date_unregistration": unreg_date,
                    })
        return str(filepath)

    def _export_student_assessment(
        self,
        records: list[InteractionRecord],
        assessment_catalog: list[dict],
        id_map: dict[str, int],
    ) -> str:
        """Export graded interactions (assignments, exams) to studentAssessment."""
        # Build lookup: (course_id, week, type) -> id_assessment
        assessment_lookup: dict[tuple[str, int, str], int] = {}
        for entry in assessment_catalog:
            key = (entry["code_module"], entry["_week"], entry["_type"])
            assessment_lookup[key] = entry["id_assessment"]

        filepath = self.output_dir / "studentAssessment.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=STUDENT_ASSESSMENT_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for record in records:
                if record.interaction_type not in ("assignment_submit", "exam"):
                    continue
                key = (record.course_id, record.week, record.interaction_type)
                assessment_id = assessment_lookup.get(key)
                if assessment_id is None:
                    continue  # No matching assessment in catalog
                student_int_id = id_map.get(record.student_id, 0)
                # date_submitted: days since presentation start
                day_offset = int(record.timestamp_offset_hours / 24) if record.timestamp_offset_hours else 0
                date_submitted = (record.week - 1) * 7 + day_offset
                score = int(round(record.quality_score * 100)) if record.quality_score else 0
                writer.writerow({
                    "id_assessment": assessment_id,
                    "id_student": student_int_id,
                    "date_submitted": max(0, date_submitted),
                    "is_banked": 0,
                    "score": min(100, max(0, score)),
                })
        return str(filepath)

    def _export_student_vle(
        self,
        records: list[InteractionRecord],
        vle_catalog: list[dict],
        presentation: str,
        id_map: dict[str, int],
    ) -> str:
        """Export non-graded interactions (logins, forum, live sessions) to studentVle."""
        # Build lookup: (course_id, activity_type) -> id_site
        site_lookup: dict[tuple[str, str], int] = {}
        for entry in vle_catalog:
            key = (entry["code_module"], entry["activity_type"])
            if key not in site_lookup:  # first match wins
                site_lookup[key] = entry["id_site"]

        filepath = self.output_dir / "studentVle.csv"
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=STUDENT_VLE_COLUMNS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for record in records:
                activity = map_activity_type(record.interaction_type)
                if activity is None:
                    continue  # assignment/exam goes to studentAssessment
                site_key = (record.course_id, activity)
                site_id = site_lookup.get(site_key)
                if site_id is None:
                    continue
                student_int_id = id_map.get(record.student_id, 0)
                day_offset = int(record.timestamp_offset_hours / 24) if record.timestamp_offset_hours else 0
                date = (record.week - 1) * 7 + day_offset
                clicks = click_heuristic(
                    record.interaction_type,
                    record.duration_minutes or 0,
                    record.metadata or {},
                )
                writer.writerow({
                    "code_module": record.course_id,
                    "code_presentation": presentation,
                    "id_student": student_int_id,
                    "id_site": site_id,
                    "date": max(0, date),
                    "sum_click": clicks,
                })
        return str(filepath)
