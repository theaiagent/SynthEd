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

import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..agents.persona import StudentPersona
from .engine_config import EngineConfig
from .environment import ODLEnvironment
from .grading import (
    GradingConfig,
    calculate_semester_grade,
    check_dual_hurdle_pass,
    classify_outcome as _classify_outcome,
)
from .institutional import InstitutionalConfig, scale_by
from .social_network import SocialNetwork
from .statistics import summary_statistics as _summary_statistics
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

logger = logging.getLogger(__name__)


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
    # ── Grading state ──
    midterm_exam_scores: list[float] = field(default_factory=list)
    assignment_scores: list[float] = field(default_factory=list)
    forum_scores: list[float] = field(default_factory=list)
    final_score: float | None = None
    semester_grade: float | None = None  # raw quality [0-1], NOT floor-adjusted
    outcome: str | None = None
    n_total_assignments: int = 0
    n_total_forums: int = 0

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

    def __init__(
        self,
        environment: ODLEnvironment,
        llm_client: LLMClient | None = None,
        seed: int = 42,
        mode: str = "rule_based",
        unavoidable_withdrawal_rate: float = 0.0,
        institutional_config: InstitutionalConfig | None = None,
        grading_config: GradingConfig | None = None,
        engine_config: EngineConfig | None = None,
    ):
        self.env = environment
        self.cfg = engine_config or EngineConfig()
        self.inst = institutional_config or InstitutionalConfig()
        self.grading_config = grading_config or GradingConfig()
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
            self.network.decay_links(decay_rate=self.cfg._NETWORK_DECAY_RATE)
            self.epstein_axtell.update_network(week, week_records_by_student, self.network, rng=self.rng)
            for student in students:
                state = states[student.id]
                if state.has_dropped_out:
                    continue
                self.epstein_axtell.apply_peer_influence(student, state, states, self.network)
                # CoI social_presence boosted by network degree
                degree = self.network.get_degree(student.id)
                state.coi_state.social_presence += min(degree * self.cfg._COI_DEGREE_FACTOR, self.cfg._COI_DEGREE_CAP)
                state.coi_state.social_presence = float(
                    np.clip(state.coi_state.social_presence, self.cfg._ENGAGEMENT_CLIP_LO, self.cfg._ENGAGEMENT_CLIP_HI)
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

        # ── End-of-run: semester grade and outcome assignment ──
        self._assign_outcomes(states)

        return all_records, states, self.network

    def _record_graded_item(self, state: SimulationState, quality: float) -> None:
        """Update cumulative GPA with a graded item (assignment or exam).

        Applies a structural grade floor before scaling to GPA. In real courses
        students earn baseline marks from assignment templates, partial credit,
        and easy initial portions — this floor captures that effect.

        Note: In exam_only mode, cumulative_gpa includes all graded items
        (midterm exams + assignments) while semester_grade uses only final_score.
        """
        floor = self.grading_config.grade_floor
        graded = floor + (1.0 - floor) * quality
        state.gpa_points_sum += graded * self.cfg._GPA_SCALE
        state.gpa_count += 1
        state.cumulative_gpa = state.gpa_points_sum / state.gpa_count
        state.perceived_mastery_sum += quality
        state.perceived_mastery_count += 1

    def _compute_midterm_aggregate(self, state: SimulationState, cfg: GradingConfig) -> float:
        """Compute weighted midterm aggregate from component scores."""
        component_data: dict[str, tuple[list[float], int]] = {
            "exam": (state.midterm_exam_scores, len(state.midterm_exam_scores)),
            "assignment": (state.assignment_scores, max(state.n_total_assignments, len(state.assignment_scores))),
            "forum": (state.forum_scores, max(state.n_total_forums, len(state.forum_scores))),
        }
        total = 0.0
        for comp_name, weight in cfg.midterm_components.items():
            scores, n = component_data.get(comp_name, ([], 0))
            comp_mean = sum(scores) / max(n, 1) if scores else 0.0
            total += comp_mean * weight
        return total

    def _assign_outcomes(self, states: dict[str, SimulationState]) -> None:
        """Assign semester_grade and outcome to each student at end of run.

        Thresholds (pass_threshold, distinction_threshold, component_pass_thresholds)
        are on the transcript scale (floor-adjusted). Raw quality is converted via
        ``floor + (1 - floor) * raw`` before comparison.
        """
        cfg = self.grading_config
        floor = cfg.grade_floor
        for state in states.values():
            if state.has_dropped_out:
                state.outcome = "Withdrawn"
                continue
            if state.gpa_count == 0:
                state.outcome = "Fail"
                continue

            # Exam eligibility check (on floor-adjusted scale)
            if cfg.exam_eligibility_threshold is not None:
                midterm_agg = self._compute_midterm_aggregate(state, cfg)
                adjusted_midterm = floor + (1.0 - floor) * midterm_agg
                if adjusted_midterm < cfg.exam_eligibility_threshold:
                    state.outcome = "Fail"
                    continue

            state.semester_grade = calculate_semester_grade(
                cfg,
                midterm_exam_scores=state.midterm_exam_scores,
                assignment_scores=state.assignment_scores,
                forum_scores=state.forum_scores,
                final_score=state.final_score,
                n_total_assignments=state.n_total_assignments,
                n_total_forums=state.n_total_forums,
            )

            if state.semester_grade is not None:
                # Floor-adjust for classification (thresholds are on transcript scale)
                adjusted_grade = floor + (1.0 - floor) * state.semester_grade

                # Dual-hurdle check (also on floor-adjusted scale)
                midterm_agg = self._compute_midterm_aggregate(state, cfg)
                adjusted_midterm = floor + (1.0 - floor) * midterm_agg
                adjusted_final = (floor + (1.0 - floor) * state.final_score) if state.final_score is not None else None
                passes_hurdle = check_dual_hurdle_pass(cfg, adjusted_midterm, adjusted_final)

                if passes_hurdle:
                    state.outcome = _classify_outcome(adjusted_grade, cfg)
                else:
                    state.outcome = "Fail"
            else:
                state.outcome = "Fail"

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
            # Order preserved for RNG determinism
            records.extend(self._sim_lms_logins(student, state, course, engagement, week))
            records.extend(self._sim_forum_activity(student, state, course, engagement, week))
            records.extend(self._sim_assignment(student, state, course, engagement, week))
            records.extend(self._sim_live_session(student, state, course, engagement, week))
            records.extend(self._sim_exam(student, state, course, engagement, week))
        return records

    def _sim_lms_logins(
        self, student: StudentPersona, state: SimulationState,
        course: Any, engagement: float, week: int,
    ) -> list[InteractionRecord]:
        """LMS Logins (Rovai: accessibility)."""
        records: list[InteractionRecord] = []
        effective_login_floor = scale_by(self.cfg._LOGIN_LITERACY_FLOOR, self.inst.technology_quality)  # [inst: technology_quality]
        login_rate = engagement * self.cfg._LOGIN_ENG_MULTIPLIER * (effective_login_floor + self.cfg._LOGIN_LITERACY_SCALE * student.digital_literacy)
        n_logins = max(0, int(self.rng.poisson(login_rate)))
        for _ in range(n_logins):
            if student.is_employed:
                hour = float(self.rng.choice([*range(18, 24), *range(0, 2)]) + self.rng.uniform(0, 1))
            else:
                hour = float(self.rng.uniform(8, 22))
            day = self.rng.integers(0, 7)
            duration = float(max(self.cfg._LOGIN_DURATION_MIN, self.rng.normal(self.cfg._LOGIN_DURATION_MEAN_FACTOR * engagement, self.cfg._LOGIN_DURATION_STD)))
            records.append(InteractionRecord(
                student_id=student.id, week=week, course_id=course.id,
                interaction_type="lms_login",
                timestamp_offset_hours=day * 24 + hour,
                duration_minutes=round(duration, 1),
                metadata={"device": student.device_type},
            ))
        return records

    def _sim_forum_activity(
        self, student: StudentPersona, state: SimulationState,
        course: Any, engagement: float, week: int,
    ) -> list[InteractionRecord]:
        """Forum Activity (Tinto: social integration)."""
        records: list[InteractionRecord] = []
        if not course.has_forum:
            return records
        effective_forum_floor = scale_by(self.cfg._FORUM_READ_LITERACY_FLOOR, self.inst.technology_quality)  # [inst: technology_quality]
        read_prob = engagement * self.cfg._FORUM_READ_ENG_FACTOR * (effective_forum_floor + self.cfg._FORUM_READ_LITERACY_SCALE * student.digital_literacy)
        if self.rng.random() < read_prob:
            records.append(InteractionRecord(
                student_id=student.id, week=week, course_id=course.id,
                interaction_type="forum_read",
                duration_minutes=round(float(self.rng.exponential(self.cfg._FORUM_READ_EXP_MEAN)), 1),
            ))
        # Posting: extraversion + social integration drive this
        post_prob = (engagement * self.cfg._FORUM_POST_ENG_FACTOR
                     * (self.cfg._FORUM_POST_EXTRA_FLOOR + self.cfg._FORUM_POST_EXTRA_WEIGHT * student.personality.extraversion
                        + self.cfg._FORUM_POST_SOCIAL_WEIGHT * state.social_integration))
        if self.rng.random() < post_prob:
            # Forum post quality (social engagement proxy)
            forum_quality = float(np.clip(
                0.4 * engagement + 0.3 * student.social_integration + 0.3 * self.rng.normal(0.5, 0.15),
                0.0, 1.0
            ))
            state.forum_scores.append(forum_quality)
            state.n_total_forums += 1
            records.append(InteractionRecord(
                student_id=student.id, week=week, course_id=course.id,
                interaction_type="forum_post",
                duration_minutes=round(float(self.rng.normal(self.cfg._FORUM_POST_DURATION_MEAN, self.cfg._FORUM_POST_DURATION_STD)), 1),
                quality_score=round(forum_quality, 2),
                metadata={"post_length": int(self.rng.normal(self.cfg._FORUM_POST_LENGTH_MEAN, self.cfg._FORUM_POST_LENGTH_STD))},
            ))
        return records

    def _sim_assignment(
        self, student: StudentPersona, state: SimulationState,
        course: Any, engagement: float, week: int,
    ) -> list[InteractionRecord]:
        """Assignment Submission (Rovai: self-regulation + time management)."""
        records: list[InteractionRecord] = []
        if week not in course.assignment_weeks:
            return records
        submit_prob = (engagement
                       * (self.cfg._ASSIGN_SUBMIT_BASE + self.cfg._ASSIGN_SUBMIT_REG_WEIGHT * student.self_regulation
                          + self.cfg._ASSIGN_SUBMIT_TIME_WEIGHT * student.time_management
                          + self.cfg._ASSIGN_SUBMIT_CONSC_WEIGHT * student.personality.conscientiousness))
        submitted = self.rng.random() < submit_prob
        if submitted:
            quality = float(np.clip(
                scale_by(self.cfg._ASSIGN_GPA_WEIGHT, self.inst.instructional_design_quality,
                         self.cfg._INST_QUALITY_SCALE_LOW, self.cfg._INST_QUALITY_SCALE_HIGH)
                * (student.prior_gpa / self.cfg._GPA_SCALE)
                + scale_by(self.cfg._ASSIGN_ENG_WEIGHT, self.inst.instructional_design_quality,
                           self.cfg._INST_QUALITY_SCALE_LOW, self.cfg._INST_QUALITY_SCALE_HIGH)
                * engagement
                + self.cfg._ASSIGN_EFFICACY_WEIGHT * student.self_efficacy
                + self.cfg._ASSIGN_READING_WEIGHT * student.academic_reading_writing
                + self.cfg._ASSIGN_NOISE_WEIGHT * self.rng.normal(0.5, self.cfg._ASSIGN_NOISE_STD),
                0.0, 1.0
            ))
            is_late = self.rng.random() > student.time_management
            if is_late:
                quality = max(0.0, quality - self.grading_config.late_penalty)
            records.append(InteractionRecord(
                student_id=student.id, week=week, course_id=course.id,
                interaction_type="assignment_submit",
                quality_score=round(quality, 2),
                metadata={"is_late": is_late, "assignment_week": week},
            ))
            self._record_graded_item(state, quality)
            state.assignment_scores.append(quality)
            state.n_total_assignments += 1
            state.missed_assignments_streak = 0
            state.memory.append({"week": week, "event_type": "assignment",
                                 "details": f"Submitted {'late ' if is_late else ''}assignment for {course.id} ({quality:.0%})",
                                 "impact": quality - 0.5})
        else:
            state.n_total_assignments += 1
            state.missed_assignments_streak += 1
            state.memory.append({"week": week, "event_type": "missed_assignment",
                                 "details": f"Missed assignment for {course.id} (streak: {state.missed_assignments_streak})",
                                 "impact": self.cfg._MISSED_IMPACT})
        return records

    def _sim_live_session(
        self, student: StudentPersona, state: SimulationState,
        course: Any, engagement: float, week: int,
    ) -> list[InteractionRecord]:
        """Live Sessions."""
        records: list[InteractionRecord] = []
        if not course.has_live_sessions:
            return records
        attend_prob = engagement * self.cfg._LIVE_ENG_FACTOR * student.time_management
        if student.is_employed:
            attend_prob *= self.cfg._LIVE_EMPLOYED_PENALTY  # Bean & Metzner: work conflict
        if self.rng.random() < attend_prob:
            records.append(InteractionRecord(
                student_id=student.id, week=week, course_id=course.id,
                interaction_type="live_session",
                duration_minutes=round(float(self.rng.normal(self.cfg._LIVE_DURATION_MEAN, self.cfg._LIVE_DURATION_STD)), 1),
            ))
        return records

    def _sim_exam(
        self, student: StudentPersona, state: SimulationState,
        course: Any, engagement: float, week: int,
    ) -> list[InteractionRecord]:
        """Exams."""
        records: list[InteractionRecord] = []
        if week != course.midterm_week and week != course.final_week:
            return records
        exam_type = "midterm" if week == course.midterm_week else "final"
        take_prob = self.cfg._EXAM_TAKE_HIGH_ENG_PROB if engagement > self.cfg._EXAM_TAKE_ENG_THRESHOLD else engagement * self.cfg._EXAM_TAKE_LOW_MULTIPLIER
        if self.rng.random() < take_prob:
            exam_quality = float(np.clip(
                scale_by(self.cfg._EXAM_GPA_WEIGHT, self.inst.instructional_design_quality,
                         self.cfg._INST_QUALITY_SCALE_LOW, self.cfg._INST_QUALITY_SCALE_HIGH)
                * (student.prior_gpa / self.cfg._GPA_SCALE)
                + scale_by(self.cfg._EXAM_ENG_WEIGHT, self.inst.instructional_design_quality,
                           self.cfg._INST_QUALITY_SCALE_LOW, self.cfg._INST_QUALITY_SCALE_HIGH)
                * engagement
                + self.cfg._EXAM_EFFICACY_WEIGHT * student.self_efficacy
                + self.cfg._EXAM_REG_WEIGHT * student.self_regulation
                + self.cfg._EXAM_READING_WEIGHT * student.academic_reading_writing
                + self.cfg._EXAM_NOISE_WEIGHT * self.rng.normal(0.5, self.cfg._EXAM_NOISE_STD),
                0.0, 1.0
            ))
            records.append(InteractionRecord(
                student_id=student.id, week=week, course_id=course.id,
                interaction_type="exam",
                quality_score=round(exam_quality, 2),
                metadata={"exam_type": exam_type},
            ))
            self._record_graded_item(state, exam_quality)
            if exam_type == "midterm":
                state.midterm_exam_scores.append(exam_quality)
            elif exam_type == "final":
                state.final_score = exam_quality
            state.memory.append({"week": week, "event_type": "exam",
                                 "details": f"{exam_type.title()} for {course.id} ({exam_quality:.0%})",
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
        decay_attenuation = 1.0 / (1.0 + self.cfg._DECAY_DAMPING_FACTOR * (week - 1) ** 0.5)

        # ── Tinto: Integration effect ──
        integration_effect = (
            state.academic_integration * self.cfg._TINTO_ACADEMIC_WEIGHT
            + state.social_integration * self.cfg._TINTO_SOCIAL_WEIGHT
            - self.cfg._TINTO_DECAY_BASE * decay_attenuation
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
            "intrinsic": self.cfg._MOTIVATION_INTRINSIC_BOOST, "extrinsic": 0.0, "amotivation": -self.cfg._MOTIVATION_AMOTIVATION_PENALTY
        }.get(state.current_motivation_type, 0.0)
        engagement += motivation_effect

        # ── Moore (1993): Transactional distance effect ──
        avg_td = self.moore.average(student, state, self.env)
        td_effect = -(avg_td - 0.5) * self.cfg._TD_EFFECT_FACTOR
        engagement += td_effect

        # ── Garrison et al. (2000): Community of Inquiry effect ──
        coi = state.coi_state
        coi_effect = (
            coi.social_presence * self.cfg._COI_SOCIAL_WEIGHT
            + coi.cognitive_presence * self.cfg._COI_COGNITIVE_WEIGHT
            + coi.teaching_presence * self.cfg._COI_TEACHING_WEIGHT
            - self.cfg._COI_BASELINE_OFFSET
        )
        engagement += coi_effect

        # ── Gonzalez et al. (2025): Academic exhaustion drag ──
        engagement += self.gonzalez.exhaustion_engagement_effect(state)

        # ── Academic outcomes this week ──
        for r in records:
            if r.interaction_type in ("assignment_submit", "exam"):
                if r.quality_score > self.cfg._HIGH_QUALITY_THRESHOLD:
                    engagement += self.cfg._HIGH_QUALITY_BOOST
                elif r.quality_score < self.cfg._LOW_QUALITY_THRESHOLD:
                    engagement -= self.cfg._LOW_QUALITY_PENALTY

        # Missed assignments compound (Bäulke: perceived misfit grows)
        if state.missed_assignments_streak >= 2:
            engagement -= self.cfg._MISSED_STREAK_PENALTY * min(state.missed_assignments_streak - 1, self.cfg._MISSED_STREAK_CAP)

        # ── Exam week stress (Neuroticism moderator) ──
        if context.get("is_exam_week"):
            engagement -= student.personality.neuroticism * self.cfg._NEUROTICISM_EXAM_FACTOR

        # ── Kember: Cost-benefit recalculation after major events ──
        has_graded_item = any(
            r.interaction_type in ("assignment_submit", "exam") for r in records
        )
        if context.get("is_exam_week") or state.missed_assignments_streak >= 2 or has_graded_item:
            self.kember.recalculate(student, state, context, records, avg_td,
                                    week=week, total_weeks=self.env.total_weeks,
                                    inst=self.inst)
            # Cost-benefit feeds back into engagement
            engagement += (state.perceived_cost_benefit - 0.5) * self.cfg._CB_FEEDBACK_FACTOR

        # ── Persona-based engagement floor (Rovai) ──
        engagement = max(engagement, self.rovai.engagement_floor(student))

        state.current_engagement = float(np.clip(engagement, self.cfg._ENGAGEMENT_CLIP_LO, self.cfg._ENGAGEMENT_CLIP_HI))

    def summary_statistics(self, states: dict[str, SimulationState]) -> dict[str, Any]:
        """Compute aggregate statistics from simulation states."""
        return _summary_statistics(states, self.grading_config.scale.value)
