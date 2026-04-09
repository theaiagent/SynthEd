"""
Simulation state dataclasses.

Extracted from engine.py to keep that module focused on orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .theories import ExhaustionState, SDTNeedSatisfaction


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
