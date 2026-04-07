"""
OULAD target statistics extraction for calibration.

Reads real OULAD CSV data and computes reference distributions that
the trait-based calibrator optimizes SynthEd parameters to match.

Reference: Kuzilek et al. (2017). Open University Learning Analytics Dataset.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_GPA_SCALE: float = 4.0  # US 4.0 GPA scale for score→GPA conversion


@dataclass(frozen=True)
class OuladTargets:
    """Reference statistics extracted from real OULAD data."""
    # Dropout
    overall_dropout_rate: float          # fraction of Withdrawn students
    module_dropout_rates: dict[str, float]  # code_module → dropout rate

    # Scores (0-100 scale)
    score_mean: float
    score_std: float
    score_median: float

    # GPA equivalent (score/100 * 4.0)
    gpa_mean: float
    gpa_std: float

    # Engagement (mean daily clicks per student)
    engagement_mean: float
    engagement_std: float
    engagement_median: float
    engagement_cv: float              # coefficient of variation (std/mean), scale-independent

    # Demographics
    disability_rate: float
    gender_male_rate: float
    n_students: int


def extract_targets(
    oulad_dir: str | Path,
    modules: set[str] | None = None,
) -> OuladTargets:
    """
    Extract calibration targets from OULAD CSV files.

    Args:
        oulad_dir: Path to directory containing OULAD CSV files
                   (studentInfo.csv, studentAssessment.csv, studentVle.csv).
        modules: If provided, only include students from these code_modules.
                 Use for held-out splits (calibration vs validation).

    Returns:
        OuladTargets with reference distributions.
    """
    oulad_path = Path(oulad_dir)

    student_info = _read_student_info(oulad_path / "studentInfo.csv")
    if modules is not None:
        student_info = [s for s in student_info if s["code_module"] in modules]
        logger.info("Filtered to modules %s: %d students", modules, len(student_info))

    # Get student IDs for filtering scores and engagement
    student_ids = {s["id_student"] for s in student_info} if modules else None
    scores = _read_scores(oulad_path / "studentAssessment.csv", student_ids)
    student_daily_means = _read_and_aggregate_engagement(
        oulad_path / "studentVle.csv", student_ids,
    )

    # Dropout rate
    n_total = len(student_info)
    n_withdrawn = sum(1 for s in student_info if s["final_result"] == "Withdrawn")
    overall_dropout = n_withdrawn / n_total if n_total > 0 else 0.0

    # Per-module dropout
    module_counts: dict[str, list[int]] = {}  # module → [total, withdrawn]
    for s in student_info:
        mod = s["code_module"]
        if mod not in module_counts:
            module_counts[mod] = [0, 0]
        module_counts[mod][0] += 1
        if s["final_result"] == "Withdrawn":
            module_counts[mod][1] += 1
    module_dropout = {
        mod: counts[1] / counts[0] if counts[0] > 0 else 0.0
        for mod, counts in sorted(module_counts.items())
    }

    # Disability
    n_disabled = sum(1 for s in student_info if s["disability"] == "Y")
    disability_rate = n_disabled / n_total if n_total > 0 else 0.0

    # Gender
    n_male = sum(1 for s in student_info if s["gender"] == "M")
    male_rate = n_male / n_total if n_total > 0 else 0.0

    # Scores (guard empty arrays)
    if scores:
        score_arr = np.array(scores, dtype=float)
        gpa_arr = score_arr / 100.0 * _GPA_SCALE
        score_mean = round(float(np.mean(score_arr)), 2)
        score_std = round(float(np.std(score_arr)), 2)
        score_median = round(float(np.median(score_arr)), 2)
        gpa_mean = round(float(np.mean(gpa_arr)), 3)
        gpa_std = round(float(np.std(gpa_arr)), 3)
    else:
        score_mean = score_std = score_median = 0.0
        gpa_mean = gpa_std = 0.0

    # Engagement: mean clicks per student per day (guard empty)
    if student_daily_means:
        eng_arr = np.array(student_daily_means, dtype=float)
        eng_mean = round(float(np.mean(eng_arr)), 2)
        eng_std = round(float(np.std(eng_arr)), 2)
        eng_median = round(float(np.median(eng_arr)), 2)
        eng_cv = round(float(np.std(eng_arr) / np.mean(eng_arr)), 4) if float(np.mean(eng_arr)) > 0 else 0.0
    else:
        eng_mean = eng_std = eng_median = eng_cv = 0.0

    logger.info(
        "OULAD targets: %d students, dropout=%.1f%%, GPA=%.2f, engagement=%.1f clicks/day",
        n_total, overall_dropout * 100, gpa_mean, eng_mean,
    )

    return OuladTargets(
        overall_dropout_rate=round(overall_dropout, 4),
        module_dropout_rates=module_dropout,
        score_mean=score_mean,
        score_std=score_std,
        score_median=score_median,
        gpa_mean=gpa_mean,
        gpa_std=gpa_std,
        engagement_mean=eng_mean,
        engagement_std=eng_std,
        engagement_median=eng_median,
        engagement_cv=eng_cv,
        disability_rate=round(disability_rate, 4),
        gender_male_rate=round(male_rate, 4),
        n_students=n_total,
    )


# ─────────────────────────────────────────────
# CSV readers
# ─────────────────────────────────────────────

def _read_student_info(path: Path) -> list[dict[str, str]]:
    """Read studentInfo.csv into list of dicts with column validation."""
    required = {"final_result", "code_module", "gender", "disability"}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = set(reader.fieldnames or [])
        missing = required - columns
        if missing:
            raise ValueError(f"studentInfo.csv missing columns: {missing}")
        return list(reader)


def _read_scores(
    path: Path,
    student_ids: set[str] | None = None,
) -> list[float]:
    """Read numeric scores from studentAssessment.csv."""
    scores: list[float] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "score" not in (reader.fieldnames or []):
            raise ValueError("studentAssessment.csv missing 'score' column")
        for row in reader:
            if student_ids is not None and row.get("id_student") not in student_ids:
                continue
            try:
                score = float(row["score"])
                scores.append(score)
            except (ValueError, KeyError):
                continue
    return scores


def _read_and_aggregate_engagement(
    path: Path,
    student_ids: set[str] | None = None,
) -> list[float]:
    """Stream studentVle.csv and compute mean daily clicks per student.

    Aggregates on-the-fly to avoid loading 10M+ rows into memory.
    """
    student_days: dict[str, dict[str, int]] = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row.get("id_student", "")
            if student_ids is not None and sid not in student_ids:
                continue
            day = row.get("date", "")
            try:
                clicks = int(row.get("sum_click", "0"))
            except ValueError:
                continue
            if sid not in student_days:
                student_days[sid] = {}
            student_days[sid][day] = student_days[sid].get(day, 0) + clicks

    means: list[float] = []
    for daily_clicks in student_days.values():
        if daily_clicks:
            vals = list(daily_clicks.values())
            means.append(sum(vals) / len(vals))
    return means

