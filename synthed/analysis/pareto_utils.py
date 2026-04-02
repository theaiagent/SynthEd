"""Pareto front utilities for multi-objective calibration results."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ParetoSolution:
    """Single non-dominated solution from NSGA-II."""
    params: dict[str, float]
    dropout_error: float
    gpa_error: float
    engagement_error: float
    achieved_dropout: float
    achieved_gpa: float
    achieved_engagement: float


@dataclass(frozen=True)
class ParetoResult:
    """Full NSGA-II calibration output for one profile."""
    profile_name: str
    pareto_front: tuple[ParetoSolution, ...]
    knee_point: ParetoSolution
    n_evaluations: int
    parameter_names: tuple[str, ...]
    validation_dropout_mean: float | None = None
    validation_dropout_std: float | None = None
    validation_gpa_mean: float | None = None
    validation_gpa_std: float | None = None
    validation_seeds: tuple[int, ...] = ()


def find_knee_point(front: tuple[ParetoSolution, ...]) -> ParetoSolution:
    """Geometric knee-point on 2D Pareto front.

    Sorts by dropout_error first (Optuna best_trials are unordered).
    Uses scalar cross product to avoid np.cross deprecation in NumPy 2.x.
    """
    if not front:
        raise ValueError("find_knee_point requires at least one solution")
    if len(front) <= 2:
        return front[0]

    points = np.array([(s.dropout_error, s.gpa_error) for s in front])
    order = np.argsort(points[:, 0])
    sorted_front = tuple(front[int(i)] for i in order)
    sorted_points = points[order]

    mins = sorted_points.min(axis=0)
    maxs = sorted_points.max(axis=0)
    ranges = maxs - mins
    ranges[ranges == 0] = 1.0
    normalized = (sorted_points - mins) / ranges

    p1, p2 = normalized[0], normalized[-1]
    line_vec = p2 - p1
    line_len = np.linalg.norm(line_vec)
    if line_len == 0:
        return sorted_front[0]

    diffs = p1 - normalized
    distances = np.abs(
        line_vec[0] * diffs[:, 1] - line_vec[1] * diffs[:, 0]
    ) / line_len
    return sorted_front[int(np.argmax(distances))]
