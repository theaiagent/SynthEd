"""
ODLEnvironment: Simulated Open and Distance Learning environment.

Models the structural elements of an ODL institution: courses, weekly
schedule, LMS interactions, forums, assignments, and examinations.
This is the "TinyWorld" equivalent for educational simulation.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


def _default_semester_name() -> str:
    now = datetime.date.today()
    month = now.month
    year = now.year
    if month >= 8:
        return f"Fall {year}"
    elif month >= 6:
        return f"Summer {year}"
    else:
        return f"Spring {year}"


@dataclass
class Course:
    """A single course in the ODL program."""
    id: str
    name: str
    difficulty: float = 0.5  # 0-1
    weekly_workload_hours: float = 5.0
    has_forum: bool = True
    has_live_sessions: bool = False
    num_assignments: int = 4
    midterm_week: int = 7
    final_week: int = 14
    assignment_weeks: list[int] = field(default_factory=lambda: [3, 6, 10, 13])

    # Moore (1993): Transactional Distance Theory
    structure_level: float = 0.5  # 0-1; rigidity of course pacing/requirements
    dialogue_frequency: float = 0.3  # 0-1; instructor-initiated communication rate
    instructor_responsiveness: float = 0.5  # 0-1; speed/quality of instructor replies


@dataclass
class ODLEnvironment:
    """
    Simulated ODL environment representing one academic semester.

    Defines the temporal structure (weeks), available courses,
    interaction channels, and event schedule.
    """
    semester_name: str = field(default_factory=_default_semester_name)
    total_weeks: int = 14
    courses: list[Course] = field(default_factory=list)

    # Events that occur at specific weeks (week -> event description)
    scheduled_events: dict[int, str] = field(default_factory=dict)

    # Positive events that counter negative environmental pressure
    positive_events: dict[int, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.courses:
            self.courses = self._default_courses()
        if not self.scheduled_events:
            self.scheduled_events = self._default_events()
        if not self.positive_events:
            self.positive_events = self._default_positive_events()
        self._course_index: dict[str, Course] = {c.id: c for c in self.courses}

    def _default_courses(self) -> list[Course]:
        """Generate a default set of ODL courses."""
        return [
            Course(
                id="CS101", name="Introduction to Computer Science",
                difficulty=0.4, weekly_workload_hours=5, has_forum=True,
                has_live_sessions=True, num_assignments=4,
                structure_level=0.6, dialogue_frequency=0.5, instructor_responsiveness=0.6,
            ),
            Course(
                id="MATH201", name="Statistics for Social Sciences",
                difficulty=0.6, weekly_workload_hours=6, has_forum=True,
                has_live_sessions=False, num_assignments=5,
                assignment_weeks=[2, 5, 8, 11, 13],
                structure_level=0.7, dialogue_frequency=0.2, instructor_responsiveness=0.4,
            ),
            Course(
                id="EDU301", name="Foundations of Distance Education",
                difficulty=0.3, weekly_workload_hours=4, has_forum=True,
                has_live_sessions=True, num_assignments=3,
                assignment_weeks=[4, 9, 13],
                structure_level=0.3, dialogue_frequency=0.6, instructor_responsiveness=0.7,
            ),
            Course(
                id="PSY202", name="Educational Psychology",
                difficulty=0.5, weekly_workload_hours=5, has_forum=True,
                has_live_sessions=False, num_assignments=4,
                structure_level=0.5, dialogue_frequency=0.3, instructor_responsiveness=0.5,
            ),
        ]

    def _default_events(self) -> dict[int, str]:
        return {
            1: "semester_start",
            3: "first_assignment_deadline",
            7: "midterm_exams",
            10: "registration_withdrawal_deadline",
            13: "final_assignment_deadline",
            14: "final_exams",
        }

    def _default_positive_events(self) -> dict[int, str]:
        """Positive events scaled to semester length."""
        w = self.total_weeks
        return {
            1: "orientation_welcome",
            max(1, int(w * 0.25)): "financial_aid_disbursement",
            max(1, int(w * 0.50)): "semester_break",
            max(1, int(w * 0.75)): "peer_study_group",
        }

    def get_week_context(self, week: int) -> dict:
        """Get the environmental context for a given week."""
        active_assignments = []
        for course in self.courses:
            if week in course.assignment_weeks:
                active_assignments.append(course.id)

        is_exam_week = any(
            week == c.midterm_week or week == c.final_week
            for c in self.courses
        )

        return {
            "week": week,
            "semester_progress": week / self.total_weeks,
            "event": self.scheduled_events.get(week, "regular_week"),
            "active_assignments": active_assignments,
            "is_exam_week": is_exam_week,
            "total_workload_hours": sum(c.weekly_workload_hours for c in self.courses),
            "lms_available": True,  # Simplified; could model outages
            "positive_event": self.positive_events.get(week),
        }

    def get_course_by_id(self, course_id: str) -> Course | None:
        return self._course_index.get(course_id)
