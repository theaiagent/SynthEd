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
from .environment import ODLEnvironment
from .institutional import InstitutionalConfig, scale_by
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
    UnavoidableWithdrawal,
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
    gpa_points_sum: float = 0.0  # running sum of quality scores scaled to 4.0
    gpa_count: int = 0           # number of graded items (assignments + exams)
    perceived_mastery_sum: float = 0.0   # running sum of raw quality (uninflated)
    perceived_mastery_count: int = 0     # number of graded items for mastery track
    courses_active: list[str] = field(default_factory=list)
    has_dropped_out: bool = False
    dropout_week: int | None = None
    withdrawal_reason: str | None = None
    weekly_engagement_history: list[float] = field(default_factory=list)
    missed_assignments_streak: int = 0  # Consecutive missed assignments
    # Garrison et al. (2000): Community of Inquiry
    coi_state: CommunityOfInquiryState = field(default_factory=CommunityOfInquiryState)
    # Deci & Ryan (1985): Self-Determination Theory
    sdt_needs: SDTNeedSatisfaction = field(default_factory=SDTNeedSatisfaction)
    current_motivation_type: str = "extrinsic"
    # Gonzalez et al. (2025): Academic exhaustion as mediator
    exhaustion: ExhaustionState = field(default_factory=ExhaustionState)
    # Bean & Metzner coping adaptation (Lazarus & Folkman, 1984)
    coping_factor: float = 0.0  # 0.0-0.5; reduces environmental pressure impact
    # Environmental shocks (Bean & Metzner: acute life events)
    env_shock_remaining: int = 0        # weeks remaining for active shock
    env_shock_magnitude: float = 0.0    # engagement penalty per week during shock
    # Temporal memory (moved from StudentPersona to avoid mutating input)
    memory: list[dict[str, Any]] = field(default_factory=list)

    @property
    def perceived_mastery(self) -> float:
        """Raw quality average (uninflated by grade floor). Returns 0.5 when no items recorded."""
        if self.perceived_mastery_count == 0:
            return 0.5
        return self.perceived_mastery_sum / self.perceived_mastery_count


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

    # ── _simulate_student_week constants ──

    # LMS login generation
    _LOGIN_ENG_MULTIPLIER: float = 5          # base login count scales with engagement
    _LOGIN_LITERACY_FLOOR: float = 0.5        # digital literacy floor for login rate
    _LOGIN_LITERACY_SCALE: float = 0.5        # digital literacy scaling for login rate
    _LOGIN_DURATION_MEAN_FACTOR: float = 25   # mean login duration scales with engagement
    _LOGIN_DURATION_STD: float = 12           # std dev of login duration
    _LOGIN_DURATION_MIN: float = 5            # minimum login duration in minutes

    # Forum activity
    _FORUM_READ_ENG_FACTOR: float = 0.7       # engagement factor for forum read probability
    _FORUM_READ_LITERACY_FLOOR: float = 0.5   # digital literacy floor for forum reads
    _FORUM_READ_LITERACY_SCALE: float = 0.5   # digital literacy scaling for forum reads
    _FORUM_READ_EXP_MEAN: float = 10          # mean of exponential distribution for read duration
    _FORUM_POST_ENG_FACTOR: float = 0.25      # engagement factor for forum post probability
    _FORUM_POST_EXTRA_FLOOR: float = 0.4      # base component of post probability
    _FORUM_POST_EXTRA_WEIGHT: float = 0.3     # weight of extraversion in post probability
    _FORUM_POST_SOCIAL_WEIGHT: float = 0.3    # weight of social integration in post probability
    _FORUM_POST_DURATION_MEAN: float = 15     # mean post duration in minutes
    _FORUM_POST_DURATION_STD: float = 5       # std dev of post duration
    _FORUM_POST_LENGTH_MEAN: float = 80       # mean post length in characters
    _FORUM_POST_LENGTH_STD: float = 30        # std dev of post length

    # Assignment submission
    _ASSIGN_SUBMIT_REG_WEIGHT: float = 0.3    # self-regulation weight in submit probability
    _ASSIGN_SUBMIT_TIME_WEIGHT: float = 0.2   # time management weight in submit probability
    _ASSIGN_SUBMIT_CONSC_WEIGHT: float = 0.2  # conscientiousness weight in submit probability
    _ASSIGN_SUBMIT_BASE: float = 0.3          # base probability component for submission
    _ASSIGN_GPA_WEIGHT: float = 0.25          # prior GPA weight in assignment quality
    _ASSIGN_ENG_WEIGHT: float = 0.25          # engagement weight in assignment quality
    _ASSIGN_EFFICACY_WEIGHT: float = 0.20     # self-efficacy weight in assignment quality
    _ASSIGN_READING_WEIGHT: float = 0.15      # reading/writing skill weight
    _ASSIGN_NOISE_WEIGHT: float = 0.15        # random noise weight in quality
    _ASSIGN_NOISE_STD: float = 0.15           # std dev of assignment quality noise
    _GPA_SCALE: float = 4.0                   # GPA denominator for normalisation
    _GRADE_FLOOR: float = 0.45               # structural grade floor (easy marks, partial credit)
    _MISSED_IMPACT: float = -0.3              # memory impact of missed assignment

    # Live sessions
    _LIVE_ENG_FACTOR: float = 0.5             # engagement factor for live attendance
    _LIVE_EMPLOYED_PENALTY: float = 0.4       # Bean & Metzner: work conflict penalty
    _LIVE_DURATION_MEAN: float = 55           # mean live session duration in minutes
    _LIVE_DURATION_STD: float = 10            # std dev of live session duration

    # Exams
    _EXAM_TAKE_HIGH_ENG_PROB: float = 0.95    # exam take probability when engagement > threshold
    _EXAM_TAKE_ENG_THRESHOLD: float = 0.3     # engagement threshold for high exam probability
    _EXAM_TAKE_LOW_MULTIPLIER: float = 2.5    # multiplier for low-engagement exam probability
    _EXAM_GPA_WEIGHT: float = 0.20            # prior GPA weight in exam quality
    _EXAM_ENG_WEIGHT: float = 0.20            # engagement weight in exam quality
    _EXAM_EFFICACY_WEIGHT: float = 0.20       # self-efficacy weight in exam quality
    _EXAM_REG_WEIGHT: float = 0.15            # self-regulation weight in exam quality
    _EXAM_READING_WEIGHT: float = 0.10        # reading/writing skill weight
    _EXAM_NOISE_WEIGHT: float = 0.15          # random noise weight in exam quality
    _EXAM_NOISE_STD: float = 0.18             # std dev of exam quality noise

    # ── _update_engagement constants ──

    _DECAY_DAMPING_FACTOR: float = 0.5        # controls how quickly decay attenuates over weeks
    _TINTO_ACADEMIC_WEIGHT: float = 0.06      # academic integration weight in engagement
    _TINTO_SOCIAL_WEIGHT: float = 0.02        # social integration weight in engagement
    _TINTO_DECAY_BASE: float = 0.05           # base weekly decay attenuated over time
    _MOTIVATION_INTRINSIC_BOOST: float = 0.02  # engagement boost for intrinsic motivation
    _MOTIVATION_AMOTIVATION_PENALTY: float = 0.025  # engagement penalty for amotivation
    _TD_EFFECT_FACTOR: float = 0.03           # transactional distance effect on engagement
    _COI_SOCIAL_WEIGHT: float = 0.01          # CoI social presence effect weight
    _COI_COGNITIVE_WEIGHT: float = 0.02       # CoI cognitive presence effect weight
    _COI_TEACHING_WEIGHT: float = 0.01        # CoI teaching presence effect weight
    _COI_BASELINE_OFFSET: float = 0.02        # CoI baseline offset (subtracted)
    _HIGH_QUALITY_THRESHOLD: float = 0.7      # quality above this boosts engagement
    _HIGH_QUALITY_BOOST: float = 0.025        # engagement boost for high-quality work
    _LOW_QUALITY_THRESHOLD: float = 0.3       # quality below this penalises engagement
    _LOW_QUALITY_PENALTY: float = 0.035       # engagement penalty for low-quality work
    _MISSED_STREAK_PENALTY: float = 0.04      # per-streak engagement erosion
    _MISSED_STREAK_CAP: int = 3               # max streak multiplier
    _NEUROTICISM_EXAM_FACTOR: float = 0.04    # neuroticism effect during exam weeks
    _CB_FEEDBACK_FACTOR: float = 0.02         # cost-benefit feedback into engagement
    _ENGAGEMENT_CLIP_LO: float = 0.01         # engagement lower bound
    _ENGAGEMENT_CLIP_HI: float = 0.99         # engagement upper bound

    # ── Phase 2: social network constants ──
    _NETWORK_DECAY_RATE: float = 0.02         # weekly link decay rate
    _COI_DEGREE_FACTOR: float = 0.005         # social presence boost per network degree
    _COI_DEGREE_CAP: float = 0.03             # max social presence boost from network

    def __init__(
        self,
        environment: ODLEnvironment,
        llm_client: LLMClient | None = None,
        seed: int = 42,
        mode: str = "rule_based",
        unavoidable_withdrawal_rate: float = 0.0,
        institutional_config: InstitutionalConfig | None = None,
    ):
        self.env = environment
        self.inst = institutional_config or InstitutionalConfig()
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
        self.unavoidable_withdrawal = UnavoidableWithdrawal(
            per_semester_probability=unavoidable_withdrawal_rate,
            total_weeks=environment.total_weeks,
        )

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
                coi_state=CommunityOfInquiryState(
                    teaching_presence=self.inst.teaching_presence_baseline,
                ),
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

                if self.unavoidable_withdrawal.check_withdrawal(student, state, week, self.rng):
                    continue

                week_records = self._simulate_student_week(student, state, week, week_context)
                all_records.extend(week_records)
                week_records_by_student[student.id] = week_records

                active_courses = [c for c in self.env.courses if c.id in state.courses_active]
                self.tinto.update_integration(student, state, week, week_context, week_records)
                self.garrison.update_presences(student, state, week, week_records, active_courses)
                self.sdt.update_needs(student, state, week, week_records)
                state.current_motivation_type = self.sdt.evaluate_motivation_shift(state)
                self.gonzalez.update_exhaustion(student, state, week, week_context, week_records,
                                                inst=self.inst)
                self._update_engagement(student, state, week, week_context, week_records)

            # ── Phase 2: Social network + peer influence (Epstein & Axtell) ──
            self.network.decay_links(decay_rate=self._NETWORK_DECAY_RATE)
            self.epstein_axtell.update_network(week, week_records_by_student, self.network, rng=self.rng)
            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue
                self.epstein_axtell.apply_peer_influence(student, state, states, self.network)
                # CoI social_presence boosted by network degree
                degree = self.network.get_degree(student.id)
                state.coi_state.social_presence += min(degree * self._COI_DEGREE_FACTOR, self._COI_DEGREE_CAP)
                state.coi_state.social_presence = float(
                    np.clip(state.coi_state.social_presence, self._ENGAGEMENT_CLIP_LO, self._ENGAGEMENT_CLIP_HI)
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

    def _record_graded_item(self, state: SimulationState, quality: float) -> None:
        """Update cumulative GPA with a graded item (assignment or exam).

        Applies a structural grade floor before scaling to GPA. In real courses
        students earn baseline marks from assignment templates, partial credit,
        and easy initial portions — this floor captures that effect.
        """
        graded = self._GRADE_FLOOR + (1.0 - self._GRADE_FLOOR) * quality
        state.gpa_points_sum += graded * self._GPA_SCALE
        state.gpa_count += 1
        state.cumulative_gpa = state.gpa_points_sum / state.gpa_count
        state.perceived_mastery_sum += quality
        state.perceived_mastery_count += 1

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
            effective_login_floor = scale_by(self._LOGIN_LITERACY_FLOOR, self.inst.technology_quality)  # [inst: technology_quality]
            login_rate = engagement * self._LOGIN_ENG_MULTIPLIER * (effective_login_floor + self._LOGIN_LITERACY_SCALE * student.digital_literacy)
            n_logins = max(0, int(self.rng.poisson(login_rate)))
            for _ in range(n_logins):
                if student.is_employed:
                    hour = float(self.rng.choice([*range(18, 24), *range(0, 2)]) + self.rng.uniform(0, 1))
                else:
                    hour = float(self.rng.uniform(8, 22))
                day = self.rng.integers(0, 7)
                duration = float(max(self._LOGIN_DURATION_MIN, self.rng.normal(self._LOGIN_DURATION_MEAN_FACTOR * engagement, self._LOGIN_DURATION_STD)))
                records.append(InteractionRecord(
                    student_id=student.id, week=week, course_id=course_id,
                    interaction_type="lms_login",
                    timestamp_offset_hours=day * 24 + hour,
                    duration_minutes=round(duration, 1),
                    metadata={"device": student.device_type},
                ))

            # ── Forum Activity (Tinto: social integration) ──
            if course.has_forum:
                effective_forum_floor = scale_by(self._FORUM_READ_LITERACY_FLOOR, self.inst.technology_quality)  # [inst: technology_quality]
                read_prob = engagement * self._FORUM_READ_ENG_FACTOR * (effective_forum_floor + self._FORUM_READ_LITERACY_SCALE * student.digital_literacy)
                if self.rng.random() < read_prob:
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="forum_read",
                        duration_minutes=round(float(self.rng.exponential(self._FORUM_READ_EXP_MEAN)), 1),
                    ))

                # Posting: extraversion + social integration drive this
                post_prob = (engagement * self._FORUM_POST_ENG_FACTOR
                             * (self._FORUM_POST_EXTRA_FLOOR + self._FORUM_POST_EXTRA_WEIGHT * student.personality.extraversion
                                + self._FORUM_POST_SOCIAL_WEIGHT * state.social_integration))
                if self.rng.random() < post_prob:
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="forum_post",
                        duration_minutes=round(float(self.rng.normal(self._FORUM_POST_DURATION_MEAN, self._FORUM_POST_DURATION_STD)), 1),
                        metadata={"post_length": int(self.rng.normal(self._FORUM_POST_LENGTH_MEAN, self._FORUM_POST_LENGTH_STD))},
                    ))

            # ── Assignment Submission (Rovai: self-regulation + time management) ──
            if week in course.assignment_weeks:
                submit_prob = (engagement
                               * (self._ASSIGN_SUBMIT_BASE + self._ASSIGN_SUBMIT_REG_WEIGHT * student.self_regulation
                                  + self._ASSIGN_SUBMIT_TIME_WEIGHT * student.time_management
                                  + self._ASSIGN_SUBMIT_CONSC_WEIGHT * student.personality.conscientiousness))
                submitted = self.rng.random() < submit_prob

                if submitted:
                    quality = float(np.clip(
                        self._ASSIGN_GPA_WEIGHT * (student.prior_gpa / self._GPA_SCALE)
                        + self._ASSIGN_ENG_WEIGHT * engagement
                        + self._ASSIGN_EFFICACY_WEIGHT * student.self_efficacy
                        + self._ASSIGN_READING_WEIGHT * student.academic_reading_writing
                        + self._ASSIGN_NOISE_WEIGHT * self.rng.normal(0.5, self._ASSIGN_NOISE_STD),
                        0.0, 1.0
                    ))
                    is_late = self.rng.random() > student.time_management
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="assignment_submit",
                        quality_score=round(quality, 2),
                        metadata={"is_late": is_late, "assignment_week": week},
                    ))
                    self._record_graded_item(state, quality)
                    state.missed_assignments_streak = 0
                    state.memory.append({"week": week, "event_type": "assignment",
                                        "details": f"Submitted {'late ' if is_late else ''}assignment for {course_id} ({quality:.0%})",
                                        "impact": quality - 0.5})
                else:
                    state.missed_assignments_streak += 1
                    state.memory.append({"week": week, "event_type": "missed_assignment",
                                        "details": f"Missed assignment for {course_id} (streak: {state.missed_assignments_streak})",
                                        "impact": self._MISSED_IMPACT})

            # ── Live Sessions ──
            if course.has_live_sessions:
                attend_prob = engagement * self._LIVE_ENG_FACTOR * student.time_management
                if student.is_employed:
                    attend_prob *= self._LIVE_EMPLOYED_PENALTY  # Bean & Metzner: work conflict
                if self.rng.random() < attend_prob:
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="live_session",
                        duration_minutes=round(float(self.rng.normal(self._LIVE_DURATION_MEAN, self._LIVE_DURATION_STD)), 1),
                    ))

            # ── Exams ──
            if week == course.midterm_week or week == course.final_week:
                exam_type = "midterm" if week == course.midterm_week else "final"
                take_prob = self._EXAM_TAKE_HIGH_ENG_PROB if engagement > self._EXAM_TAKE_ENG_THRESHOLD else engagement * self._EXAM_TAKE_LOW_MULTIPLIER
                if self.rng.random() < take_prob:
                    exam_quality = float(np.clip(
                        self._EXAM_GPA_WEIGHT * (student.prior_gpa / self._GPA_SCALE)
                        + self._EXAM_ENG_WEIGHT * engagement
                        + self._EXAM_EFFICACY_WEIGHT * student.self_efficacy
                        + self._EXAM_REG_WEIGHT * student.self_regulation
                        + self._EXAM_READING_WEIGHT * student.academic_reading_writing
                        + self._EXAM_NOISE_WEIGHT * self.rng.normal(0.5, self._EXAM_NOISE_STD),
                        0.0, 1.0
                    ))
                    records.append(InteractionRecord(
                        student_id=student.id, week=week, course_id=course_id,
                        interaction_type="exam",
                        quality_score=round(exam_quality, 2),
                        metadata={"exam_type": exam_type},
                    ))
                    self._record_graded_item(state, exam_quality)
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
        decay_attenuation = 1.0 / (1.0 + self._DECAY_DAMPING_FACTOR * (week - 1) ** 0.5)

        # ── Tinto: Integration effect ──
        integration_effect = (
            state.academic_integration * self._TINTO_ACADEMIC_WEIGHT
            + state.social_integration * self._TINTO_SOCIAL_WEIGHT
            - self._TINTO_DECAY_BASE * decay_attenuation
        )
        engagement += integration_effect

        # ── Bean & Metzner: Environmental pressure (with coping attenuation) ──
        self.bean_metzner.update_coping(student, state)
        engagement += self.bean_metzner.calculate_environmental_pressure(student, state.coping_factor)

        # ── Environmental shocks: stochastic life events ──
        if state.env_shock_remaining > 0:
            engagement -= state.env_shock_magnitude * 0.05
            state.env_shock_remaining -= 1
            if state.env_shock_remaining == 0:
                state.env_shock_magnitude = 0.0
        else:
            duration, magnitude = self.bean_metzner.stochastic_pressure_event(student, self.rng)
            if duration > 0:
                state.env_shock_remaining = duration
                state.env_shock_magnitude = magnitude
                engagement -= magnitude * 0.05
                state.memory.append({
                    "week": week, "event_type": "env_shock",
                    "details": f"Environmental shock (magnitude={magnitude:.2f}, duration={duration}w)",
                    "impact": -magnitude * 0.05,
                })

        # ── Positive environmental events (counter-pressure) ──
        engagement += self.positive_events.apply(
            context.get("positive_event"), student, state
        )

        # ── Rovai: Self-regulation buffer ──
        engagement += self.rovai.regulation_buffer(student)

        # ── SDT (Deci & Ryan, 1985): Motivation type effect ──
        motivation_effect = {
            "intrinsic": self._MOTIVATION_INTRINSIC_BOOST, "extrinsic": 0.0, "amotivation": -self._MOTIVATION_AMOTIVATION_PENALTY
        }.get(state.current_motivation_type, 0.0)
        engagement += motivation_effect

        # ── Moore (1993): Transactional distance effect ──
        avg_td = self.moore.average(student, state, self.env)
        td_effect = -(avg_td - 0.5) * self._TD_EFFECT_FACTOR
        engagement += td_effect

        # ── Garrison et al. (2000): Community of Inquiry effect ──
        coi = state.coi_state
        coi_effect = (
            coi.social_presence * self._COI_SOCIAL_WEIGHT
            + coi.cognitive_presence * self._COI_COGNITIVE_WEIGHT
            + coi.teaching_presence * self._COI_TEACHING_WEIGHT
            - self._COI_BASELINE_OFFSET
        )
        engagement += coi_effect

        # ── Gonzalez et al. (2025): Academic exhaustion drag ──
        engagement += self.gonzalez.exhaustion_engagement_effect(state)

        # ── Academic outcomes this week ──
        for r in records:
            if r.interaction_type in ("assignment_submit", "exam"):
                if r.quality_score > self._HIGH_QUALITY_THRESHOLD:
                    engagement += self._HIGH_QUALITY_BOOST
                elif r.quality_score < self._LOW_QUALITY_THRESHOLD:
                    engagement -= self._LOW_QUALITY_PENALTY

        # Missed assignments compound (Bäulke: perceived misfit grows)
        if state.missed_assignments_streak >= 2:
            engagement -= self._MISSED_STREAK_PENALTY * min(state.missed_assignments_streak - 1, self._MISSED_STREAK_CAP)

        # ── Exam week stress (Neuroticism moderator) ──
        if context.get("is_exam_week"):
            engagement -= student.personality.neuroticism * self._NEUROTICISM_EXAM_FACTOR

        # ── Kember: Cost-benefit recalculation after major events ──
        has_graded_item = any(
            r.interaction_type in ("assignment_submit", "exam") for r in records
        )
        if context.get("is_exam_week") or state.missed_assignments_streak >= 2 or has_graded_item:
            self.kember.recalculate(student, state, context, records, avg_td,
                                    week=week, total_weeks=self.env.total_weeks,
                                    inst=self.inst)
            # Cost-benefit feeds back into engagement
            engagement += (state.perceived_cost_benefit - 0.5) * self._CB_FEEDBACK_FACTOR

        # ── Persona-based engagement floor (Rovai) ──
        engagement = max(engagement, self.rovai.engagement_floor(student))

        state.current_engagement = float(np.clip(engagement, self._ENGAGEMENT_CLIP_LO, self._ENGAGEMENT_CLIP_HI))

    def summary_statistics(self, states: dict[str, SimulationState]) -> dict[str, Any]:
        total = len(states)
        dropouts = sum(1 for s in states.values() if s.has_dropped_out)
        dropout_weeks = [s.dropout_week for s in states.values() if s.dropout_week]
        final_engagements = [
            s.weekly_engagement_history[-1] if s.weekly_engagement_history else 0
            for s in states.values() if not s.has_dropped_out
        ]
        phase_dist: dict[str | int, int] = {}
        for s in states.values():
            if s.withdrawal_reason is not None:
                key = "unavoidable_withdrawal"
            elif s.has_dropped_out:
                key = 5  # Bäulke phase 5 (decided)
            else:
                key = s.dropout_phase
            phase_dist[key] = phase_dist.get(key, 0) + 1

        # Unavoidable withdrawal breakdown
        withdrawal_reasons: dict[str, int] = {}
        for s in states.values():
            if s.withdrawal_reason is not None:
                withdrawal_reasons[s.withdrawal_reason] = (
                    withdrawal_reasons.get(s.withdrawal_reason, 0) + 1
                )
        withdrawal_count = sum(withdrawal_reasons.values())

        # GPA statistics (only for students with graded items)
        gpa_values = [s.cumulative_gpa for s in states.values() if s.gpa_count > 0]
        mean_final_gpa = float(np.mean(gpa_values)) if gpa_values else None

        return {
            "total_students": total,
            "dropout_count": dropouts,
            "dropout_rate": dropouts / total if total > 0 else 0,
            "mean_dropout_week": float(np.mean(dropout_weeks)) if dropout_weeks else None,
            "std_dropout_week": float(np.std(dropout_weeks)) if dropout_weeks else None,
            "mean_final_engagement": float(np.mean(final_engagements)) if final_engagements else None,
            "std_final_engagement": float(np.std(final_engagements)) if final_engagements else None,
            "mean_final_gpa": mean_final_gpa,
            "retained_students": total - dropouts,
            "dropout_phase_distribution": {
                (f"phase_{k}" if isinstance(k, int) else str(k)): v
                for k, v in sorted(phase_dist.items(), key=lambda x: (isinstance(x[0], str), x[0]))
            },
            "unavoidable_withdrawal_count": withdrawal_count,
            "unavoidable_withdrawal_reasons": withdrawal_reasons,
        }
