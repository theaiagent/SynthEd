"""
MultiSemesterRunner: Orchestrates multi-semester simulations with carry-over.

Between semesters, surviving students receive partial recovery of engagement
and exhaustion while retaining social network connections (with decay).
Dropped-out students (Bäulke phase 5) are permanently removed.

Carry-over mechanics reflect established theoretical anchors:
- Tinto (1975): Social integration decays over breaks but doesn't vanish
- Gonzalez et al. (2025): Exhaustion partially recovers during inter-semester gaps
- Kember (1989): Cost-benefit perception receives small positive adjustment
- Bäulke et al.: Dropout phase regresses by one step during break reflection
- Epstein & Axtell (1996): Network links decay but persist across semesters
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from ..agents.persona import StudentPersona
from .engine import (
    SimulationEngine, InteractionRecord, SimulationState,
    CommunityOfInquiryState,
)
from .social_network import SocialNetwork
from .theories import ExhaustionState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class SemesterCarryOverConfig:
    """
    Configuration for inter-semester carry-over adjustments.

    All values are applied once between consecutive semesters to model
    the break period's effect on student state.
    """

    # Engagement: small positive recovery during break
    engagement_recovery: float = 0.05

    # Cap on engagement recovery (students won't exceed this from recovery alone)
    engagement_recovery_cap: float = 0.80

    # Social integration retention factor (Tinto: connections fade without contact)
    social_integration_decay: float = 0.70

    # Network link strength decay factor (Epstein & Axtell: ties weaken over break)
    network_link_decay: float = 0.30

    # Bäulke: dropout phase regresses by this many steps during break reflection
    dropout_phase_regression: int = 1

    # Gonzalez: exhaustion recovery factor (0-1, fraction of exhaustion removed)
    exhaustion_recovery: float = 0.60

    # Kember: small positive cost-benefit adjustment after break reflection
    cost_benefit_recovery: float = 0.03


# ─────────────────────────────────────────────
# Result containers
# ─────────────────────────────────────────────

@dataclass
class SemesterResult:
    """Result from a single semester's simulation run."""
    semester_index: int
    records: list[InteractionRecord]
    states: dict[str, SimulationState]
    network: SocialNetwork


@dataclass(frozen=True)
class SemesterInterimReport:
    """Progress report generated after each semester when a target range is set."""
    semester: int
    cumulative_dropout_rate: float
    target_range: tuple[float, float] | None
    status: str  # "on_track", "below_target", "above_target"


@dataclass
class MultiSemesterResult:
    """Aggregated result from all semesters."""
    semester_results: list[SemesterResult]
    all_records: list[InteractionRecord]
    final_states: dict[str, SimulationState]
    final_network: SocialNetwork
    interim_reports: list[SemesterInterimReport]


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

class MultiSemesterRunner:
    """
    Orchestrates sequential semester simulations with inter-semester carry-over.

    For each semester:
    1. Run SimulationEngine.run() with the active student population
    2. Collect records and tag them with semester metadata
    3. Filter out permanently dropped students (Bäulke phase 5)
    4. Apply carry-over adjustments to surviving students
    5. Pass adjusted state into the next semester

    The single-semester case (n_semesters=1) is never routed here;
    pipeline.py calls engine.run() directly for that case.
    """

    def __init__(
        self,
        engine: SimulationEngine,
        n_semesters: int,
        weeks_per_semester: int | None = None,
        carry_over: SemesterCarryOverConfig | None = None,
        target_dropout_range: tuple[float, float] | None = None,
    ):
        if n_semesters < 2:
            raise ValueError(
                f"MultiSemesterRunner requires n_semesters >= 2, got {n_semesters}"
            )
        self.engine = engine
        self.n_semesters = n_semesters
        self.weeks_per_semester = weeks_per_semester or engine.env.total_weeks
        self.carry_over = carry_over or SemesterCarryOverConfig()
        self.target_dropout_range = target_dropout_range

    def run(
        self, students: list[StudentPersona],
    ) -> MultiSemesterResult:
        """
        Execute multi-semester simulation.

        Returns:
            MultiSemesterResult with per-semester and aggregated data.
        """
        semester_results: list[SemesterResult] = []
        all_records: list[InteractionRecord] = []
        interim_reports: list[SemesterInterimReport] = []
        total_students = len(students)

        active_students = list(students)
        state_overrides: dict[str, dict[str, Any]] | None = None
        network: SocialNetwork | None = None

        for sem_idx in range(self.n_semesters):
            semester_num = sem_idx + 1
            week_offset = sem_idx * self.weeks_per_semester

            logger.info(
                "  Semester %d/%d: %d active students, week offset %d",
                semester_num, self.n_semesters, len(active_students), week_offset,
            )

            # Run this semester
            records, states, sem_network = self.engine.run(
                active_students,
                weeks=self.weeks_per_semester,
                initial_state_overrides=state_overrides,
                initial_network=network,
            )

            # Offset week numbers and tag with semester metadata
            for record in records:
                record.week += week_offset
                record.metadata["semester"] = semester_num

            # Offset dropout_week in states
            for state in states.values():
                if state.dropout_week is not None:
                    state.dropout_week += week_offset

            semester_results.append(SemesterResult(
                semester_index=sem_idx,
                records=list(records),
                states=dict(states),
                network=sem_network,
            ))
            all_records.extend(records)

            # Compute interim report when a target range is configured
            if self.target_dropout_range is not None:
                interim = _build_interim_report(
                    semester_num, semester_results, total_students,
                    self.target_dropout_range,
                )
                interim_reports.append(interim)
                logger.info(
                    "  Semester %d interim: cumulative dropout %.1f%% — %s",
                    semester_num,
                    interim.cumulative_dropout_rate * 100,
                    interim.status,
                )

            # After the last semester, no carry-over needed
            if sem_idx == self.n_semesters - 1:
                break

            # Apply carry-over for next semester
            active_students, state_overrides, network = self._apply_carry_over(
                active_students, states, sem_network, self.carry_over,
            )

            logger.info(
                "  Carry-over: %d students continuing to semester %d",
                len(active_students), semester_num + 1,
            )

        # Build final aggregated states: include ALL students across semesters.
        # Earlier semesters' states are used for students who dropped out then;
        # later semesters override for students who survived.
        final_states: dict[str, SimulationState] = {}
        for sem_result in semester_results:
            for sid, state in sem_result.states.items():
                final_states[sid] = state
        final_network = semester_results[-1].network

        return MultiSemesterResult(
            semester_results=semester_results,
            all_records=all_records,
            final_states=final_states,
            final_network=final_network,
            interim_reports=interim_reports,
        )

    @staticmethod
    def _apply_carry_over(
        students: list[StudentPersona],
        states: dict[str, SimulationState],
        network: SocialNetwork,
        config: SemesterCarryOverConfig,
    ) -> tuple[list[StudentPersona], dict[str, dict[str, Any]], SocialNetwork]:
        """
        Apply inter-semester carry-over adjustments.

        Returns:
            Tuple of (new student list, state overrides dict, carried-over network).
        """
        surviving_students: list[StudentPersona] = []
        overrides: dict[str, dict[str, Any]] = {}

        for student in students:
            state = states.get(student.id)
            if state is None:
                continue

            # Filter out permanently dropped students (Bäulke phase 5)
            # or students who withdrew due to unavoidable life events
            if state.dropout_phase >= 5 or state.withdrawal_reason is not None:
                continue

            # Create carry-over persona (immutable: use dataclasses.replace)
            new_persona = _create_carry_over_persona(student, state, config)
            surviving_students.append(new_persona)

            # Build state overrides for the next semester's initialization
            overrides[student.id] = _build_state_overrides(state, config)

        # Decay network links for the inter-semester gap
        # (heavier decay than weekly: models the break period)
        carried_network = network  # reuse the same network object
        carried_network.decay_links(decay_rate=config.network_link_decay)

        return surviving_students, overrides, carried_network

    # summary_statistics helper removed — engine.summary_statistics handles it


# ─────────────────────────────────────────────
# Pure helper functions (no mutation)
# ─────────────────────────────────────────────

def _create_carry_over_persona(
    original: StudentPersona,
    state: SimulationState,
    config: SemesterCarryOverConfig,
) -> StudentPersona:
    """
    Create a new StudentPersona for the next semester using dataclasses.replace().

    Carries forward evolved integration values while keeping
    immutable traits (personality, demographics) unchanged.
    """
    # Social integration decays over break (Tinto)
    new_social_integration = float(np.clip(
        state.social_integration * config.social_integration_decay,
        0.01, 0.95,
    ))

    # Academic integration carries forward directly
    new_academic_integration = float(np.clip(
        state.academic_integration, 0.01, 0.95,
    ))

    # Engagement recovers slightly during break
    recovered_engagement = float(np.clip(
        state.current_engagement + config.engagement_recovery,
        0.01, config.engagement_recovery_cap,
    ))

    # Cost-benefit gets small positive adjustment (Kember: break reflection)
    new_cost_benefit = float(np.clip(
        state.perceived_cost_benefit + config.cost_benefit_recovery,
        0.01, 0.95,
    ))

    return replace(
        original,
        academic_integration=new_academic_integration,
        social_integration=new_social_integration,
        base_engagement_probability=recovered_engagement,
        perceived_cost_benefit=new_cost_benefit,
    )


def _build_state_overrides(
    state: SimulationState,
    config: SemesterCarryOverConfig,
) -> dict[str, Any]:
    """
    Build a dict of state attribute overrides for the next semester.

    These overrides are applied after SimulationEngine initializes states
    from persona attributes, allowing evolved values to carry forward.
    """
    # Dropout phase regresses during break (Bäulke: reflection period)
    new_dropout_phase = max(0, state.dropout_phase - config.dropout_phase_regression)

    # Exhaustion partially recovers (Gonzalez)
    new_exhaustion_level = float(np.clip(
        state.exhaustion.exhaustion_level * (1.0 - config.exhaustion_recovery),
        0.0, 1.0,
    ))

    # CoI state resets partially (new semester, new course interactions)
    new_social_presence = float(np.clip(
        state.coi_state.social_presence * 0.6, 0.01, 0.95,
    ))
    new_cognitive_presence = float(np.clip(
        state.coi_state.cognitive_presence * 0.7, 0.01, 0.95,
    ))
    new_teaching_presence = float(np.clip(
        state.coi_state.teaching_presence * 0.8, 0.01, 0.95,
    ))

    # Build new nested objects (immutable creation, no mutation)
    new_exhaustion = ExhaustionState(
        exhaustion_level=new_exhaustion_level,
        recovery_capacity=state.exhaustion.recovery_capacity,
    )
    new_coi = CommunityOfInquiryState(
        social_presence=new_social_presence,
        cognitive_presence=new_cognitive_presence,
        teaching_presence=new_teaching_presence,
    )

    return {
        "dropout_phase": new_dropout_phase,
        "has_dropped_out": False,
        "dropout_week": None,
        "withdrawal_reason": None,
        "missed_assignments_streak": 0,
        "weekly_engagement_history": [],
        "memory": [],
        "exhaustion": new_exhaustion,
        "coi_state": new_coi,
    }


def _build_interim_report(
    semester_num: int,
    semester_results: list[SemesterResult],
    total_students: int,
    target_range: tuple[float, float],
) -> SemesterInterimReport:
    """Compute cumulative dropout rate and status after a semester."""
    # Count unique dropped-out students across all semesters so far
    dropped_ids: set[str] = set()
    for sem_result in semester_results:
        for sid, state in sem_result.states.items():
            if state.has_dropped_out:
                dropped_ids.add(sid)

    cumulative_rate = len(dropped_ids) / total_students if total_students > 0 else 0.0
    lo, hi = target_range

    if cumulative_rate < lo:
        status = "below_target"
    elif cumulative_rate > hi:
        status = "above_target"
    else:
        status = "on_track"

    return SemesterInterimReport(
        semester=semester_num,
        cumulative_dropout_rate=round(cumulative_rate, 4),
        target_range=target_range,
        status=status,
    )
