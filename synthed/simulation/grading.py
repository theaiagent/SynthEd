"""Configurable grading system for ODL simulation.

Provides :class:`GradingConfig` (frozen dataclass) for institution-level
grading policy, scale conversion, and outcome classification utilities.
Also provides grading orchestration free functions extracted from SimulationEngine.
"""
from __future__ import annotations

import enum
import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .state import SimulationState

logger = logging.getLogger(__name__)

_VALID_COMPONENT_KEYS = frozenset({"exam", "assignment", "forum"})
_VALID_DISTRIBUTIONS = frozenset({"beta", "normal", "uniform"})
_VALID_ASSESSMENT_MODES = frozenset({"mixed", "exam_only", "continuous"})
_VALID_GRADING_METHODS = frozenset({"absolute", "relative"})
_VALID_MISSING_POLICIES = frozenset({"zero", "redistribute"})


class GradingScale(enum.Enum):
    """Supported output scales."""
    SCALE_100 = 100
    SCALE_4 = 4


# Piecewise-linear GPA conversion (OULAD/WES-grounded)
_GPA_BREAKPOINTS: tuple[tuple[float, float], ...] = (
    (0.00, 0.0),
    (0.40, 1.0),
    (0.55, 2.0),
    (0.70, 3.0),
    (0.85, 3.7),
    (1.00, 4.0),
)


@dataclass(frozen=True)
class GradingConfig:
    """Institution-level grading policy. Frozen: use dataclasses.replace()."""

    scale: GradingScale = GradingScale.SCALE_100
    assessment_mode: str = "mixed"
    midterm_weight: float = 0.40
    final_weight: float = 0.60
    midterm_components: dict[str, float] = field(
        default_factory=lambda: {"exam": 0.50, "assignment": 0.30, "forum": 0.20}
    )
    distribution: str = "beta"  # Used by sample_base_quality() (not called by engine)
    dist_alpha: float = 5.0     # Used by sample_base_quality() (not called by engine)
    dist_beta: float = 3.0      # Used by sample_base_quality() (not called by engine)
    grading_method: str = "absolute"
    grade_floor: float = 0.45
    pass_threshold: float = 0.64
    distinction_threshold: float = 0.73
    dual_hurdle: bool = False
    component_pass_thresholds: dict[str, float] = field(default_factory=dict)
    exam_eligibility_threshold: float | None = None
    late_penalty: float = 0.05
    noise_std: float = 0.05  # Used by compute_grade() only (not called by engine)
    missing_policy: str = "zero"

    def __post_init__(self) -> None:
        # Weight sum
        total = self.midterm_weight + self.final_weight
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"midterm_weight + final_weight must sum to 1.0, got {total}")
        # Component sum
        if self.midterm_components:
            comp_total = sum(self.midterm_components.values())
            if not math.isclose(comp_total, 1.0, abs_tol=1e-6):
                raise ValueError(f"midterm_components must sum to 1.0, got {comp_total}")
            invalid = set(self.midterm_components) - _VALID_COMPONENT_KEYS
            if invalid:
                raise ValueError(f"Invalid midterm_components keys: {invalid}. Valid: {_VALID_COMPONENT_KEYS}")
        # Threshold ordering
        if self.distinction_threshold <= self.pass_threshold:
            raise ValueError(
                f"distinction_threshold ({self.distinction_threshold}) must be > "
                f"pass_threshold ({self.pass_threshold})"
            )
        # Numeric ranges
        for name, val, lo, hi in [
            ("grade_floor", self.grade_floor, 0.0, 1.0),
            ("pass_threshold", self.pass_threshold, 0.0, 1.0),
            ("distinction_threshold", self.distinction_threshold, 0.0, 1.0),
            ("noise_std", self.noise_std, 0.0, 1.0),
            ("late_penalty", self.late_penalty, 0.0, 1.0),
            ("midterm_weight", self.midterm_weight, 0.0, 1.0),
            ("final_weight", self.final_weight, 0.0, 1.0),
        ]:
            if not lo <= val <= hi:
                raise ValueError(f"{name}={val} outside [{lo}, {hi}]")
        # Distribution validation
        if self.distribution not in _VALID_DISTRIBUTIONS:
            raise ValueError(f"Unsupported distribution: '{self.distribution}'. Use: {_VALID_DISTRIBUTIONS}")
        if self.distribution == "uniform" and self.dist_alpha >= self.dist_beta:
            raise ValueError(f"Uniform requires dist_alpha < dist_beta, got {self.dist_alpha} >= {self.dist_beta}")
        # Mode validation
        if self.assessment_mode not in _VALID_ASSESSMENT_MODES:
            raise ValueError(f"Invalid assessment_mode: '{self.assessment_mode}'")
        if self.missing_policy not in _VALID_MISSING_POLICIES:
            raise ValueError(f"Invalid missing_policy: '{self.missing_policy}'")
        if self.grading_method not in _VALID_GRADING_METHODS:
            raise ValueError(f"Invalid grading_method: '{self.grading_method}'")
        # Dual-hurdle consistency
        if self.dual_hurdle and not self.component_pass_thresholds:
            raise ValueError("dual_hurdle=True requires at least one entry in component_pass_thresholds")
        # Defensive copy of mutable dicts
        object.__setattr__(self, "midterm_components", dict(self.midterm_components))
        object.__setattr__(self, "component_pass_thresholds", dict(self.component_pass_thresholds))


def piecewise_gpa(quality: float) -> float:
    """Convert 0-1 quality to 0-4.0 GPA using OULAD/WES-grounded breakpoints."""
    quality = float(np.clip(quality, 0.0, 1.0))
    for i in range(1, len(_GPA_BREAKPOINTS)):
        q_lo, g_lo = _GPA_BREAKPOINTS[i - 1]
        q_hi, g_hi = _GPA_BREAKPOINTS[i]
        if quality <= q_hi:
            frac = (quality - q_lo) / (q_hi - q_lo) if q_hi > q_lo else 0.0
            return g_lo + frac * (g_hi - g_lo)
    return _GPA_BREAKPOINTS[-1][1]


def convert_scale(quality: float, scale: GradingScale) -> float:
    """Convert 0-1 quality to output scale."""
    if scale == GradingScale.SCALE_4:
        return piecewise_gpa(quality)
    return quality * scale.value


def classify_outcome(quality: float, config: GradingConfig) -> str:
    """Classify a 0-1 quality into Distinction/Pass/Fail."""
    if quality >= config.distinction_threshold:
        return "Distinction"
    if quality >= config.pass_threshold:
        return "Pass"
    return "Fail"


def compute_grade(
    quality: float,
    config: GradingConfig,
    rng: np.random.Generator | None = None,
) -> float:
    """Apply grade floor, measurement noise, and scale conversion.

    Note: Not called by SimulationEngine. The engine applies grade_floor
    in _record_graded_item and _assign_outcomes separately. Available for
    external use and Sobol analysis.
    """
    graded = config.grade_floor + (1.0 - config.grade_floor) * quality
    if rng is not None and config.noise_std > 0:
        graded += rng.normal(0.0, config.noise_std)
    graded = float(np.clip(graded, 0.0, 1.0))
    return convert_scale(graded, config.scale)


def sample_base_quality(config: GradingConfig, rng: np.random.Generator) -> float:
    """Sample base quality from institution's grade distribution.

    Note: Not called by SimulationEngine. The engine computes quality
    directly from persona traits. Available for external use and future versions.
    """
    if config.distribution == "beta":
        raw = rng.beta(config.dist_alpha, config.dist_beta)
    elif config.distribution == "normal":
        raw = rng.normal(config.dist_alpha, config.dist_beta)
    elif config.distribution == "uniform":
        raw = rng.uniform(config.dist_alpha, config.dist_beta)
    else:
        raise ValueError(f"Unsupported distribution: '{config.distribution}'")
    return float(np.clip(raw, 0.0, 1.0))


_MIN_T_SCORE_N = 30


def apply_relative_grading(raw_scores: list[float]) -> list[float]:
    """Apply t-score standardization (T = 50 + 10 * (X - mu) / sigma).

    Returns 50.0 for single-student, identical-score, or n<2 cases.
    Warns if n < 30.

    Used by engine when grading_method='relative'.
    """
    if len(raw_scores) < 2:
        return [50.0] * len(raw_scores)
    if not all(math.isfinite(s) for s in raw_scores):
        raise ValueError("apply_relative_grading received non-finite score(s)")
    arr = np.array(raw_scores, dtype=float)
    std = float(np.std(arr, ddof=0))  # population std (cohort IS the population)
    if std < 1e-9:
        return [50.0] * len(raw_scores)
    if len(raw_scores) < _MIN_T_SCORE_N:
        logger.warning("T-score with n=%d < %d: results may be unstable", len(raw_scores), _MIN_T_SCORE_N)
    mean = float(np.mean(arr))
    t_scores = 50.0 + 10.0 * (arr - mean) / std
    return [float(np.clip(s, 0.0, 100.0)) for s in t_scores]


def normalize_t_scores(t_scores: list[float]) -> list[float]:
    """Convert t-scores (0-100) to 0-1 scale for classify_outcome."""
    for s in t_scores:
        if not math.isfinite(s):
            raise ValueError(f"normalize_t_scores received non-finite value: {s!r}")
    return [s / 100.0 for s in t_scores]


def calculate_semester_grade(
    config: GradingConfig,
    midterm_exam_scores: list[float],
    assignment_scores: list[float],
    forum_scores: list[float],
    final_score: float | None,
    n_total_assignments: int = 0,
    n_total_forums: int = 0,
) -> float | None:
    """Calculate weighted semester grade.

    Uses n_total_* for correct denominator (submitted 2/4 = sum/4, not sum/2).
    Respects missing_policy and dual_hurdle settings.
    Returns None if final is required but not taken.
    """
    if config.assessment_mode == "exam_only":
        return final_score
    if config.assessment_mode == "continuous":
        # All weight on midterm components, no final needed
        pass
    elif final_score is None:
        return None

    component_data: dict[str, tuple[list[float], int]] = {
        "exam": (midterm_exam_scores, len(midterm_exam_scores)),
        "assignment": (assignment_scores, max(n_total_assignments, len(assignment_scores))),
        "forum": (forum_scores, max(n_total_forums, len(forum_scores))),
    }

    midterm_total = _aggregate_components(
        component_data, config.midterm_components, config.missing_policy,
    )
    if midterm_total is None:
        return None

    semester = midterm_total * config.midterm_weight
    if config.assessment_mode != "continuous" and final_score is not None:
        semester += final_score * config.final_weight

    return semester


def check_dual_hurdle_pass(
    config: GradingConfig,
    midterm_aggregate: float,
    final_score: float | None,
) -> bool:
    """Check if student passes all hurdle requirements. True = passes."""
    if not config.dual_hurdle or not config.component_pass_thresholds:
        return True
    if "midterm" in config.component_pass_thresholds:
        if midterm_aggregate < config.component_pass_thresholds["midterm"]:
            return False
    if "final" in config.component_pass_thresholds:
        if final_score is None or final_score < config.component_pass_thresholds["final"]:
            return False
    return True


# ---------------------------------------------------------------------------
# Grading orchestration — free functions extracted from SimulationEngine
# ---------------------------------------------------------------------------


def _aggregate_components(
    component_data: dict[str, tuple[list[float], int]],
    weights: dict[str, float],
    missing_policy: str = "zero",
) -> float | None:
    """Compute weighted aggregate from component scores.

    Shared by ``_compute_midterm_aggregate`` and ``calculate_semester_grade``.
    When *missing_policy* is ``"redistribute"``, empty components are skipped
    and remaining weights are renormalized.  Returns ``None`` if all
    components are empty under redistribute policy.
    """
    total = 0.0
    active_weight = 0.0
    for comp_name, weight in weights.items():
        scores, n_total = component_data.get(comp_name, ([], 0))
        if not scores:
            if missing_policy == "redistribute":
                continue
            comp_mean = 0.0
        else:
            comp_mean = sum(scores) / max(n_total, 1)
        total += comp_mean * weight
        active_weight += weight

    if missing_policy == "redistribute":
        # active_weight == 0.0 is exact: loop body never entered (all skipped).
        # active_weight < 1.0 is monotone-safe: weights only added, never subtracted.
        if active_weight == 0.0:
            return None
        if active_weight < 1.0:
            total /= active_weight

    return total


def _compute_midterm_aggregate(state: SimulationState, cfg: GradingConfig) -> float:
    """Compute weighted midterm aggregate from component scores."""
    component_data: dict[str, tuple[list[float], int]] = {
        "exam": (state.midterm_exam_scores, len(state.midterm_exam_scores)),
        "assignment": (state.assignment_scores, max(state.n_total_assignments, len(state.assignment_scores))),
        "forum": (state.forum_scores, max(state.n_total_forums, len(state.forum_scores))),
    }
    result = _aggregate_components(component_data, cfg.midterm_components, cfg.missing_policy)
    # None only returned when all components empty under redistribute.
    # has_gradable_work gate in _filter_eligible_states prevents this path.
    assert result is not None, "midterm aggregate should not be None after has_gradable_work gate"
    return result


def _filter_eligible_states(
    states: dict[str, SimulationState],
    cfg: GradingConfig,
    floor: float,
) -> dict[str, float]:
    """Compute semester_grade and filter eligible students.

    Sets outcome for ineligible students (Withdrawn, Fail).
    Returns dict of sid -> raw [0-1] semester_grade, NOT floor-adjusted.
    """
    eligible: dict[str, float] = {}
    for sid, state in states.items():
        if state.has_dropped_out:
            state.outcome = "Withdrawn"
            continue
        # Check all possible grading inputs. gpa_count covers exam_only mode
        # where final_score is the only graded item (not in score lists).
        has_gradable_work = (
            state.midterm_exam_scores
            or state.assignment_scores
            or state.forum_scores
            or state.gpa_count > 0
        )
        if not has_gradable_work:
            state.outcome = "Fail"
            continue
        if cfg.exam_eligibility_threshold is not None:
            midterm_agg = _compute_midterm_aggregate(state, cfg)
            adjusted_midterm = floor + (1.0 - floor) * midterm_agg
            if adjusted_midterm < cfg.exam_eligibility_threshold:
                state.outcome = "Fail"
                continue
        grade = calculate_semester_grade(
            cfg,
            midterm_exam_scores=state.midterm_exam_scores,
            assignment_scores=state.assignment_scores,
            forum_scores=state.forum_scores,
            final_score=state.final_score,
            n_total_assignments=state.n_total_assignments,
            n_total_forums=state.n_total_forums,
        )
        state.semester_grade = grade
        if grade is not None:
            eligible[sid] = grade
        else:
            state.outcome = "Fail"
    return eligible


def _classify_absolute_single(
    state: SimulationState, cfg: GradingConfig, floor: float, grade: float,
) -> str:
    """Classify a single student using absolute grading (floor-adjust + hurdle + classify).

    Returns the outcome string: Distinction, Pass, or Fail.
    """
    adjusted_grade = floor + (1.0 - floor) * grade
    midterm_agg = _compute_midterm_aggregate(state, cfg)
    adjusted_midterm = floor + (1.0 - floor) * midterm_agg
    adjusted_final = (
        (floor + (1.0 - floor) * state.final_score)
        if state.final_score is not None
        else None
    )
    passes_hurdle = check_dual_hurdle_pass(cfg, adjusted_midterm, adjusted_final)
    if passes_hurdle:
        return classify_outcome(adjusted_grade, cfg)
    return "Fail"


def _classify_relative(
    states: dict[str, SimulationState],
    cfg: GradingConfig,
    floor: float,
    sids: list[str],
    normalized: list[float],
) -> None:
    """Classify students using normalized t-scores with dual-hurdle check."""
    for sid, norm_score in zip(sids, normalized, strict=True):
        state = states[sid]
        midterm_agg = _compute_midterm_aggregate(state, cfg)
        adjusted_midterm = floor + (1.0 - floor) * midterm_agg
        adjusted_final = (
            (floor + (1.0 - floor) * state.final_score)
            if state.final_score is not None
            else None
        )
        passes_hurdle = check_dual_hurdle_pass(cfg, adjusted_midterm, adjusted_final)
        if passes_hurdle:
            state.outcome = classify_outcome(norm_score, cfg)
        else:
            state.outcome = "Fail"


def _assign_outcomes_absolute(
    states: dict[str, SimulationState], grading_config: GradingConfig,
) -> None:
    """Assign semester_grade and outcome using absolute grading."""
    floor = grading_config.grade_floor
    eligible = _filter_eligible_states(states, grading_config, floor)
    for sid, grade in eligible.items():
        states[sid].outcome = _classify_absolute_single(
            states[sid], grading_config, floor, grade,
        )


def _assign_outcomes_relative(
    states: dict[str, SimulationState], grading_config: GradingConfig,
) -> None:
    """Assign semester_grade and outcome using relative (t-score) grading.

    Falls back to absolute if fewer than 2 eligible or zero variance.
    """
    floor = grading_config.grade_floor
    eligible = _filter_eligible_states(states, grading_config, floor)

    if len(eligible) < 2:
        logger.warning(
            "Relative grading: fewer than 2 eligible students, "
            "falling back to absolute",
        )
        for sid, grade in eligible.items():
            states[sid].outcome = _classify_absolute_single(
                states[sid], grading_config, floor, grade,
            )
        return

    sids = list(eligible.keys())
    raw_grades = [eligible[sid] for sid in sids]
    t_scores = apply_relative_grading(raw_grades)
    normalized = normalize_t_scores(t_scores)

    if all(abs(t - 50.0) < 1e-9 for t in t_scores):
        logger.warning(
            "Relative grading: zero variance in semester grades, "
            "falling back to absolute",
        )
        for sid, grade in eligible.items():
            states[sid].outcome = _classify_absolute_single(
                states[sid], grading_config, floor, grade,
            )
        return

    _classify_relative(states, grading_config, floor, sids, normalized)


def assign_outcomes(
    states: dict[str, SimulationState],
    grading_config: GradingConfig,
) -> None:
    """Assign semester_grade and outcome to each student at end of run.

    Dispatches to absolute or relative grading based on grading_config.
    """
    if grading_config.grading_method == "relative":
        _assign_outcomes_relative(states, grading_config)
    else:
        _assign_outcomes_absolute(states, grading_config)
