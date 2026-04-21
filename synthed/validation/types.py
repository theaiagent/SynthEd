"""
Shared type definitions for the validation package.

ReferenceStatistics and ValidationResult are defined here so they can be
imported by external callers without pulling in the full validator module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class ReferenceStatistics:
    """
    Real-world reference statistics for validation.

    Users provide aggregate statistics from their institution (no individual
    data needed). These are used to assess how well synthetic data matches
    the target population.
    """
    # Demographics
    age_mean: float = 28.0
    age_std: float = 8.0
    gender_distribution: dict[str, float] = field(
        default_factory=lambda: {"male": 0.55, "female": 0.45}
    )
    employment_rate: float = 0.69

    # Academic
    gpa_mean: float = 3.03
    gpa_std: float = 0.75
    dropout_rate: float = 0.312
    dropout_range: tuple[float, float] | None = (0.20, 0.45)

    # Grading outcomes
    pass_rate: float | None = None
    distinction_rate: float | None = None

    # Engagement (if available)
    avg_weekly_logins: float | None = None
    avg_forum_posts_per_student: float | None = None

    def __post_init__(self):
        if self.dropout_range is not None:
            lo, hi = self.dropout_range
            if not (0.0 < lo < hi < 1.0):
                raise ValueError(
                    f"dropout_range must satisfy 0 < lower < upper < 1, "
                    f"got {self.dropout_range}"
                )

    @classmethod
    def from_json(cls, filepath: str) -> ReferenceStatistics:
        data = json.loads(Path(filepath).read_text())
        return cls(**data)


@dataclass
class ValidationResult:
    """Result of a single validation test.

    ``passed`` is strictly ``bool`` — enforced in ``__post_init__``. Downstream
    consumers (scorecard summary counts, validation grades) rely on this so
    they can do plain truthy reads without an ``is True`` guard at every site.
    """
    test_name: str
    metric: str
    synthetic_value: float
    reference_value: float | None
    statistic: float | None = None
    p_value: float | None = None
    passed: bool = True
    details: str = ""

    def __post_init__(self):
        # numpy comparisons (e.g. ``ks_p > alpha``) emit ``np.bool_`` which is
        # semantically a boolean but no longer a ``bool`` subclass on numpy 2.x.
        # Coerce those to plain Python ``bool``; reject everything else.
        if isinstance(self.passed, np.bool_):
            self.passed = bool(self.passed)
        elif not isinstance(self.passed, bool):
            raise TypeError(
                f"passed must be bool, got {type(self.passed).__name__}: {self.passed!r}"
            )
