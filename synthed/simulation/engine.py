"""
SimulationEngine: Week-by-week simulation of student behavior in an ODL environment.

Combines persona-driven behavioral probabilities with environmental context
to generate realistic interaction traces. Supports both rule-based (fast)
and LLM-augmented (rich) simulation modes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..agents.persona import StudentPersona
from .environment import ODLEnvironment
from ..utils.llm import LLMClient


@dataclass
class InteractionRecord:
    """A single interaction event in the simulation."""
    student_id: str
    week: int
    course_id: str
    interaction_type: str  # lms_login, forum_post, forum_read, assignment_submit, live_session, exam
    timestamp_offset_hours: float = 0.0  # Offset within the week
    duration_minutes: float = 0.0
    quality_score: float = 0.0  # 0-1, for assignments/exams
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationState:
    """Tracks the evolving state of a student across the simulation."""
    student_id: str
    current_engagement: float = 0.5  # Dynamic, changes over time
    cumulative_gpa: float = 0.0
    courses_active: list[str] = field(default_factory=list)
    courses_dropped: list[str] = field(default_factory=list)
    has_dropped_out: bool = False
    dropout_week: int | None = None
    weekly_engagement_history: list[float] = field(default_factory=list)


class SimulationEngine:
    """
    Orchestrates the week-by-week simulation of student populations.

    Two modes:
    - Rule-based (default): Fast, deterministic given seed. Uses persona
      attributes and environmental context to compute behavioral probabilities.
    - LLM-augmented: Slower, richer. Uses LLM to generate nuanced decisions
      and natural language artifacts (forum posts, etc.).
    """

    def __init__(
        self,
        environment: ODLEnvironment,
        llm_client: LLMClient | None = None,
        seed: int = 42,
        mode: str = "rule_based",  # "rule_based" or "llm_augmented"
    ):
        self.env = environment
        self.llm = llm_client
        self.rng = np.random.default_rng(seed)
        self.mode = mode
        random.seed(seed)

    def run(
        self,
        students: list[StudentPersona],
        weeks: int | None = None,
    ) -> tuple[list[InteractionRecord], dict[str, SimulationState]]:
        """
        Run the full simulation.

        Returns:
            - All interaction records
            - Final state for each student
        """
        weeks = weeks or self.env.total_weeks
        all_records: list[InteractionRecord] = []
        states: dict[str, SimulationState] = {}

        # Initialize states
        for student in students:
            course_ids = [c.id for c in self.env.courses[:student.enrolled_courses]]
            states[student.id] = SimulationState(
                student_id=student.id,
                current_engagement=student.base_engagement_probability,
                courses_active=course_ids,
            )

        # Week-by-week simulation
        for week in range(1, weeks + 1):
            week_context = self.env.get_week_context(week)

            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue

                # Simulate this student's week
                week_records = self._simulate_student_week(
                    student, state, week, week_context
                )
                all_records.extend(week_records)

                # Update engagement based on week's activity
                self._update_engagement(student, state, week, week_context, week_records)

                # Check for dropout
                if self._check_dropout(student, state, week):
                    state.has_dropped_out = True
                    state.dropout_week = week

        return all_records, states

    def _simulate_student_week(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        context: dict,
    ) -> list[InteractionRecord]:
        """Generate interaction records for one student in one week."""
        records = []
        engagement = state.current_engagement

        for course_id in state.courses_active:
            course = self.env.get_course_by_id(course_id)
            if not course:
                continue

            # --- LMS Logins ---
            # Higher engagement → more logins per week
            n_logins = max(0, int(self.rng.poisson(engagement * 5)))
            for login_idx in range(n_logins):
                # Time distribution: working students log in evenings/weekends
                if student.is_employed:
                    hour_offset = float(self.rng.choice(
                        [*range(18, 24), *range(0, 2)],  # Evening/night
                    ) + self.rng.uniform(0, 1))
                else:
                    hour_offset = float(self.rng.uniform(8, 22))

                day_offset = self.rng.integers(0, 7)
                duration = float(max(5, self.rng.normal(30 * engagement, 15)))

                records.append(InteractionRecord(
                    student_id=student.id,
                    week=week,
                    course_id=course_id,
                    interaction_type="lms_login",
                    timestamp_offset_hours=day_offset * 24 + hour_offset,
                    duration_minutes=round(duration, 1),
                    metadata={"device": student.device_type},
                ))

            # --- Forum Activity ---
            if course.has_forum:
                # Read probability higher than post probability
                if self.rng.random() < engagement * 0.7:
                    records.append(InteractionRecord(
                        student_id=student.id,
                        week=week,
                        course_id=course_id,
                        interaction_type="forum_read",
                        duration_minutes=round(float(self.rng.exponential(10)), 1),
                    ))

                # Posting: extraversion and engagement both matter
                post_prob = engagement * 0.3 * (0.5 + 0.5 * student.personality.extraversion)
                if self.rng.random() < post_prob:
                    records.append(InteractionRecord(
                        student_id=student.id,
                        week=week,
                        course_id=course_id,
                        interaction_type="forum_post",
                        duration_minutes=round(float(self.rng.normal(15, 5)), 1),
                        metadata={"post_length": int(self.rng.normal(80, 30))},
                    ))

            # --- Assignment Submission ---
            if week in course.assignment_weeks:
                submit_prob = engagement * (0.5 + 0.5 * student.personality.conscientiousness)
                submitted = self.rng.random() < submit_prob

                if submitted:
                    # Quality depends on engagement, ability, and effort
                    base_quality = (
                        0.3 * (student.prior_gpa / 4.0)
                        + 0.3 * engagement
                        + 0.2 * student.self_efficacy
                        + 0.2 * self.rng.normal(0.5, 0.15)
                    )
                    quality = float(np.clip(base_quality, 0.0, 1.0))

                    # Late submission probability
                    is_late = self.rng.random() > student.personality.conscientiousness

                    records.append(InteractionRecord(
                        student_id=student.id,
                        week=week,
                        course_id=course_id,
                        interaction_type="assignment_submit",
                        quality_score=round(quality, 2),
                        metadata={
                            "is_late": is_late,
                            "assignment_week": week,
                        },
                    ))

                    student.add_memory(week, "assignment",
                                       f"Submitted {'late ' if is_late else ''}assignment for {course_id} (quality: {quality:.0%})",
                                       impact=quality - 0.5)
                else:
                    student.add_memory(week, "missed_assignment",
                                       f"Missed assignment deadline for {course_id}",
                                       impact=-0.3)

            # --- Live Sessions ---
            if course.has_live_sessions:
                attend_prob = engagement * 0.6
                if student.is_employed:
                    attend_prob *= 0.5  # Working students attend less
                if self.rng.random() < attend_prob:
                    records.append(InteractionRecord(
                        student_id=student.id,
                        week=week,
                        course_id=course_id,
                        interaction_type="live_session",
                        duration_minutes=round(float(self.rng.normal(60, 10)), 1),
                    ))

            # --- Exams ---
            if week == course.midterm_week or week == course.final_week:
                exam_type = "midterm" if week == course.midterm_week else "final"
                take_prob = 0.95 if engagement > 0.3 else engagement * 2

                if self.rng.random() < take_prob:
                    exam_quality = float(np.clip(
                        0.25 * (student.prior_gpa / 4.0)
                        + 0.25 * engagement
                        + 0.25 * student.self_efficacy
                        + 0.15 * student.personality.conscientiousness
                        + 0.10 * self.rng.normal(0.5, 0.2),
                        0.0, 1.0
                    ))
                    records.append(InteractionRecord(
                        student_id=student.id,
                        week=week,
                        course_id=course_id,
                        interaction_type="exam",
                        quality_score=round(exam_quality, 2),
                        metadata={"exam_type": exam_type},
                    ))
                    student.add_memory(week, "exam",
                                       f"{exam_type.title()} exam for {course_id} (score: {exam_quality:.0%})",
                                       impact=exam_quality - 0.5)

        return records

    def _update_engagement(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
        context: dict,
        records: list[InteractionRecord],
    ):
        """Update student engagement based on week's events and outcomes."""
        # Base engagement drift
        engagement = state.current_engagement

        # Activity effect: doing things reinforces engagement
        activity_count = len(records)
        if activity_count > 0:
            engagement += 0.01 * min(activity_count / 5, 1.0)
        else:
            engagement -= 0.08  # Inactivity decay (stronger)

        # Assignment/exam outcomes affect motivation
        for r in records:
            if r.interaction_type in ("assignment_submit", "exam"):
                if r.quality_score > 0.7:
                    engagement += 0.03  # Success boost
                elif r.quality_score < 0.3:
                    engagement -= 0.04  # Failure discouragement

        # Missed assignments erode engagement
        for course_id in state.courses_active:
            course = self.env.get_course_by_id(course_id)
            if course and week in course.assignment_weeks:
                submitted = any(
                    r.course_id == course_id and r.interaction_type == "assignment_submit"
                    for r in records
                )
                if not submitted:
                    engagement -= 0.06

        # Stress effect during exam weeks
        if context.get("is_exam_week"):
            engagement -= student.personality.neuroticism * 0.05

        # Work-life balance pressure
        if student.is_employed and student.weekly_work_hours > 40:
            engagement -= 0.02
        if student.has_family_responsibilities:
            engagement -= 0.01

        # Personality resilience
        engagement += student.personality.conscientiousness * 0.01

        # Clamp and store
        state.current_engagement = float(np.clip(engagement, 0.01, 0.99))
        state.weekly_engagement_history.append(state.current_engagement)

    def _check_dropout(
        self,
        student: StudentPersona,
        state: SimulationState,
        week: int,
    ) -> bool:
        """Determine if a student drops out this week."""
        # Engagement threshold for dropout consideration
        if state.current_engagement > 0.45:
            return False

        # Dropout probability: combines base risk with engagement decay
        base_prob = student.base_dropout_risk
        engagement_factor = (0.45 - state.current_engagement) / 0.45  # 0 at 0.45, 1 at 0
        weekly_prob = base_prob * engagement_factor * 0.25

        # Engagement trend: declining trend increases risk
        history = state.weekly_engagement_history
        if len(history) >= 3:
            recent_trend = history[-1] - history[-3]
            if recent_trend < -0.1:
                weekly_prob *= 1.5  # Accelerating decline

        # Early weeks: lower dropout (students are still trying)
        if week <= 2:
            weekly_prob *= 0.2
        elif week <= 4:
            weekly_prob *= 0.6
        # Near withdrawal deadline: spike
        elif week == 10:
            weekly_prob *= 2.5
        # Late semester: some give up before finals
        elif week >= 12:
            weekly_prob *= 1.8

        return bool(self.rng.random() < weekly_prob)

    def summary_statistics(
        self,
        states: dict[str, SimulationState],
    ) -> dict[str, Any]:
        """Compute summary statistics from simulation results."""
        total = len(states)
        dropouts = sum(1 for s in states.values() if s.has_dropped_out)

        dropout_weeks = [s.dropout_week for s in states.values() if s.dropout_week]
        final_engagements = [
            s.weekly_engagement_history[-1] if s.weekly_engagement_history else 0
            for s in states.values() if not s.has_dropped_out
        ]

        return {
            "total_students": total,
            "dropout_count": dropouts,
            "dropout_rate": dropouts / total if total > 0 else 0,
            "mean_dropout_week": float(np.mean(dropout_weeks)) if dropout_weeks else None,
            "std_dropout_week": float(np.std(dropout_weeks)) if dropout_weeks else None,
            "mean_final_engagement": float(np.mean(final_engagements)) if final_engagements else None,
            "retained_students": total - dropouts,
        }
