"""
Shared type definitions for the validation package.

ReferenceStatistics and ValidationResult are defined here so they can be
imported by external callers without pulling in the full validator module.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path

import numpy as np


def _validate_proportion(value: float, name: str) -> None:
    """Reject nonscalar, boolean or non-finite probability inputs with context."""
    if (
        isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
        or not 0.0 <= value <= 1.0 or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite real proportion in [0, 1], got {value!r}")


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
        """Validate configured probability references without clipping inputs."""
        self._validate_gender_reference()
        for name in ("employment_rate", "dropout_rate", "pass_rate", "distinction_rate"):
            value = getattr(self, name)
            if value is None and name in {"pass_rate", "distinction_rate"}:
                continue
            _validate_proportion(value, name)
        if self.dropout_range is not None:
            lo, hi = self.dropout_range
            if not (0.0 < lo < hi < 1.0):
                raise ValueError(
                    f"dropout_range must satisfy 0 < lower < upper < 1, "
                    f"got {self.dropout_range}"
                )

    def _validate_gender_reference(self) -> None:
        """Require literal category labels and a complete probability distribution.

        The sum allowance is only accumulated floating-point roundoff, one
        unit at 1.0 per category; no empirical probability tolerance is used.
        Call again before assessment because this dataclass/dictionary is mutable.
        """
        distribution = self.gender_distribution
        if not isinstance(distribution, dict) or not distribution:
            raise ValueError("gender_distribution must be a nonempty dictionary")
        for category, probability in distribution.items():
            if not isinstance(category, str) or not category:
                raise ValueError("gender_distribution keys must be nonempty strings")
            try:
                _validate_proportion(probability, f"gender_distribution[{category!r}]")
            except Exception as exc:
                raise ValueError(f"gender_distribution[{category!r}] must be a finite real proportion in [0, 1]") from exc
        total = math.fsum(distribution.values())
        if not math.isclose(total, 1.0, rel_tol=0.0,
                            abs_tol=len(distribution) * math.ulp(1.0)):
            raise ValueError(f"gender_distribution must sum to 1, got {total!r}")

    @classmethod
    def from_json(cls, filepath: str) -> ReferenceStatistics:
        data = json.loads(Path(filepath).read_text())
        return cls(**data)


@dataclass
class ValidationResult:
    """Result of a single validation test.

    ``passed`` is strictly ``bool``. ``status`` distinguishes failed checks
    from checks that could not be assessed. Unassessed measurements are
    ``None`` and carry a reason; all other numeric values must be finite.
    """
    test_name: str
    metric: str
    synthetic_value: float | None
    reference_value: float | None
    statistic: float | None = None
    p_value: float | None = None
    passed: bool = True
    details: str = ""
    status: str | None = None

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
        if self.status is None:
            self.status = "passed" if self.passed else "failed"
        if self.status not in {"passed", "failed", "not_assessed"}:
            raise ValueError(f"Unknown validation status: {self.status!r}")
        if self.passed != (self.status == "passed"):
            raise ValueError("Validation status and passed flag disagree")
        for name in ("synthetic_value", "reference_value", "statistic", "p_value"):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite or None, got {value!r}")
        if self.status == "not_assessed":
            if not isinstance(self.details, str) or not self.details.strip():
                raise ValueError("not_assessed requires a nonempty reason in details")
            if any(value is not None for value in (self.synthetic_value, self.statistic, self.p_value)):
                raise ValueError("not_assessed measurements must be None")
