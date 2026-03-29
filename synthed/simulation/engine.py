"""
SimulationEngine: Theory-grounded week-by-week simulation of ODL student behavior.

Engagement and dropout mechanics map to established theoretical frameworks:

- Tinto (1975): Academic/social integration drive institutional commitment
- Bean & Metzner (1985): Environmental pressures (work, family, finances)
  outweigh social integration for non-traditional/ODE students
- Kember (1989): Students perform ongoing cost-benefit analysis
- Rovai (2003): Accessibility and digital skills as persistence factors
- Bäulke et al.: Phase-oriented view of dropout
  (non-fit perception → thoughts of quitting → deliberation → info search → decision)
- Durkheim/Tinto: Social disconnection increases dropout risk
- Moore (1993): Transactional distance = f(structure, dialogue, autonomy)
- Garrison et al. (2000): Community of Inquiry — social, cognitive, teaching presence
- Epstein & Axtell (1996): Agent-based social simulation — peer influence and contagion
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..agents.persona import StudentPersona
from .environment import ODLEnvironment, Course
from .social_network import SocialNetwork
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
class CommunityOfInquiryState:
    """Garrison et al. (2000): Three presences tracked per student."""
    social_presence: float = 0.3       # 0-1; perceived connection to learning community
    cognitive_presence: float = 0.4    # 0-1; depth of meaning-making in discourse
    teaching_presence: float = 0.5     # 0-1; perceived instructor design + facilitation


@dataclass
class SimulationState:
    """Tracks evolving state of a student across the simulation."""
    student_id: str
    current_engagement: float = 0.5
    academic_integration: float = 0.5  # Tinto: evolves with performance
    social_integration: float = 0.3  # Tinto: evolves with interaction
    perceived_cost_benefit: float = 0.6  # Kember: evolves with experience
    dropout_phase: int = 0  # Bäulke: 0–5
    cumulative_gpa: float = 0.0
    courses_active: list[str] = field(default_factory=list)
    has_dropped_out: bool = False
    dropout_week: int | None = None
    weekly_engagement_history: list[float] = field(default_factory=list)
    missed_assignments_streak: int = 0  # Consecutive missed assignments
    # Garrison et al. (2000): Community of Inquiry
    coi_state: CommunityOfInquiryState = field(default_factory=CommunityOfInquiryState)
    # Temporal memory (moved from StudentPersona to avoid mutating input)
    memory: list[dict[str, Any]] = field(default_factory=list)


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
    - Phase 0 (Baseline): Student enrolled, no dropout indicators
    - Phase 1 (Non-Fit Perception): Sensing incongruence with program
    - Phase 2 (Thoughts of Quitting): Unsystematic consideration of alternatives
    - Phase 3 (Deliberation): Consciously weighing pros/cons of staying vs leaving
    - Phase 4 (Information Search): Targeted search for alternative options
    - Phase 5 (Final Decision): Dropout occurs
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
    ) -> tuple[list[InteractionRecord], dict[str, SimulationState], SocialNetwork]:
        """
        Run the simulation with two-phase weekly loop (Epstein & Axtell, 1996).

        Phase 1: Individual behavior — each student acts independently.
        Phase 2: Social network formation + peer influence — agents affect each other.

        Returns:
            Tuple of (interaction records, final states, social network).
        """
        weeks = weeks or self.env.total_weeks
        all_records: list[InteractionRecord] = []
        states: dict[str, SimulationState] = {}
        self.network = SocialNetwork()

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
            week_records_by_student: dict[str, list[InteractionRecord]] = {}

            # ── Phase 1: Individual behavior ──
            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue

                week_records = self._simulate_student_week(student, state, week, week_context)
                all_records.extend(week_records)
                week_records_by_student[student.id] = week_records
                self._update_integration(student, state, week, week_context, week_records)
                self._update_coi_presences(student, state, week, week_records)
                self._update_engagement(student, state, week, week_context, week_records)

            # ── Phase 2: Social network + peer influence (Epstein & Axtell) ──
            self._update_social_network(week, week_records_by_student)
            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue
                self._apply_peer_influence(student, state, states)
                # CoI social_presence boosted by network degree
                degree = self.network.get_degree(student.id)
                state.coi_state.social_presence += min(degree * 0.005, 0.03)
                state.coi_state.social_presence = float(
                    np.clip(state.coi_state.social_presence, 0.01, 0.95)
                )
                # Record engagement AFTER peer influence (data integrity)
                state.weekly_engagement_history.append(state.current_engagement)
                self._advance_dropout_phase(student, state, week)

                if state.dropout_phase >= 5:
                    state.has_dropped_out = True
                    state.dropout_week = week

        return all_records, states, self.network

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
                    state.memory.append({"week": week, "event_type": "assignment",
                                        "details": f"Submitted {'late ' if is_late else ''}assignment for {course_id} ({quality:.0%})",
                                        "impact": quality - 0.5})
                else:
                    state.missed_assignments_streak += 1
                    state.memory.append({"week": week, "event_type": "missed_assignment",
                                        "details": f"Missed assignment for {course_id} (streak: {state.missed_assignments_streak})",
                                        "impact": -0.3})

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
                    state.memory.append({"week": week, "event_type": "exam",
                                        "details": f"{exam_type.title()} for {course_id} ({exam_quality:.0%})",
                                        "impact": exam_quality - 0.5})

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

        # ── Adaptive baseline decay ──
        # Early weeks have higher decay (adaptation shock); decay diminishes
        # as the student settles in. Modeled as inverse-sqrt attenuation.
        # Week 1: full decay (1.0x), Week 14: ~0.27x, Week 28: ~0.19x
        decay_attenuation = 1.0 / (1.0 + 0.5 * (week - 1) ** 0.5)

        # ── Tinto: Integration effect ──
        # Academic integration is the stronger factor in ODE
        integration_effect = (
            state.academic_integration * 0.06
            + state.social_integration * 0.02
            - 0.05 * decay_attenuation  # Attenuated baseline decay
        )
        engagement += integration_effect

        # ── Bean & Metzner: Environmental pressure ──
        # ODL students face heavier external burdens (employment, family, finances)
        env_pressure = 0.0
        if student.is_employed and student.weekly_work_hours > 30:
            env_pressure -= 0.025  # Overwork erodes engagement
        if student.has_family_responsibilities:
            env_pressure -= 0.02
        if student.financial_stress > 0.5:
            env_pressure -= 0.015
        engagement += env_pressure

        # ── Rovai: Self-regulation buffer ──
        # High self-regulation students resist engagement decay
        regulation_buffer = (student.self_regulation - 0.5) * 0.03
        engagement += regulation_buffer

        # ── Moore (1993): Transactional distance effect ──
        avg_td = self._avg_transactional_distance(student, state)
        td_effect = -(avg_td - 0.5) * 0.03  # High TD erodes engagement
        engagement += td_effect

        # ── Garrison et al. (2000): Community of Inquiry effect ──
        coi = state.coi_state
        coi_effect = (
            coi.social_presence * 0.01
            + coi.cognitive_presence * 0.02
            + coi.teaching_presence * 0.01
            - 0.02  # baseline offset
        )
        engagement += coi_effect

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

            # Moore → Kember: high transactional distance reduces perceived value
            state.perceived_cost_benefit -= (avg_td - 0.5) * 0.02
            state.perceived_cost_benefit = float(np.clip(state.perceived_cost_benefit, 0.05, 0.95))
            # Cost-benefit feeds back into engagement
            engagement += (state.perceived_cost_benefit - 0.5) * 0.02

        # ── Persona-based engagement floor ──
        # Students with strong self-regulation, goal commitment, and self-efficacy
        # have a personal floor below which engagement does not drop.
        # This models resilience: some students persist despite adversity.
        personal_floor = (
            student.self_regulation * 0.15
            + student.goal_commitment * 0.12
            + student.self_efficacy * 0.10
            + student.learner_autonomy * 0.08  # Moore: autonomous learners persist
        ) * 0.50  # Scale: max ~0.22 for high-resilience students
        engagement = max(engagement, personal_floor)

        state.current_engagement = float(np.clip(engagement, 0.01, 0.99))

    # ── BÄULKE ET AL.: Phase-Oriented Dropout Progression ──

    def _advance_dropout_phase(
        self, student: StudentPersona, state: SimulationState, week: int,
    ):
        """
        Advance the dropout phase based on Bäulke, Grunschel & Dresel (2022).

        Six-phase model integrating Betsch (2005) decision-making and
        Rubicon action-phase model (Achtziger & Gollwitzer, 2010):

        0 → 1: Non-fit perception — sensing incongruence with program
        1 → 2: Thoughts of quitting — unsystematic consideration of alternatives
        2 → 3: Deliberation — consciously weighing pros/cons of staying vs leaving
        3 → 4: Information search — targeted search for alternative options
        4 → 5: Final decision — committed to withdraw
        """
        eng = state.current_engagement
        history = state.weekly_engagement_history
        avg_td = self._avg_transactional_distance(student, state)

        if state.dropout_phase == 0:
            # Phase 0 → 1: Non-fit perception
            if (eng < 0.40
                    or (eng < 0.45 and state.coi_state.cognitive_presence < 0.25)
                    or (eng < 0.45 and avg_td > 0.55)):
                state.dropout_phase = 1
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Non-fit perception: questioning fit with program",
                                    "impact": -0.2})

        elif state.dropout_phase == 1:
            # Recovery back to 0 (harder in ODL — fewer re-engagement mechanisms)
            if eng > 0.50:
                state.dropout_phase = 0
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Re-engaged with program", "impact": 0.2})
            # Phase 1 → 2: Thoughts of quitting
            elif (eng < 0.36
                  and (state.missed_assignments_streak >= 1
                       or state.social_integration < 0.20)):
                state.dropout_phase = 2
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Thoughts of quitting: considering alternatives "
                                               "after experiencing difficulties",
                                    "impact": -0.25})

        elif state.dropout_phase == 2:
            # Recovery back to 1
            if eng > 0.45:
                state.dropout_phase = 1
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Renewed commitment, thoughts of quitting subsided",
                                    "impact": 0.15})
            # Phase 2 → 3: Deliberation (requires sustained decline)
            elif eng < 0.32 and len(history) >= 2 and history[-1] < history[-2]:
                state.dropout_phase = 3
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Deliberation: actively weighing whether to continue",
                                    "impact": -0.3})

        elif state.dropout_phase == 3:
            # Recovery back to 2
            if eng > 0.40:
                state.dropout_phase = 2
                state.memory.append({"week": week, "event_type": "recovery",
                                    "details": "Stepped back from deliberation to thoughts of quitting",
                                    "impact": 0.1})
            # Phase 3 → 4: Information search
            elif eng < 0.25 and state.perceived_cost_benefit < 0.40:
                state.dropout_phase = 4
                state.memory.append({"week": week, "event_type": "dropout_phase",
                                    "details": "Information search: exploring alternatives "
                                               "to current program",
                                    "impact": -0.4})

        elif state.dropout_phase == 4:
            # Recovery still possible but unlikely
            if eng > 0.35 and state.perceived_cost_benefit > 0.45:
                state.dropout_phase = 3
            # Phase 4 → 5: Final decision — probabilistic, scaled by triggers
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
                # Withdrawal deadline at ~70% of semester (Kember)
                withdrawal_week = int(self.env.total_weeks * 0.70)
                if week == withdrawal_week:
                    triggers += 1

                if triggers >= 1:
                    decision_prob = student.base_dropout_risk * triggers * 0.28
                    if self.rng.random() < decision_prob:
                        state.dropout_phase = 5
                        state.memory.append({"week": week, "event_type": "dropout",
                                            "details": "Decided to withdraw from program",
                                            "impact": -0.8})

    # ── GARRISON ET AL. (2000): Community of Inquiry ──

    def _update_coi_presences(
        self, student: StudentPersona, state: SimulationState,
        week: int, records: list[InteractionRecord],
    ):
        """
        Update Community of Inquiry presences based on weekly activity.

        Social presence: driven by forum posts, live sessions, extraversion.
        Cognitive presence: driven by assignment quality, forum depth, openness.
        Teaching presence: driven by course dialogue, instructor responsiveness.
        """
        coi = state.coi_state

        # Social presence
        forum_posts = sum(1 for r in records if r.interaction_type == "forum_post")
        live_sessions = sum(1 for r in records if r.interaction_type == "live_session")
        coi.social_presence += (
            forum_posts * 0.03
            + live_sessions * 0.02
            + (student.personality.extraversion - 0.5) * 0.01
            - 0.02  # decay without activity
        )

        # Cognitive presence
        academic_events = [r for r in records
                          if r.interaction_type in ("assignment_submit", "exam")]
        if academic_events:
            avg_quality = float(np.mean([r.quality_score for r in academic_events]))
            coi.cognitive_presence += (avg_quality - 0.5) * 0.04
        deep_posts = sum(1 for r in records
                        if r.interaction_type == "forum_post"
                        and r.metadata.get("post_length", 0) > 100)
        coi.cognitive_presence += deep_posts * 0.02 - 0.01

        # Teaching presence (environment-driven, modulated by student perception)
        active_courses = [
            c for c in self.env.courses if c.id in state.courses_active
        ]
        if active_courses:
            avg_dialogue = float(np.mean([c.dialogue_frequency for c in active_courses]))
            avg_responsiveness = float(np.mean([c.instructor_responsiveness for c in active_courses]))
            coi.teaching_presence += (avg_dialogue - 0.4) * 0.02
            coi.teaching_presence += (avg_responsiveness - 0.5) * 0.01
        coi.teaching_presence += (student.institutional_support_access - 0.5) * 0.01

        # Clamp all presences
        coi.social_presence = float(np.clip(coi.social_presence, 0.01, 0.95))
        coi.cognitive_presence = float(np.clip(coi.cognitive_presence, 0.01, 0.95))
        coi.teaching_presence = float(np.clip(coi.teaching_presence, 0.01, 0.95))

    # ── MOORE (1993): Transactional Distance ──

    def _calculate_transactional_distance(
        self, student: StudentPersona, course: Course,
    ) -> float:
        """
        Moore (1993): Transactional distance = f(structure, dialogue, autonomy).
        High structure + low dialogue + low autonomy = high transactional distance.
        Returns 0-1 where higher = more distant (worse for engagement).
        """
        td = (
            course.structure_level * 0.35
            - course.dialogue_frequency * 0.30
            - student.learner_autonomy * 0.25
            - course.instructor_responsiveness * 0.10
        )
        return float(np.clip(td + 0.30, 0.0, 1.0))

    # ── EPSTEIN & AXTELL (1996): Agent-Based Social Simulation ──

    def _update_social_network(
        self, week: int, week_records: dict[str, list[InteractionRecord]],
    ) -> None:
        """
        Epstein & Axtell (1996): Form/strengthen links based on co-activity.
        Students who post in the same forum in the same week form weak ties.
        """
        # Group forum posters by course
        course_posters: dict[str, list[str]] = {}
        for sid, records in week_records.items():
            for r in records:
                if r.interaction_type == "forum_post":
                    course_posters.setdefault(r.course_id, []).append(sid)

        for _course_id, posters in course_posters.items():
            unique_posters = list(set(posters))
            for i, p1 in enumerate(unique_posters):
                for p2 in unique_posters[i + 1:]:
                    self.network.add_link(p1, p2, 0.05, "forum")
                    self.network.add_link(p2, p1, 0.05, "forum")

        # Live session co-attendance also forms ties
        course_live: dict[str, list[str]] = {}
        for sid, records in week_records.items():
            for r in records:
                if r.interaction_type == "live_session":
                    course_live.setdefault(r.course_id, []).append(sid)

        for _course_id, attendees in course_live.items():
            unique_attendees = list(set(attendees))
            for i, a1 in enumerate(unique_attendees):
                for a2 in unique_attendees[i + 1:]:
                    self.network.add_link(a1, a2, 0.03, "live_session")
                    self.network.add_link(a2, a1, 0.03, "live_session")

    def _apply_peer_influence(
        self, student: StudentPersona, state: SimulationState,
        states: dict[str, SimulationState],
    ) -> None:
        """
        Epstein & Axtell (1996): Peer contagion effects.

        Three influence channels:
        1. Engagement contagion: peers pull engagement toward local mean
        2. Dropout contagion: peers in dropout phases increase risk
        3. Social integration reinforcement via peer connection
        """
        # Engagement contagion
        eng_influence = self.network.peer_influence(student.id, states, "current_engagement")
        state.current_engagement = float(np.clip(
            state.current_engagement + eng_influence, 0.01, 0.99
        ))

        # Dropout contagion
        contagion_penalty = self.network.dropout_contagion(student.id, states)
        if contagion_penalty > 0:
            state.current_engagement = float(np.clip(
                state.current_engagement - contagion_penalty, 0.01, 0.99
            ))

        # Peer connection reinforces social integration (Tinto via ABSS)
        degree = self.network.get_degree(student.id)
        if degree > 0:
            state.social_integration = float(np.clip(
                state.social_integration + min(degree * 0.003, 0.02), 0.01, 0.80
            ))

    def _avg_transactional_distance(
        self, student: StudentPersona, state: SimulationState,
    ) -> float:
        """Average transactional distance across active courses."""
        distances = []
        for cid in state.courses_active:
            course = self.env.get_course_by_id(cid)
            if course:
                distances.append(self._calculate_transactional_distance(student, course))
        return float(np.mean(distances)) if distances else 0.5

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
            p = s.dropout_phase if not s.has_dropped_out else 5
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
