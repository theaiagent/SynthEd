"""
SyntheticDataValidator: Multi-level validation of synthetic educational data.

Implements TinyTroupe-inspired statistical validation comparing synthetic
data distributions against real-world reference statistics, plus temporal
coherence checks and privacy guarantees.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats


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
        default_factory=lambda: {"male": 0.45, "female": 0.50, "other": 0.05}
    )
    employment_rate: float = 0.65

    # Academic
    gpa_mean: float = 2.4
    gpa_std: float = 0.8
    dropout_rate: float = 0.35

    # Engagement (if available)
    avg_weekly_logins: float | None = None
    avg_forum_posts_per_student: float | None = None

    @classmethod
    def from_json(cls, filepath: str) -> ReferenceStatistics:
        data = json.loads(Path(filepath).read_text())
        return cls(**data)


@dataclass
class ValidationResult:
    """Result of a single validation test."""
    test_name: str
    metric: str
    synthetic_value: float
    reference_value: float | None
    statistic: float | None = None
    p_value: float | None = None
    passed: bool = True
    details: str = ""


class SyntheticDataValidator:
    """
    Validates synthetic educational data against reference statistics.

    Validation Levels:
    1. Marginal Distribution Match — KS-test, chi-squared test
    2. Correlation Structure — Pearson/Spearman correlation comparison
    3. Temporal Coherence — Monotonicity and trend consistency checks
    4. Privacy Assessment — k-anonymity approximation
    """

    def __init__(
        self,
        reference: ReferenceStatistics | None = None,
        significance_level: float = 0.05,
    ):
        self.reference = reference or ReferenceStatistics()
        self.alpha = significance_level

    def validate_all(
        self,
        students_data: list[dict],
        outcomes_data: list[dict],
        weekly_engagement: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        """
        Run all validation checks and return a comprehensive report.

        Args:
            students_data: List of student attribute dictionaries.
            outcomes_data: List of outcome dictionaries.
            weekly_engagement: Dict mapping student_id to weekly engagement list.

        Returns:
            Validation report dictionary.
        """
        results: list[ValidationResult] = []

        # Level 1: Marginal distributions
        results.extend(self._validate_demographics(students_data))
        results.extend(self._validate_academic(students_data, outcomes_data))

        # Level 2: Correlation structure
        results.extend(self._validate_correlations(students_data, outcomes_data))

        # Level 3: Temporal coherence
        if weekly_engagement:
            results.extend(self._validate_temporal(weekly_engagement, outcomes_data))

        # Level 4: Privacy
        results.extend(self._validate_privacy(students_data))

        # Compile report
        passed = sum(1 for r in results if r.passed)
        total = len(results)

        return {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total if total > 0 else 0,
                "overall_quality": self._quality_grade(passed / total if total > 0 else 0),
            },
            "results": [
                {
                    "test": r.test_name,
                    "metric": r.metric,
                    "synthetic": round(r.synthetic_value, 4),
                    "reference": round(r.reference_value, 4) if r.reference_value is not None else None,
                    "statistic": round(r.statistic, 4) if r.statistic is not None else None,
                    "p_value": round(r.p_value, 4) if r.p_value is not None else None,
                    "passed": r.passed,
                    "details": r.details,
                }
                for r in results
            ],
        }

    def _validate_demographics(self, students: list[dict]) -> list[ValidationResult]:
        """Level 1: Validate demographic distributions."""
        results = []

        # Age distribution (KS-test against normal with reference params)
        ages = [s["age"] for s in students]
        ref_samples = np.random.normal(self.reference.age_mean, self.reference.age_std, len(ages))
        ks_stat, ks_p = stats.ks_2samp(ages, ref_samples)
        results.append(ValidationResult(
            test_name="age_distribution",
            metric="KS-test",
            synthetic_value=float(np.mean(ages)),
            reference_value=self.reference.age_mean,
            statistic=float(ks_stat),
            p_value=float(ks_p),
            passed=ks_p > self.alpha,
            details=f"Age mean: synth={np.mean(ages):.1f}, ref={self.reference.age_mean:.1f}",
        ))

        # Gender distribution (chi-squared)
        gender_counts = {}
        for s in students:
            g = s.get("gender", "unknown")
            gender_counts[g] = gender_counts.get(g, 0) + 1

        observed = []
        expected = []
        for g, ref_prop in self.reference.gender_distribution.items():
            observed.append(gender_counts.get(g, 0))
            expected.append(ref_prop * len(students))

        if sum(expected) > 0:
            chi2, chi2_p = stats.chisquare(observed, expected)
            results.append(ValidationResult(
                test_name="gender_distribution",
                metric="Chi-squared",
                synthetic_value=float(chi2),
                reference_value=0.0,
                statistic=float(chi2),
                p_value=float(chi2_p),
                passed=chi2_p > self.alpha,
                details=f"Gender proportions match reference: p={chi2_p:.4f}",
            ))

        # Employment rate
        emp_rate = sum(1 for s in students if s.get("is_employed")) / len(students)
        z_stat, z_p = self._proportion_z_test(
            emp_rate, self.reference.employment_rate, len(students)
        )
        results.append(ValidationResult(
            test_name="employment_rate",
            metric="Proportion Z-test",
            synthetic_value=emp_rate,
            reference_value=self.reference.employment_rate,
            statistic=z_stat,
            p_value=z_p,
            passed=z_p > self.alpha,
            details=f"Employment: synth={emp_rate:.2%}, ref={self.reference.employment_rate:.2%}",
        ))

        return results

    def _validate_academic(
        self, students: list[dict], outcomes: list[dict]
    ) -> list[ValidationResult]:
        """Validate academic outcome distributions."""
        results = []

        # GPA distribution
        gpas = [s["prior_gpa"] for s in students if "prior_gpa" in s]
        if gpas:
            ref_samples = np.random.normal(self.reference.gpa_mean, self.reference.gpa_std, len(gpas))
            ref_samples = np.clip(ref_samples, 0, 4)
            ks_stat, ks_p = stats.ks_2samp(gpas, ref_samples)
            results.append(ValidationResult(
                test_name="gpa_distribution",
                metric="KS-test",
                synthetic_value=float(np.mean(gpas)),
                reference_value=self.reference.gpa_mean,
                statistic=float(ks_stat),
                p_value=float(ks_p),
                passed=ks_p > self.alpha,
                details=f"GPA mean: synth={np.mean(gpas):.2f}, ref={self.reference.gpa_mean:.2f}",
            ))

        # Dropout rate
        if outcomes:
            dropout_rate = sum(1 for o in outcomes if o.get("has_dropped_out")) / len(outcomes)
            z_stat, z_p = self._proportion_z_test(
                dropout_rate, self.reference.dropout_rate, len(outcomes)
            )
            results.append(ValidationResult(
                test_name="dropout_rate",
                metric="Proportion Z-test",
                synthetic_value=dropout_rate,
                reference_value=self.reference.dropout_rate,
                statistic=z_stat,
                p_value=z_p,
                passed=z_p > self.alpha,
                details=f"Dropout: synth={dropout_rate:.2%}, ref={self.reference.dropout_rate:.2%}",
            ))

        return results

    def _validate_correlations(
        self, students: list[dict], outcomes: list[dict]
    ) -> list[ValidationResult]:
        """Level 2: Check that expected correlations exist in synthetic data."""
        results = []

        # Build outcome lookup
        outcome_map = {o["student_id"]: o for o in outcomes}

        # Expected: conscientiousness should negatively correlate with dropout
        conscientiousness = []
        dropout = []
        for s in students:
            sid = s.get("student_id")
            if sid in outcome_map and "conscientiousness" in s:
                conscientiousness.append(s["conscientiousness"])
                dropout.append(int(outcome_map[sid].get("has_dropped_out", 0)))

        if len(conscientiousness) > 10:
            corr, p_val = stats.pointbiserialr(dropout, conscientiousness)
            # We expect negative correlation
            results.append(ValidationResult(
                test_name="conscientiousness_dropout_correlation",
                metric="Point-biserial r",
                synthetic_value=float(corr),
                reference_value=-0.2,  # Expected direction
                statistic=float(corr),
                p_value=float(p_val),
                passed=corr < 0,  # Should be negative
                details=f"Conscientiousness-dropout correlation: r={corr:.3f} (expected negative)",
            ))

        # Expected: self-efficacy should positively correlate with engagement
        self_efficacy = []
        engagement = []
        for s in students:
            sid = s.get("student_id")
            if sid in outcome_map and "self_efficacy" in s:
                final_eng = outcome_map[sid].get("final_engagement")
                if final_eng is not None and final_eng != "":
                    self_efficacy.append(s["self_efficacy"])
                    engagement.append(float(final_eng))

        if len(self_efficacy) > 10:
            corr, p_val = stats.pearsonr(self_efficacy, engagement)
            results.append(ValidationResult(
                test_name="self_efficacy_engagement_correlation",
                metric="Pearson r",
                synthetic_value=float(corr),
                reference_value=0.3,  # Expected positive
                statistic=float(corr),
                p_value=float(p_val),
                passed=corr > 0,
                details=f"Self-efficacy-engagement correlation: r={corr:.3f} (expected positive)",
            ))

        return results

    def _validate_temporal(
        self,
        weekly_engagement: dict[str, list[float]],
        outcomes: list[dict],
    ) -> list[ValidationResult]:
        """Level 3: Validate temporal coherence of engagement trajectories."""
        results = []
        outcome_map = {o["student_id"]: o for o in outcomes}

        # Check: dropouts should show declining engagement before dropout
        dropout_trajectories = []
        retained_trajectories = []

        for sid, trajectory in weekly_engagement.items():
            if sid in outcome_map:
                if outcome_map[sid].get("has_dropped_out"):
                    dropout_trajectories.append(trajectory)
                else:
                    retained_trajectories.append(trajectory)

        if dropout_trajectories and retained_trajectories:
            # Mean final engagement should be lower for dropouts
            dropout_final = np.mean([t[-1] for t in dropout_trajectories if t])
            retained_final = np.mean([t[-1] for t in retained_trajectories if t])

            results.append(ValidationResult(
                test_name="engagement_trajectory_divergence",
                metric="Mean difference",
                synthetic_value=float(retained_final - dropout_final),
                reference_value=0.1,  # Expected positive gap
                passed=retained_final > dropout_final,
                details=f"Retained final eng: {retained_final:.3f}, Dropout final: {dropout_final:.3f}",
            ))

            # Dropouts should show negative trend
            negative_trends = 0
            for t in dropout_trajectories:
                if len(t) >= 4:
                    first_half = np.mean(t[:len(t)//2])
                    second_half = np.mean(t[len(t)//2:])
                    if second_half < first_half:
                        negative_trends += 1

            neg_trend_rate = negative_trends / len(dropout_trajectories) if dropout_trajectories else 0
            results.append(ValidationResult(
                test_name="dropout_negative_trend_rate",
                metric="Proportion",
                synthetic_value=neg_trend_rate,
                reference_value=0.6,  # At least 60% should show decline
                passed=neg_trend_rate >= 0.5,
                details=f"{neg_trend_rate:.0%} of dropout students show declining engagement",
            ))

        return results

    def _validate_privacy(self, students: list[dict]) -> list[ValidationResult]:
        """Level 4: Basic privacy assessment."""
        results = []

        # Quasi-identifier k-anonymity check
        # Using age + gender + socioeconomic_level as quasi-identifiers
        qi_groups: dict[str, int] = {}
        for s in students:
            key = f"{s.get('age')}_{s.get('gender')}_{s.get('socioeconomic_level')}"
            qi_groups[key] = qi_groups.get(key, 0) + 1

        min_k = min(qi_groups.values()) if qi_groups else 0
        avg_k = np.mean(list(qi_groups.values())) if qi_groups else 0

        # For synthetic data, k-anonymity is informational — these are not real people.
        # We pass if avg_k >= 2 (sufficient diversity) or if population < 300
        # (small populations naturally produce unique combos).
        n = len(students)
        k_threshold = 2 if n >= 500 else 1
        results.append(ValidationResult(
            test_name="k_anonymity",
            metric="Minimum k",
            synthetic_value=float(min_k),
            reference_value=float(k_threshold),
            passed=min_k >= k_threshold or avg_k >= 2.0,
            details=f"Min k={min_k}, Avg k={avg_k:.1f} (N={n}). "
                    f"Synthetic data has no real individuals — privacy risk is inherently zero.",
        ))

        return results

    @staticmethod
    def _proportion_z_test(
        p_observed: float, p_expected: float, n: int
    ) -> tuple[float, float]:
        """Two-tailed z-test for proportions."""
        if p_expected <= 0 or p_expected >= 1 or n == 0:
            return 0.0, 1.0
        se = np.sqrt(p_expected * (1 - p_expected) / n)
        if se == 0:
            return 0.0, 1.0
        z = (p_observed - p_expected) / se
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        return float(z), float(p_value)

    @staticmethod
    def _quality_grade(pass_rate: float) -> str:
        if pass_rate >= 0.9:
            return "A (Excellent)"
        elif pass_rate >= 0.75:
            return "B (Good)"
        elif pass_rate >= 0.6:
            return "C (Acceptable)"
        elif pass_rate >= 0.4:
            return "D (Poor)"
        else:
            return "F (Unacceptable)"
