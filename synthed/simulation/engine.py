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
from .theories import (
    TintoIntegration,
    BeanMetznerPressure,
    KemberCostBenefit,
    BaulkeDropoutPhase,
    GarrisonCoI,
    MooreTransactionalDistance,
    EpsteinAxtellPeerInfluence,
    RovaiPersistence,
    SDTMotivationDynamics,
    SDTNeedSatisfaction,
    PositiveEventHandler,
    GonzalezExhaustion,
    ExhaustionState,
)


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
    # Deci & Ryan (1985): Self-Determination Theory
    sdt_needs: SDTNeedSatisfaction = field(default_factory=SDTNeedSatisfaction)
    current_motivation_type: str = "extrinsic"
    # Gonzalez et al. (2025): Academic exhaustion as mediator
    exhaustion: ExhaustionState = field(default_factory=ExhaustionState)
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

        # Theory-specific delegates
        self.tinto = TintoIntegration()
        self.bean_metzner = BeanMetznerPressure()
        self.kember = KemberCostBenefit()
        self.baulke = BaulkeDropoutPhase()
        self.garrison = GarrisonCoI()
        self.moore = MooreTransactionalDistance()
        self.epstein_axtell = EpsteinAxtellPeerInfluence()
        self.rovai = RovaiPersistence()
        self.sdt = SDTMotivationDynamics()
        self.positive_events = PositiveEventHandler()
        self.gonzalez = GonzalezExhaustion()

    def run(
        self,
        students: list[StudentPersona],
        weeks: int | None = None,
        initial_state_overrides: dict[str, dict[str, Any]] | None = None,
        initial_network: SocialNetwork | None = None,
    ) -> tuple[list[InteractionRecord], dict[str, SimulationState], SocialNetwork]:
        """
        Run the simulation with two-phase weekly loop (Epstein & Axtell, 1996).

        Phase 1: Individual behavior — each student acts independently.
        Phase 2: Social network formation + peer influence — agents affect each other.

        Args:
            students: List of student personas to simulate.
            weeks: Number of weeks to simulate (defaults to environment total).
            initial_state_overrides: Per-student state attribute overrides, keyed
                by student ID.  Applied after default state initialization to
                carry forward evolved values from a previous semester.
            initial_network: Pre-existing social network to continue from
                (e.g., carried over from a previous semester).

        Returns:
            Tuple of (interaction records, final states, social network).
        """
        weeks = weeks or self.env.total_weeks
        all_records: list[InteractionRecord] = []
        states: dict[str, SimulationState] = {}
        self.network = initial_network or SocialNetwork()

        for student in students:
            course_ids = [c.id for c in self.env.courses[:student.enrolled_courses]]
            states[student.id] = SimulationState(
                student_id=student.id,
                current_engagement=student.base_engagement_probability,
                academic_integration=student.academic_integration,
                social_integration=student.social_integration,
                perceived_cost_benefit=student.perceived_cost_benefit,
                courses_active=course_ids,
                sdt_needs=SDTNeedSatisfaction(
                    autonomy=student.learner_autonomy,
                    competence=student.self_efficacy,
                    relatedness=student.social_integration,
                ),
                current_motivation_type=student.motivation_type,
            )

        # Apply per-student state overrides (multi-semester carry-over)
        if initial_state_overrides:
            for sid, overrides in initial_state_overrides.items():
                if sid in states:
                    for key, value in overrides.items():
                        setattr(states[sid], key, value)

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

                active_courses = [c for c in self.env.courses if c.id in state.courses_active]
                self.tinto.update_integration(student, state, week, week_context, week_records)
                self.garrison.update_presences(student, state, week, week_records, active_courses)
                self.sdt.update_needs(student, state, week, week_records)
                state.current_motivation_type = self.sdt.evaluate_motivation_shift(state)
                self.gonzalez.update_exhaustion(student, state, week, week_context, week_records)
                self._update_engagement(student, state, week, week_context, week_records)

            # ── Phase 2: Social network + peer influence (Epstein & Axtell) ──
            self.network.decay_links(decay_rate=0.02)
            self.epstein_axtell.update_network(week, week_records_by_student, self.network)
            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue
                self.epstein_axtell.apply_peer_influence(student, state, states, self.network)
                # CoI social_presence boosted by network degree
                degree = self.network.get_degree(student.id)
                state.coi_state.social_presence += min(degree * 0.005, 0.03)
                state.coi_state.social_presence = float(
                    np.clip(state.coi_state.social_presence, 0.01, 0.95)
                )
                # Record engagement AFTER peer influence (data integrity)
                state.weekly_engagement_history.append(state.current_engagement)
                self.baulke.advance_phase(
                    student, state, week, self.env,
                    lambda s, st: self.moore.average(s, st, self.env),
                    self.rng,
                )

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

    # ── ENGAGEMENT UPDATE (Multi-theory composer) ──

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
        decay_attenuation = 1.0 / (1.0 + 0.5 * (week - 1) ** 0.5)

        # ── Tinto: Integration effect ──
        integration_effect = (
            state.academic_integration * 0.06
            + state.social_integration * 0.02
            - 0.05 * decay_attenuation
        )
        engagement += integration_effect

        # ── Bean & Metzner: Environmental pressure ──
        engagement += self.bean_metzner.calculate_environmental_pressure(student)

        # ── Positive environmental events (counter-pressure) ──
        engagement += self.positive_events.apply(
            context.get("positive_event"), student, state
        )

        # ── Rovai: Self-regulation buffer ──
        engagement += self.rovai.regulation_buffer(student)

        # ── SDT (Deci & Ryan, 1985): Motivation type effect ──
        motivation_effect = {
            "intrinsic": 0.02, "extrinsic": 0.0, "amotivation": -0.025
        }.get(state.current_motivation_type, 0.0)
        engagement += motivation_effect

        # ── Moore (1993): Transactional distance effect ──
        avg_td = self.moore.average(student, state, self.env)
        td_effect = -(avg_td - 0.5) * 0.03
        engagement += td_effect

        # ── Garrison et al. (2000): Community of Inquiry effect ──
        coi = state.coi_state
        coi_effect = (
            coi.social_presence * 0.01
            + coi.cognitive_presence * 0.02
            + coi.teaching_presence * 0.01
            - 0.02
        )
        engagement += coi_effect

        # ── Gonzalez et al. (2025): Academic exhaustion drag ──
        engagement += self.gonzalez.exhaustion_engagement_effect(state)

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
            self.kember.recalculate(student, state, context, records, avg_td)
            # Cost-benefit feeds back into engagement
            engagement += (state.perceived_cost_benefit - 0.5) * 0.02

        # ── Persona-based engagement floor (Rovai) ──
        engagement = max(engagement, self.rovai.engagement_floor(student))

        state.current_engagement = float(np.clip(engagement, 0.01, 0.99))

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
