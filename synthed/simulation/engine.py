"""
SimulationEngine: Theory-grounded week-by-week simulation of ODL student behavior.

Engagement and dropout mechanics map to established theoretical frameworks:

- Tinto (1975): Academic/social integration drive institutional commitment
- Bean & Metzner (1985): Environmental pressures (work, family, finances)
  outweigh social integration for non-traditional/ODE students
- Kember (1989): Students perform ongoing cost-benefit analysis
- Rovai (2003): Accessibility and digital skills as persistence factors
- Bäulke et al.: Dropout as a phased self-regulatory process
  (committed → perceived misfit → rumination → info seeking → decision)
- Durkheim/Tinto: Social disconnection increases dropout risk
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
    timestamp_offset_hours: float = 0.0
    duration_minutes: float = 0.0
    quality_score: float = 0.0  # 0-1, for assignments/exams
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationState:
    """Tracks evolving state of a student across the simulation."""
    student_id: str
    current_engagement: float = 0.5
    academic_integration: float = 0.5  # Tinto: evolves with performance
    social_integration: float = 0.3  # Tinto: evolves with interaction
    perceived_cost_benefit: float = 0.6  # Kember: evolves with experience
    dropout_phase: int = 0  # Bäulke: 0–4
    cumulative_gpa: float = 0.0
    courses_active: list[str] = field(default_factory=list)
    courses_dropped: list[str] = field(default_factory=list)
    has_dropped_out: bool = False
    dropout_week: int | None = None
    weekly_engagement_history: list[float] = field(default_factory=list)
    missed_assignments_streak: int = 0  # Consecutive missed assignments


class SimulationEngine:
    """
    Week-by-week ODL simulation with theory-grounded mechanics.

    Engagement update incorporates:
    - Academic integration changes (Tinto) — driven by assignment/exam outcomes
    - Social integration changes (Tinto) — driven by forum activity
    - Environmental pressure (Bean & Metzner) — work/family stress
    - Self-regulation effects (Rovai/Bäulke) — consistency of study behavior
    - Cost-benefit recalculation (Kember) — updated after significant events

    Dropout follows Bäulke et al.'s phase model:
    - Phase 0 (Committed): No dropout risk
    - Phase 1 (Perceived Misfit): Low engagement triggers doubt
    - Phase 2 (Rumination): Declining trajectory, considering leaving
    - Phase 3 (Info Seeking): Very low engagement, actively considering exit
    - Phase 4 (Decision): Dropout occurs
    """

    def __init__(
        self,
        environment: ODLEnvironment,
        llm_client: LLMClient | None = None,
        seed: int = 42,
        mode: str = "rule_based",
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
        weeks = weeks or self.env.total_weeks
        all_records: list[InteractionRecord] = []
        states: dict[str, SimulationState] = {}

        for student in students:
            course_ids = [c.id for c in self.env.courses[:student.enrolled_courses]]
            states[student.id] = SimulationState(
                student_id=student.id,
                current_engagement=student.base_engagement_probability,
                academic_integration=student.academic_integration,
                social_integration=student.social_integration,
                perceived_cost_benefit=student.perceived_cost_benefit,
                courses_active=course_ids,
            )

        for week in range(1, weeks + 1):
            week_context = self.env.get_week_context(week)
            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue

                week_records = self._simulate_student_week(student, state, week, week_context)
                all_records.extend(week_records)
                self._update_integration(student, state, week, week_context, week_records)
                self._update_engagement(student, state, week, week_context, week_records)
                self._advance_dropout_phase(student, state, week)

                if state.dropout_phase >= 4:
                    state.has_dropped_out = True
                    state.dropout_week = week

        return all_records, states

    def _simulate_student_week(
        self, student: StudentPersona, state: SimulationState,
        week: int, context: dict,
    ) -> list[InteractionRecord]:
        records = []
        engagement = state.current_engagement

        for course_id in state.courses_active:
            course = self.env.get_course_by_id(course_id)
            if not course:
                continue

            # ── LMS Logins (Rovai: accessibility) ──
            login_rate = engagement * 5 * (0.5 + 0.5 * student.digital_literacy)
            n_logins = max(0, int(self.rng.poisson(login_rate)))
            for _ in range(n_logins):
                if student.is_employed:
                    hour = float(self.rng.choice([*range(18, 24), *range(0, 2)]) + self.rng.uniform(0, 1))
                else:
                    hour = float(self.rng.uniform(8, 22))
                day = self.rng.integers(0, 7)
                duration = float(max(5, self.rng.normal(25 * engagement, 12)))
                records.append(InteractionRecord(
                    student_id=student.id, week=week, course_id=course_id,
                    interaction_type="lms_login",
                    timestamp_offset_hours=day * 24 + hour,
                    duration_minutes=round(duration, 1),
                    metadata={"device": student.device_type},
                ))

            # ── Forum Activity (Tinto: social integration) ──
            if course.has_forum:
                read_prob = engagement * 0.7 * (0.5 + 0.5 * student.digital_literacy)
                if self.rng.random() < read_prob:
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="forum_read",
                        duration_minutes=round(float(self.rng.exponential(10)), 1),
                    ))

                # Posting: extraversion + social integration drive this
                post_prob = (engagement * 0.25
                             * (0.4 + 0.3 * student.personality.extraversion
                                + 0.3 * state.social_integration))
                if self.rng.random() < post_prob:
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="forum_post",
                        duration_minutes=round(float(self.rng.normal(15, 5)), 1),
                        metadata={"post_length": int(self.rng.normal(80, 30))},
                    ))

            # ── Assignment Submission (Rovai: self-regulation + time management) ──
            if week in course.assignment_weeks:
                submit_prob = (engagement
                               * (0.3 + 0.3 * student.self_regulation
                                  + 0.2 * student.time_management
                                  + 0.2 * student.personality.conscientiousness))
                submitted = self.rng.random() < submit_prob

                if submitted:
                    quality = float(np.clip(
                        0.25 * (student.prior_gpa / 4.0)
                        + 0.25 * engagement
                        + 0.20 * student.self_efficacy
                        + 0.15 * student.academic_reading_writing
                        + 0.15 * self.rng.normal(0.5, 0.15),
                        0.0, 1.0
                    ))
                    is_late = self.rng.random() > student.time_management
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="assignment_submit",
                        quality_score=round(quality, 2),
                        metadata={"is_late": is_late, "assignment_week": week},
                    ))
                    state.missed_assignments_streak = 0
                    student.add_memory(week, "assignment",
                                       f"Submitted {'late ' if is_late else ''}assignment for {course_id} ({quality:.0%})",
                                       impact=quality - 0.5)
                else:
                    state.missed_assignments_streak += 1
                    student.add_memory(week, "missed_assignment",
                                       f"Missed assignment for {course_id} (streak: {state.missed_assignments_streak})",
                                       impact=-0.3)

            # ── Live Sessions ──
            if course.has_live_sessions:
                attend_prob = engagement * 0.5 * student.time_management
                if student.is_employed:
                    attend_prob *= 0.4  # Bean & Metzner: work conflict
                if self.rng.random() < attend_prob:
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="live_session",
                        duration_minutes=round(float(self.rng.normal(55, 10)), 1),
                    ))

            # ── Exams ──
            if week == course.midterm_week or week == course.final_week:
                exam_type = "midterm" if week == course.midterm_week else "final"
                take_prob = 0.95 if engagement > 0.3 else engagement * 2.5
                if self.rng.random() < take_prob:
                    exam_quality = float(np.clip(
                        0.20 * (student.prior_gpa / 4.0)
                        + 0.20 * engagement
                        + 0.20 * student.self_efficacy
                        + 0.15 * student.self_regulation
                        + 0.10 * student.academic_reading_writing
                        + 0.15 * self.rng.normal(0.5, 0.18),
                        0.0, 1.0
                    ))
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="exam",
                        quality_score=round(exam_quality, 2),
                        metadata={"exam_type": exam_type},
                    ))
                    student.add_memory(week, "exam",
                                       f"{exam_type.title()} for {course_id} ({exam_quality:.0%})",
                                       impact=exam_quality - 0.5)

        return records

    # ── TINTO: Academic & Social Integration Updates ──

    def _update_integration(
        self, student: StudentPersona, state: SimulationState,
        week: int, context: dict, records: list[InteractionRecord],
    ):
        """Update Tinto's academic and social integration based on week's events."""

        # Academic integration: driven by assignment/exam performance
        academic_events = [r for r in records if r.interaction_type in ("assignment_submit", "exam")]
        if academic_events:
            avg_quality = np.mean([r.quality_score for r in academic_events])
            # Good performance strengthens academic integration
            state.academic_integration += (avg_quality - 0.5) * 0.05
        else:
            # No academic activity → slight erosion
            state.academic_integration -= 0.02

        # Social integration: driven by forum posts (Tinto + Durkheim)
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        forum_reads = sum(1 for r in records if r.interaction_type == "forum_read")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")

        if forum_posts > 0:
            state.social_integration += 0.03 * min(forum_posts, 3)
        if live_sessions > 0:
            state.social_integration += 0.02
        if forum_reads > 0 and forum_posts == 0:
            state.social_integration += 0.005  # Lurking helps minimally
        if forum_posts == 0 and forum_reads == 0 and live_sessions == 0:
            state.social_integration -= 0.03  # Durkheim: isolation erodes connection

        state.academic_integration = float(np.clip(state.academic_integration, 0.01, 0.95))
        state.social_integration = float(np.clip(state.social_integration, 0.01, 0.80))

    # ── ENGAGEMENT UPDATE (Multi-theory) ──

    def _update_engagement(
        self, student: StudentPersona, state: SimulationState,
        week: int, context: dict, records: list[InteractionRecord],
    ):
        """
        Update engagement incorporating all theoretical anchors.

        Tinto: Integration → institutional commitment → engagement
        Bean & Metzner: Environmental stressors erode engagement
        Rovai: Self-regulation sustains engagement across weeks
        Kember: Cost-benefit perception modulates persistence
        """
        engagement = state.current_engagement

        # ── Tinto: Integration effect ──
        # Academic integration is the stronger factor in ODE
        integration_effect = (
            state.academic_integration * 0.06
            + state.social_integration * 0.02
            - 0.04  # Baseline decay (requires active maintenance)
        )
        engagement += integration_effect

        # ── Bean & Metzner: Environmental pressure ──
        env_pressure = 0.0
        if student.is_employed and student.weekly_work_hours > 35:
            env_pressure -= 0.02  # Overwork erodes engagement
        if student.has_family_responsibilities:
            env_pressure -= 0.015
        if student.financial_stress > 0.6:
            env_pressure -= 0.01
        engagement += env_pressure

        # ── Rovai: Self-regulation buffer ──
        # High self-regulation students resist engagement decay
        regulation_buffer = (student.self_regulation - 0.5) * 0.03
        engagement += regulation_buffer

        # ── Academic outcomes this week ──
        for r in records:
            if r.interaction_type in ("assignment_submit", "exam"):
                if r.quality_score > 0.7:
                    engagement += 0.025
                elif r.quality_score < 0.3:
                    engagement -= 0.035

        # Missed assignments compound (Bäulke: perceived misfit grows)
        if state.missed_assignments_streak >= 2:
            engagement -= 0.04 * min(state.missed_assignments_streak - 1, 3)

        # ── Exam week stress (Neuroticism moderator) ──
        if context.get("is_exam_week"):
            engagement -= student.personality.neuroticism * 0.04

        # ── Kember: Cost-benefit recalculation after major events ──
        if context.get("is_exam_week") or state.missed_assignments_streak >= 2:
            # Poor performance reduces perceived cost-benefit
            recent_quality = [r.quality_score for r in records
                              if r.interaction_type in ("assignment_submit", "exam") and r.quality_score > 0]
            if recent_quality:
                avg_q = np.mean(recent_quality)
                state.perceived_cost_benefit += (avg_q - 0.5) * 0.04
            elif state.missed_assignments_streak >= 2:
                state.perceived_cost_benefit -= 0.03

            state.perceived_cost_benefit = float(np.clip(state.perceived_cost_benefit, 0.05, 0.95))
            # Cost-benefit feeds back into engagement
            engagement += (state.perceived_cost_benefit - 0.5) * 0.02

        state.current_engagement = float(np.clip(engagement, 0.01, 0.99))
        state.weekly_engagement_history.append(state.current_engagement)

    # ── BÄULKE ET AL.: Dropout Phase Progression ──

    def _advance_dropout_phase(
        self, student: StudentPersona, state: SimulationState, week: int,
    ):
        """
        Advance the dropout phase based on Bäulke et al.'s process model.

        Phase transitions:
        0 → 1: Engagement drops below threshold (perceived misfit)
        1 → 2: Sustained low engagement + declining trajectory (rumination)
        2 → 3: Very low engagement + low cost-benefit (info seeking)
        3 → 4: Dropout decision — triggered by critical event or sustained phase 3
        """
        eng = state.current_engagement
        history = state.weekly_engagement_history

        if state.dropout_phase == 0:
            # Phase 0 → 1: Perceived misfit
            # Trigger: engagement drops below 0.38 (notable disengagement)
            if eng < 0.38:
                state.dropout_phase = 1
                student.add_memory(week, "dropout_phase", "Beginning to question fit with program", -0.2)

        elif state.dropout_phase == 1:
            # Can recover back to 0
            if eng > 0.45:
                state.dropout_phase = 0
                student.add_memory(week, "recovery", "Re-engaged with program", 0.2)
            # Phase 1 → 2: Rumination (requires sustained decline)
            elif eng < 0.30 and len(history) >= 3 and history[-1] < history[-3]:
                state.dropout_phase = 2
                student.add_memory(week, "dropout_phase", "Actively considering whether to continue", -0.3)

        elif state.dropout_phase == 2:
            # Can still recover
            if eng > 0.40:
                state.dropout_phase = 1
            # Phase 2 → 3: Info seeking (requires very low engagement + poor cost-benefit)
            elif eng < 0.20 and state.perceived_cost_benefit < 0.32:
                state.dropout_phase = 3
                student.add_memory(week, "dropout_phase", "Exploring alternatives to current program", -0.4)

        elif state.dropout_phase == 3:
            # Recovery still possible but unlikely
            if eng > 0.35 and state.perceived_cost_benefit > 0.45:
                state.dropout_phase = 2
            # Phase 3 → 4: Decision — requires multiple concurrent triggers
            else:
                triggers = 0
                if eng < 0.10:
                    triggers += 1  # Near-zero engagement
                if state.missed_assignments_streak >= 3:
                    triggers += 1  # Academic failure cascade
                if state.perceived_cost_benefit < 0.15:
                    triggers += 1  # Economic rationality: not worth it
                if student.financial_stress > 0.7:
                    triggers += 1  # Bean & Metzner: environmental crisis
                if week == 10:
                    triggers += 1  # Withdrawal deadline (Kember)

                # Need at least 2 triggers; probability scaled by base risk
                if triggers >= 2:
                    decision_prob = student.base_dropout_risk * triggers * 0.18
                    if self.rng.random() < decision_prob:
                        state.dropout_phase = 4
                        student.add_memory(week, "dropout", "Decided to withdraw from program", -0.8)

    def summary_statistics(self, states: dict[str, SimulationState]) -> dict[str, Any]:
        total = len(states)
        dropouts = sum(1 for s in states.values() if s.has_dropped_out)
        dropout_weeks = [s.dropout_week for s in states.values() if s.dropout_week]
        final_engagements = [
            s.weekly_engagement_history[-1] if s.weekly_engagement_history else 0
            for s in states.values() if not s.has_dropped_out
        ]
        phase_dist = {}
        for s in states.values():
            p = s.dropout_phase if not s.has_dropped_out else 4
            phase_dist[p] = phase_dist.get(p, 0) + 1

        return {
            "total_students": total,
            "dropout_count": dropouts,
            "dropout_rate": dropouts / total if total > 0 else 0,
            "mean_dropout_week": float(np.mean(dropout_weeks)) if dropout_weeks else None,
            "std_dropout_week": float(np.std(dropout_weeks)) if dropout_weeks else None,
            "mean_final_engagement": float(np.mean(final_engagements)) if final_engagements else None,
            "retained_students": total - dropouts,
            "dropout_phase_distribution": {
                f"phase_{k}": v for k, v in sorted(phase_dist.items())
            },
        }
