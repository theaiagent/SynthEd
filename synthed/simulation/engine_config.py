"""EngineConfig: frozen dataclass holding all SimulationEngine constants.

Mirrors the class-level ``_UPPERCASE`` constants formerly defined in
``engine.py``.  Frozen — use ``dataclasses.replace()`` for overrides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    """Simulation engine tuning constants.  Frozen: use dataclasses.replace()."""

    # ── LMS login generation ──
    _LOGIN_ENG_MULTIPLIER: float = 5.0
    _LOGIN_LITERACY_FLOOR: float = 0.5
    _LOGIN_LITERACY_SCALE: float = 0.5
    _LOGIN_DURATION_MEAN_FACTOR: float = 25.0
    _LOGIN_DURATION_STD: float = 12.0
    _LOGIN_DURATION_MIN: float = 5.0

    # ── Forum activity ──
    _FORUM_READ_ENG_FACTOR: float = 0.7
    _FORUM_READ_LITERACY_FLOOR: float = 0.5
    _FORUM_READ_LITERACY_SCALE: float = 0.5
    _FORUM_READ_EXP_MEAN: float = 10.0
    _FORUM_POST_ENG_FACTOR: float = 0.25
    _FORUM_POST_EXTRA_FLOOR: float = 0.4
    _FORUM_POST_EXTRA_WEIGHT: float = 0.3
    _FORUM_POST_SOCIAL_WEIGHT: float = 0.3
    _FORUM_POST_DURATION_MEAN: float = 15.0
    _FORUM_POST_DURATION_STD: float = 5.0
    _FORUM_POST_LENGTH_MEAN: float = 80.0
    _FORUM_POST_LENGTH_STD: float = 30.0

    # ── Assignment submission & quality ──
    _ASSIGN_SUBMIT_REG_WEIGHT: float = 0.3
    _ASSIGN_SUBMIT_TIME_WEIGHT: float = 0.2
    _ASSIGN_SUBMIT_CONSC_WEIGHT: float = 0.2
    _ASSIGN_SUBMIT_BASE: float = 0.3
    _ASSIGN_GPA_WEIGHT: float = 0.25
    _ASSIGN_ENG_WEIGHT: float = 0.25
    _ASSIGN_EFFICACY_WEIGHT: float = 0.20
    _ASSIGN_READING_WEIGHT: float = 0.15
    _ASSIGN_NOISE_WEIGHT: float = 0.15
    _ASSIGN_NOISE_STD: float = 0.15
    _GPA_SCALE: float = 4.0
    _MISSED_IMPACT: float = -0.3

    # ── Live sessions ──
    _LIVE_ENG_FACTOR: float = 0.5
    _LIVE_EMPLOYED_PENALTY: float = 0.4
    _LIVE_DURATION_MEAN: float = 55.0
    _LIVE_DURATION_STD: float = 10.0

    # ── Exams ──
    _EXAM_TAKE_HIGH_ENG_PROB: float = 0.95
    _EXAM_TAKE_ENG_THRESHOLD: float = 0.3
    _EXAM_TAKE_LOW_MULTIPLIER: float = 2.5
    _EXAM_GPA_WEIGHT: float = 0.20
    _EXAM_ENG_WEIGHT: float = 0.20
    _EXAM_EFFICACY_WEIGHT: float = 0.20
    _EXAM_REG_WEIGHT: float = 0.15
    _EXAM_READING_WEIGHT: float = 0.10
    _EXAM_NOISE_WEIGHT: float = 0.15
    _EXAM_NOISE_STD: float = 0.18

    # ── Engagement update ──
    _DECAY_DAMPING_FACTOR: float = 0.5
    _TINTO_ACADEMIC_WEIGHT: float = 0.06
    _TINTO_SOCIAL_WEIGHT: float = 0.02
    _TINTO_DECAY_BASE: float = 0.05
    _MOTIVATION_INTRINSIC_BOOST: float = 0.02
    _MOTIVATION_AMOTIVATION_PENALTY: float = 0.025
    _TD_EFFECT_FACTOR: float = 0.03
    _COI_SOCIAL_WEIGHT: float = 0.01
    _COI_COGNITIVE_WEIGHT: float = 0.02
    _COI_TEACHING_WEIGHT: float = 0.01
    _COI_BASELINE_OFFSET: float = 0.02
    _HIGH_QUALITY_THRESHOLD: float = 0.7
    _HIGH_QUALITY_BOOST: float = 0.025
    _LOW_QUALITY_THRESHOLD: float = 0.3
    _LOW_QUALITY_PENALTY: float = 0.035
    _MISSED_STREAK_PENALTY: float = 0.04
    _MISSED_STREAK_CAP: int = 3
    _NEUROTICISM_EXAM_FACTOR: float = 0.04
    _CB_FEEDBACK_FACTOR: float = 0.02
    _ENGAGEMENT_CLIP_LO: float = 0.01
    _ENGAGEMENT_CLIP_HI: float = 0.99

    # ── Institutional quality effect on grades ──
    _INST_QUALITY_SCALE_LOW: float = 0.7
    _INST_QUALITY_SCALE_HIGH: float = 1.3

    # ── Social network ──
    _NETWORK_DECAY_RATE: float = 0.02
    _COI_DEGREE_FACTOR: float = 0.005
    _COI_DEGREE_CAP: float = 0.03

    def __post_init__(self) -> None:
        # Ordering constraints
        if self._ENGAGEMENT_CLIP_LO >= self._ENGAGEMENT_CLIP_HI:
            raise ValueError(
                f"_ENGAGEMENT_CLIP_LO ({self._ENGAGEMENT_CLIP_LO}) must be < "
                f"_ENGAGEMENT_CLIP_HI ({self._ENGAGEMENT_CLIP_HI})"
            )
        if self._LOW_QUALITY_THRESHOLD >= self._HIGH_QUALITY_THRESHOLD:
            raise ValueError(
                f"_LOW_QUALITY_THRESHOLD ({self._LOW_QUALITY_THRESHOLD}) must be < "
                f"_HIGH_QUALITY_THRESHOLD ({self._HIGH_QUALITY_THRESHOLD})"
            )
        if self._INST_QUALITY_SCALE_LOW >= self._INST_QUALITY_SCALE_HIGH:
            raise ValueError(
                f"_INST_QUALITY_SCALE_LOW ({self._INST_QUALITY_SCALE_LOW}) must be < "
                f"_INST_QUALITY_SCALE_HIGH ({self._INST_QUALITY_SCALE_HIGH})"
            )
        # Positive constraints
        if self._MISSED_STREAK_CAP <= 0:
            raise ValueError(f"_MISSED_STREAK_CAP must be > 0, got {self._MISSED_STREAK_CAP}")
        if self._GPA_SCALE <= 0:
            raise ValueError(f"_GPA_SCALE must be > 0, got {self._GPA_SCALE}")
        if self._LOGIN_DURATION_MIN < 0:
            raise ValueError(f"_LOGIN_DURATION_MIN must be positive, got {self._LOGIN_DURATION_MIN}")
        # Weight sum constraints (assignment quality)
        _assign_sum = (self._ASSIGN_GPA_WEIGHT + self._ASSIGN_ENG_WEIGHT
                       + self._ASSIGN_EFFICACY_WEIGHT + self._ASSIGN_READING_WEIGHT
                       + self._ASSIGN_NOISE_WEIGHT)
        if not math.isclose(_assign_sum, 1.0, rel_tol=1e-9):
            raise ValueError(f"Assignment quality weights must sum to 1.0, got {_assign_sum}")
        _exam_sum = (self._EXAM_GPA_WEIGHT + self._EXAM_ENG_WEIGHT
                     + self._EXAM_EFFICACY_WEIGHT + self._EXAM_REG_WEIGHT
                     + self._EXAM_READING_WEIGHT + self._EXAM_NOISE_WEIGHT)
        if not math.isclose(_exam_sum, 1.0, rel_tol=1e-9):
            raise ValueError(f"Exam quality weights must sum to 1.0, got {_exam_sum}")
        # Submit probability cap
        _submit_sum = (self._ASSIGN_SUBMIT_BASE + self._ASSIGN_SUBMIT_REG_WEIGHT
                       + self._ASSIGN_SUBMIT_TIME_WEIGHT + self._ASSIGN_SUBMIT_CONSC_WEIGHT)
        if _submit_sum > 1.0 + 1e-9:
            raise ValueError(f"Assignment submit weights must be <= 1.0, got {_submit_sum}")
        # Positive noise STD
        if self._ASSIGN_NOISE_STD <= 0:
            raise ValueError(f"_ASSIGN_NOISE_STD must be > 0, got {self._ASSIGN_NOISE_STD}")
        if self._EXAM_NOISE_STD <= 0:
            raise ValueError(f"_EXAM_NOISE_STD must be > 0, got {self._EXAM_NOISE_STD}")
        # Non-negative weights
        _weight_fields = [
            "_TINTO_ACADEMIC_WEIGHT", "_TINTO_SOCIAL_WEIGHT", "_TINTO_DECAY_BASE",
            "_MOTIVATION_INTRINSIC_BOOST", "_MOTIVATION_AMOTIVATION_PENALTY",
            "_TD_EFFECT_FACTOR", "_COI_SOCIAL_WEIGHT", "_COI_COGNITIVE_WEIGHT",
            "_COI_TEACHING_WEIGHT", "_COI_BASELINE_OFFSET",
            "_HIGH_QUALITY_BOOST", "_LOW_QUALITY_PENALTY",
            "_MISSED_STREAK_PENALTY", "_NEUROTICISM_EXAM_FACTOR", "_CB_FEEDBACK_FACTOR",
        ]
        for name in _weight_fields:
            val = getattr(self, name)
            if val < 0:
                raise ValueError(f"{name} must be non-negative, got {val}")

