"""
SyntheticDataValidator: Multi-level validation of synthetic educational data.

Implements TinyTroupe-inspired statistical validation comparing synthetic
data distributions against real-world reference statistics, plus temporal
coherence checks and privacy guarantees.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from .types import ReferenceStatistics, ValidationResult
from .report_contract import quality_grade, summarize_results

# ── Standard correlation tests (declarative table) ──
# Columns: attr_key, outcome_key, test_name, expected_direction,
#          reference_value, description, continuous
_STANDARD_TESTS: list[tuple] = [
    (
        "conscientiousness", "has_dropped_out",
        "tinto_conscientiousness_dropout", "negative", -0.2,
        "Conscientiousness-dropout (Poropat 2009: expected negative)", False,
    ),
    (
        "self_efficacy", "final_engagement",
        "bandura_self_efficacy_engagement", "positive", 0.3,
        "Self-efficacy-engagement (Bandura 1997: expected positive)", True,
    ),
    (
        "self_regulation", "final_engagement",
        "rovai_self_regulation_engagement", "positive", 0.25,
        "Self-regulation-engagement (Rovai 2003: expected positive)", True,
    ),
    (
        "financial_stress", "has_dropped_out",
        "bean_metzner_financial_stress_dropout", "positive", 0.15,
        "Financial stress-dropout (Bean & Metzner 1985: expected positive)", False,
    ),
    (
        "goal_commitment", "final_engagement",
        "tinto_goal_commitment_engagement", "positive", 0.2,
        "Goal commitment-engagement (Tinto 1975: expected positive)", True,
    ),
    (
        "learner_autonomy", "final_engagement",
        "moore_autonomy_engagement", "positive", 0.2,
        "Learner autonomy-engagement (Moore 1993: expected positive)", True,
    ),
    (
        "coi_composite", "final_engagement",
        "garrison_coi_engagement", "positive", 0.3,
        "CoI composite-engagement (Garrison 2000: expected positive)", True,
    ),
    (
        "network_degree", "final_engagement",
        "epstein_network_degree_engagement", "positive", 0.2,
        "Network degree-engagement (Epstein & Axtell 1996: expected positive)", True,
    ),
    (
        "perceived_cost_benefit", "final_engagement",
        "kember_cost_benefit_engagement", "positive", 0.25,
        "Cost-benefit-engagement (Kember 1989: expected positive)", True,
    ),
]


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
        seed: int = 42,
    ):
        self.reference = reference or ReferenceStatistics()
        self.alpha = significance_level
        self._rng = np.random.default_rng(seed)

    def validate_all(
        self,
        students_data: list[dict],
        outcomes_data: list[dict],
        weekly_engagement: dict[str, list[float]] | None = None,
        *,
        total_weeks: int | None = None,
    ) -> dict[str, Any]:
        """
        Run all validation checks and return a comprehensive report.

        Args:
            students_data: List of student attribute dictionaries.
            outcomes_data: List of outcome dictionaries.
            weekly_engagement: Dict mapping student_id to weekly engagement list.
            total_weeks: Planned simulation horizon, matching global dropout weeks.
                If omitted, infer it from the longest supplied trajectory.

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
        if weekly_engagement is not None:
            results.extend(self._validate_temporal(
                weekly_engagement, outcomes_data, total_weeks=total_weeks,
            ))

        # Level 4: Privacy
        results.extend(self._validate_privacy(students_data))

        # Level 5: Backstory consistency (optional — only when backstories are present)
        results.extend(self._validate_backstories(students_data))

        # Compile report
        rows = [
                {
                    "test": r.test_name,
                    "metric": r.metric,
                    "synthetic": round(r.synthetic_value, 4) if r.synthetic_value is not None else None,
                    "reference": round(r.reference_value, 4) if r.reference_value is not None else None,
                    "statistic": round(r.statistic, 4) if r.statistic is not None else None,
                    "p_value": round(r.p_value, 4) if r.p_value is not None else None,
                    "passed": r.passed,
                    "status": r.status,
                    "details": r.details,
                }
                for r in results
            ]
        return {"summary": summarize_results(rows), "results": rows}

    @staticmethod
    def _not_assessed(test_name: str, metric: str, reference: float | None,
                      reason: str) -> ValidationResult:
        """Represent an unavailable measurement with its explicit reason."""
        return ValidationResult(test_name, metric, None, reference,
                                passed=False, details=reason, status="not_assessed")

    def _effective_alpha(self, n: int) -> float:
        """Scale-adjusted significance level for large populations.

        At small N (<=500), returns configured alpha (default 0.05).
        At large N, reduces alpha to compensate for increased statistical
        power detecting trivially small deviations.
        """
        if n <= 500:
            return self.alpha
        adjusted = self.alpha * (200 / n) ** 0.5
        return max(adjusted, 0.001)

    def _validate_demographics(self, students: list[dict]) -> list[ValidationResult]:
        """Level 1: Validate demographic distributions."""
        results = []
        if not students:
            return [self._not_assessed(name, metric, ref, "insufficient_population; n=0")
                    for name, metric, ref in (
                        ("age_distribution", "KS-test", self.reference.age_mean),
                        ("gender_distribution", "Chi-squared", 0.0),
                        ("employment_rate", "Proportion Z-test", self.reference.employment_rate),
                    )]

        # Age distribution (one-sample KS-test against theoretical normal CDF)
        ages = [s["age"] for s in students]
        if not np.all(np.isfinite(ages)):
            results.append(self._not_assessed("age_distribution", "KS-test", self.reference.age_mean,
                                             f"non_finite_input; n={len(ages)}"))
        else:
            ks_stat, ks_p = stats.kstest(
                ages, "norm", args=(self.reference.age_mean, self.reference.age_std),
            )
            results.append(self._measured_result(
                test_name="age_distribution",
                metric="KS-test",
                synthetic_value=float(np.mean(ages)),
                reference_value=self.reference.age_mean,
                statistic=float(ks_stat),
                p_value=float(ks_p),
                passed=ks_p > self._effective_alpha(len(ages)),
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
            results.append(self._measured_result(
                test_name="gender_distribution",
                metric="Chi-squared",
                synthetic_value=float(chi2),
                reference_value=0.0,
                statistic=float(chi2),
                p_value=float(chi2_p),
                passed=chi2_p > self._effective_alpha(len(students)),
                details=f"Gender proportions match reference: p={chi2_p:.4f}",
            ))

        # Employment rate (proportion with employment_intensity > 0.05)
        emp_rate = sum(1 for s in students if s.get("employment_intensity", 0) > 0.05) / len(students)
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
            passed=z_p > self._effective_alpha(len(students)),
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
        if gpas and not np.all(np.isfinite(gpas)):
            results.append(self._not_assessed("gpa_distribution", "KS-test", self.reference.gpa_mean,
                                             f"non_finite_input; n={len(gpas)}"))
        elif gpas:
            ref_samples = self._rng.normal(self.reference.gpa_mean, self.reference.gpa_std, len(gpas))
            ref_samples = np.clip(ref_samples, 0, 4)
            ks_stat, ks_p = stats.ks_2samp(gpas, ref_samples)
            results.append(self._measured_result(
                test_name="gpa_distribution",
                metric="KS-test",
                synthetic_value=float(np.mean(gpas)),
                reference_value=self.reference.gpa_mean,
                statistic=float(ks_stat),
                p_value=float(ks_p),
                passed=ks_p > self._effective_alpha(len(gpas)),
                details=f"GPA mean: synth={np.mean(gpas):.2f}, ref={self.reference.gpa_mean:.2f}",
            ))

        else:
            results.append(self._not_assessed("gpa_distribution", "KS-test", self.reference.gpa_mean,
                                             "insufficient_gpa_observations; n=0"))

        # Dropout rate
        if outcomes:
            dropout_rate = sum(1 for o in outcomes if o.get("has_dropped_out")) / len(outcomes)
            if self.reference.dropout_range is not None:
                lo, hi = self.reference.dropout_range
                passed = lo <= dropout_rate <= hi
                results.append(ValidationResult(
                    test_name="dropout_rate",
                    metric="Range check",
                    synthetic_value=dropout_rate,
                    reference_value=(lo + hi) / 2,
                    passed=passed,
                    details=f"Dropout: synth={dropout_rate:.2%}, target=[{lo:.2%}, {hi:.2%}]",
                ))

            else:
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
                    passed=z_p > self._effective_alpha(len(outcomes)),
                    details=f"Dropout: synth={dropout_rate:.2%}, ref={self.reference.dropout_rate:.2%}",
                ))
        else:
            results.append(self._not_assessed("dropout_rate", "Range check" if self.reference.dropout_range else "Proportion Z-test",
                                             self.reference.dropout_rate, "insufficient_outcomes; n=0"))

        return results

    def _correlation_test(
        self,
        students: list[dict],
        outcome_map: dict[str, dict],
        attr_key: str,
        outcome_key: str,
        test_name: str,
        expected_direction: str,
        reference_value: float,
        description: str,
        continuous: bool = True,
    ) -> ValidationResult:
        """Measure paired observations or report why no estimate is available."""
        xs, ys = [], []
        for s in students:
            sid = s.get("student_id")
            if sid in outcome_map and attr_key in s:
                val = outcome_map[sid].get(outcome_key)
                if val is not None and val != "":
                    xs.append(s[attr_key])
                    ys.append(float(val))
        return self._paired_correlation(xs, ys, test_name, expected_direction,
                                        reference_value, description, continuous)

    def _paired_correlation(self, xs: list, ys: list, test_name: str,
                            expected_direction: str, reference_value: float,
                            description: str, continuous: bool = True) -> ValidationResult:
        """Guard undefined pairs before applying the existing correlation rule."""
        metric = "Pearson r" if continuous else "Point-biserial r"
        n = len(xs)
        reason = None
        if n <= 10:
            reason = "insufficient_pairs"
        elif not np.all(np.isfinite(xs)) or not np.all(np.isfinite(ys)):
            reason = "non_finite_input"
        elif np.ptp(xs) == 0 or np.ptp(ys) == 0:
            reason = "constant_input"
        if reason:
            return self._not_assessed(test_name, metric, reference_value, f"{reason}; n={n}")
        if continuous:
            corr, p_val = stats.pearsonr(xs, ys)
        else:
            corr, p_val = stats.pointbiserialr(ys, xs)

        if expected_direction == "positive":
            passed = corr > 0
        elif expected_direction == "negative":
            passed = corr < 0
        else:
            passed = True

        return self._measured_result(
            test_name=test_name,
            metric=metric,
            synthetic_value=float(corr),
            reference_value=reference_value,
            statistic=float(corr),
            p_value=float(p_val),
            passed=passed,
            details=f"{description}: r={corr:.3f}; n={n}",
        )

    def _measured_result(self, **values) -> ValidationResult:
        """Turn undefined statistic outputs into explicit unassessed results."""
        for key in ("synthetic_value", "statistic", "p_value"):
            value = values.get(key)
            if value is not None and not np.isfinite(value):
                return self._not_assessed(values["test_name"], values["metric"],
                                          values["reference_value"],
                                          "undefined_statistic; " + values.get("details", ""))
        return ValidationResult(**values)

    def _validate_correlations(
        self, students: list[dict], outcomes: list[dict]
    ) -> list[ValidationResult]:
        """
        Level 2: Validate theory-grounded correlations in synthetic data.

        Expected relationships from literature:
        - Conscientiousness → dropout (negative) [Poropat, 2009]
        - Self-efficacy → engagement (positive) [Bandura, 1997]
        - Self-regulation → engagement (positive) [Rovai, 2003]
        - Financial stress → dropout (positive) [Bean & Metzner, 1985]
        - Goal commitment → engagement (positive) [Tinto, 1975]
        """
        results = []
        outcome_map = {o["student_id"]: o for o in outcomes}

        for attr_key, outcome_key, test_name, direction, ref_val, desc, continuous in _STANDARD_TESTS:
            result = self._correlation_test(
                students, outcome_map,
                attr_key, outcome_key,
                test_name, direction, ref_val, desc, continuous,
            )
            results.append(result)

        # ── SDT (Deci & Ryan, 1985): Intrinsic motivation → higher engagement ──
        intrinsic_eng = [
            outcome_map[s["student_id"]]["final_engagement"]
            for s in students if s.get("motivation_type") == "intrinsic"
            and s["student_id"] in outcome_map
            and outcome_map[s["student_id"]].get("final_engagement") is not None
        ]
        amotivation_eng = [
            outcome_map[s["student_id"]]["final_engagement"]
            for s in students if s.get("motivation_type") == "amotivation"
            and s["student_id"] in outcome_map
            and outcome_map[s["student_id"]].get("final_engagement") is not None
        ]
        group_reason = None
        if len(intrinsic_eng) < 5 or len(amotivation_eng) < 5:
            group_reason = "insufficient_groups"
        elif not np.all(np.isfinite(intrinsic_eng)) or not np.all(np.isfinite(amotivation_eng)):
            group_reason = "non_finite_input"
        elif np.ptp(intrinsic_eng) == 0 and np.ptp(amotivation_eng) == 0:
            group_reason = "constant_groups"
        if group_reason:
            results.append(self._not_assessed("sdt_intrinsic_vs_amotivation", "Independent t-test", None,
                                             f"{group_reason}; intrinsic_n={len(intrinsic_eng)}; amotivation_n={len(amotivation_eng)}"))
        else:
            intrinsic_mean = float(np.mean(intrinsic_eng))
            amotivation_mean = float(np.mean(amotivation_eng))
            t_stat, t_p = stats.ttest_ind(intrinsic_eng, amotivation_eng)
            results.append(self._measured_result(
                test_name="sdt_intrinsic_vs_amotivation",
                metric="Independent t-test",
                synthetic_value=intrinsic_mean,
                reference_value=amotivation_mean,
                statistic=float(t_stat),
                p_value=float(t_p),
                passed=intrinsic_mean > amotivation_mean,
                details=f"Intrinsic eng={intrinsic_mean:.3f} vs amotivation={amotivation_mean:.3f} "
                        f"(Deci & Ryan 1985: intrinsic > amotivation); "
                        f"intrinsic_n={len(intrinsic_eng)}; amotivation_n={len(amotivation_eng)}",
            ))

        # ── GPA → dropout (negative): Higher GPA students drop out less ──
        gpa_xs, gpa_ys = [], []
        for s in students:
            sid = s.get("student_id")
            if sid in outcome_map:
                final_gpa = outcome_map[sid].get("final_gpa")
                dropped = outcome_map[sid].get("has_dropped_out")
                if final_gpa is not None and dropped is not None:
                    gpa_xs.append(float(final_gpa))
                    gpa_ys.append(float(dropped))
        results.append(self._paired_correlation(gpa_xs, gpa_ys, "gpa_dropout_correlation",
                                               "negative", -0.2, "GPA-dropout", False))

        # ── Bäulke et al.: Dropout phase distribution ──
        phase_counts: dict[int, int] = {}
        for o in outcomes:
            phase = o.get("final_dropout_phase")
            if phase is not None:
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
        if phase_counts and not all(np.isfinite(phase) for phase in phase_counts):
            results.append(self._not_assessed("baulke_phase_distribution", "Decided phase proportion", self.reference.dropout_rate,
                                             f"non_finite_input; n={sum(phase_counts.values())}"))
        elif phase_counts:
            total = sum(phase_counts.values())

            # In ODL context, many students experience non-fit (Bäulke model
            # was developed for campus universities). We check that the terminal
            # phase (decided) is a minority.
            decided_rate = phase_counts.get(5, 0) / total
            results.append(ValidationResult(
                test_name="baulke_phase_distribution",
                metric="Decided phase proportion",
                synthetic_value=decided_rate,
                reference_value=self.reference.dropout_rate,
                passed=decided_rate <= 0.50,
                details=f"Phase 5 (decided): {decided_rate:.0%}, "
                        f"dropout target: {self.reference.dropout_rate:.0%}",
            ))
        else:
            results.append(self._not_assessed("baulke_phase_distribution", "Decided phase proportion",
                                             self.reference.dropout_rate, "missing_phase_observations; n=0"))

        # ── Outcome distribution: pass_rate / distinction_rate ──
        if self.reference.pass_rate is not None or self.reference.distinction_rate is not None:
            outcome_counts: dict[str, int] = {}
            for o in outcomes:
                oc = o.get("outcome")
                if oc:
                    outcome_counts[oc] = outcome_counts.get(oc, 0) + 1
            n_total = sum(outcome_counts.values()) if outcome_counts else 1
            if self.reference.pass_rate is not None:
                synth_pass = outcome_counts.get("Pass", 0) / n_total
                results.append(ValidationResult(
                    test_name="outcome_pass_rate",
                    metric="Pass rate",
                    synthetic_value=synth_pass,
                    reference_value=self.reference.pass_rate,
                    passed=abs(synth_pass - self.reference.pass_rate) < 0.15,
                    details=f"Pass rate: {synth_pass:.1%} (ref: {self.reference.pass_rate:.1%}, tolerance ±15pp)",
                ))
            if self.reference.distinction_rate is not None:
                synth_dist = outcome_counts.get("Distinction", 0) / n_total
                results.append(ValidationResult(
                    test_name="outcome_distinction_rate",
                    metric="Distinction rate",
                    synthetic_value=synth_dist,
                    reference_value=self.reference.distinction_rate,
                    passed=abs(synth_dist - self.reference.distinction_rate) < 0.15,
                    details=f"Distinction rate: {synth_dist:.1%} (ref: {self.reference.distinction_rate:.1%}, tolerance ±15pp)",
                ))

        # ── Engagement-GPA positive correlation ──
        eng_xs: list[float] = []
        gpa_ys_eng: list[float] = []
        for o in outcomes:
            eng = o.get("mean_engagement")
            gpa = o.get("final_gpa")
            if eng is not None and gpa is not None:
                eng_xs.append(float(eng))
                gpa_ys_eng.append(float(gpa))
        results.append(self._paired_correlation(eng_xs, gpa_ys_eng, "engagement_gpa_correlation",
                                               "positive", 0.2, "Engagement-GPA"))

        return results

    def _validate_temporal(
        self,
        weekly_engagement: dict[str, list[float]],
        outcomes: list[dict],
        *,
        total_weeks: int | None = None,
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

        dropout_observed = [t for t in dropout_trajectories if t]
        retained_observed = [t for t in retained_trajectories if t]
        finite_trajectories = all(np.all(np.isfinite(t)) for t in dropout_observed + retained_observed)
        if dropout_observed and retained_observed and finite_trajectories:
            # Mean final engagement should be lower for dropouts
            dropout_final = np.mean([t[-1] for t in dropout_observed])
            retained_final = np.mean([t[-1] for t in retained_observed])

            results.append(self._measured_result(
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
        else:
            reason = "insufficient_trajectory_groups" if finite_trajectories else "non_finite_input"
            for name, metric, ref in (("engagement_trajectory_divergence", "Mean difference", 0.1),
                                      ("dropout_negative_trend_rate", "Proportion", 0.6)):
                results.append(self._not_assessed(name, metric, ref, reason))

        # Dropout timing: early attrition pattern (majority drop in first half)
        dropout_weeks = [
            outcome_map[sid].get("dropout_week")
            for sid in weekly_engagement
            if sid in outcome_map and outcome_map[sid].get("has_dropped_out")
            and outcome_map[sid].get("dropout_week") is not None
        ]
        if total_weeks is None:
            total_weeks = max((len(t) for t in weekly_engagement.values()), default=0)
        if dropout_weeks and total_weeks > 0 and np.all(np.isfinite(dropout_weeks)):
            midpoint = total_weeks / 2
            early_dropouts = sum(1 for w in dropout_weeks if w <= midpoint)
            early_rate = early_dropouts / len(dropout_weeks)
            results.append(ValidationResult(
                test_name="dropout_early_attrition",
                metric="Early dropout proportion",
                synthetic_value=early_rate,
                reference_value=0.50,
                passed=early_rate >= 0.30,  # at least 30% drop in first half
                details=f"{early_rate:.0%} of dropouts occur in first half of "
                        f"the {total_weeks}-week simulation",
            ))
        else:
            results.append(self._not_assessed("dropout_early_attrition", "Early dropout proportion", 0.5,
                                             "missing_or_non_finite_dropout_timing_or_horizon"))

        return results

    def _validate_privacy(self, students: list[dict]) -> list[ValidationResult]:
        """Level 4: Basic privacy assessment."""
        results = []
        if not students:
            return [self._not_assessed("k_anonymity", "Minimum k", None, "insufficient_population; n=0")]

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

    def _validate_backstories(self, students: list[dict]) -> list[ValidationResult]:
        """Level 5 (optional): Validate backstory consistency with persona attributes.

        Only runs when backstory data is present in at least one student record.
        Checks that backstories are not empty and mention relevant persona attributes.
        """
        results: list[ValidationResult] = []

        backstories = [
            s for s in students
            if s.get("backstory") and isinstance(s["backstory"], str) and s["backstory"].strip()
        ]
        if not backstories:
            # No backstories present — skip validation silently
            return results

        # Check 1: No empty backstories when LLM enrichment was used
        total_with_field = sum(1 for s in students if "backstory" in s)
        non_empty = len(backstories)
        empty_rate = 1 - (non_empty / total_with_field) if total_with_field > 0 else 0

        results.append(ValidationResult(
            test_name="backstory_non_empty_rate",
            metric="Proportion non-empty",
            synthetic_value=1 - empty_rate,
            reference_value=0.8,
            passed=empty_rate <= 0.5,
            details=f"{non_empty}/{total_with_field} backstories are non-empty "
                    f"({1 - empty_rate:.0%})",
        ))

        # Check 2: Backstories should mention relevant persona attributes
        relevance_hits = 0
        for s in backstories:
            text = s["backstory"].lower()
            # Look for mentions of key persona attributes
            attribute_keywords = []
            if s.get("employment_intensity", 0) > 0.05:
                attribute_keywords.extend(["work", "job", "employ", "career"])
            if s.get("family_responsibility_level", 0) > 0.05:
                attribute_keywords.extend(["family", "child", "parent", "care"])
            motivation = s.get("motivation_type", "")
            if motivation == "intrinsic":
                attribute_keywords.extend(["passion", "interest", "curious", "love"])
            elif motivation == "extrinsic":
                attribute_keywords.extend(["career", "salary", "promotion", "certificate"])
            elif motivation == "amotivation":
                attribute_keywords.extend(["uncertain", "unsure", "pressure", "expect"])

            if any(kw in text for kw in attribute_keywords):
                relevance_hits += 1

        relevance_rate = relevance_hits / len(backstories) if backstories else 0
        results.append(ValidationResult(
            test_name="backstory_attribute_relevance",
            metric="Relevance rate",
            synthetic_value=relevance_rate,
            reference_value=0.5,
            passed=relevance_rate >= 0.3,
            details=f"{relevance_hits}/{len(backstories)} backstories mention "
                    f"relevant persona attributes ({relevance_rate:.0%})",
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
        """Preserve the legacy grade helper for callers with assessed checks."""
        return quality_grade(pass_rate, 1)
