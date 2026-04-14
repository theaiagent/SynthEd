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
    hv_history: tuple[float, ...] = ()


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


def compute_hypervolume(
    points: np.ndarray, reference_point: np.ndarray
) -> float:
    """2D hypervolume indicator via sweep-line (Fonseca et al., 2006).

    Computes the area dominated by *points* and bounded by *reference_point*.
    Both objectives are assumed to be minimised.

    Parameters
    ----------
    points : np.ndarray
        (N, 2) array of objective vectors.
    reference_point : np.ndarray
        (2,) reference (upper-bound) vector.

    Returns
    -------
    float
        Dominated hypervolume (area).  Zero when *points* is empty or no
        point strictly dominates the reference on both objectives.
    """
    if points.shape[0] == 0:
        return 0.0

    ref_x, ref_y = reference_point[0], reference_point[1]

    # Keep only points strictly below the reference on both objectives
    mask = (points[:, 0] < ref_x) & (points[:, 1] < ref_y)
    valid = points[mask]
    if valid.shape[0] == 0:
        return 0.0

    # Sort by first objective ascending
    order = np.argsort(valid[:, 0])
    sorted_pts = valid[order]

    volume = 0.0
    best_y = ref_y  # best (lowest) second-objective value seen so far

    for i in range(sorted_pts.shape[0]):
        x_i = sorted_pts[i, 0]
        y_i = sorted_pts[i, 1]
        best_y = min(best_y, y_i)
        x_next = (
            sorted_pts[i + 1, 0]
            if i + 1 < sorted_pts.shape[0]
            else ref_x
        )
        volume += (x_next - x_i) * (ref_y - best_y)

    return float(volume)


def compare_knee_points(
    a: ParetoSolution,
    b: ParetoSolution,
) -> float:
    """Normalized Euclidean distance between two knee-point param vectors.

    Each parameter's difference is divided by the range (max of abs values)
    of the two values. Returns the RMS of these normalized differences.
    If all params are identical, returns 0.0.
    """
    keys = sorted(a.params.keys())
    if not keys:
        return 0.0
    diffs = []
    for k in keys:
        va, vb = a.params[k], b.params[k]
        r = max(abs(va), abs(vb))
        if r == 0:
            diffs.append(0.0)
        else:
            diffs.append(((va - vb) / r) ** 2)
    return float(np.sqrt(sum(diffs) / len(diffs)))
