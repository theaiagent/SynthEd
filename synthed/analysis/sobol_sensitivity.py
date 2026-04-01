"""
Sobol sensitivity analysis for SynthEd simulation parameters.

Performs variance-based global sensitivity analysis using Sobol indices
(Saltelli et al., 2010) to identify which parameters most influence
dropout rate, engagement distribution, and GPA distribution.

Unlike OAT (one-at-a-time) sweeps, Sobol captures interaction effects
between parameters, revealing non-linear dependencies.

Requires: SALib (pip install SALib)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields

import numpy as np
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample

from ..agents.persona import PersonaConfig
from ._sim_runner import MODULE_ALIASES, run_simulation_with_overrides

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Parameter space definition
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class SobolParameter:
    """A single parameter in the Sobol analysis space."""
    name: str           # unique identifier, e.g. "config.employment_rate"
    lower: float        # lower bound
    upper: float        # upper bound
    description: str    # human-readable purpose
    log_scale: bool = False       # Phase 2: Optuna log-uniform sampling
    step: float | None = None     # Phase 2: discretization step

    def __post_init__(self):
        if self.lower >= self.upper:
            raise ValueError(
                f"SobolParameter '{self.name}': lower ({self.lower}) must be < upper ({self.upper})"
            )


# Prefix convention:
#   "config."   → PersonaConfig attribute
#   "engine."   → SimulationEngine class-level constant
#   "tinto."    → engine.tinto attribute
#   "bean."     → engine.bean_metzner attribute
#   "kember."   → engine.kember attribute
#   "baulke."   → engine.baulke attribute
#   "sdt."      → engine.sdt attribute
#   "rovai."    → engine.rovai attribute
#   "garrison." → engine.garrison attribute
#   "gonzalez." → engine.gonzalez attribute
#   "moore."    → engine.moore attribute
#   "epstein."  → engine.epstein_axtell attribute

# Full parameter space: 52 parameters selected for theoretical importance
# and empirical impact on dropout/engagement/GPA outcomes.
SOBOL_PARAMETER_SPACE: tuple[SobolParameter, ...] = (
    # ── PersonaConfig: Population characteristics ──
    SobolParameter("config.employment_rate", 0.40, 0.95, "Employment prevalence"),
    SobolParameter("config.financial_stress_mean", 0.20, 0.80, "Mean financial stress"),
    SobolParameter("config.self_regulation_mean", 0.20, 0.70, "Mean self-regulation"),
    SobolParameter("config.digital_literacy_mean", 0.30, 0.80, "Mean digital literacy"),
    SobolParameter("config.dropout_base_rate", 0.40, 0.95, "Dropout risk scaling base"),
    SobolParameter("config.has_family_rate", 0.20, 0.70, "Family responsibility rate"),
    SobolParameter("config.prior_gpa_mean", 1.5, 3.5, "Mean prior GPA"),
    SobolParameter("config.disability_rate", 0.02, 0.20, "Disability prevalence"),

    # ── Engine: Engagement update weights ──
    SobolParameter("engine._TINTO_ACADEMIC_WEIGHT", 0.02, 0.12, "Academic integration → engagement"),
    SobolParameter("engine._TINTO_SOCIAL_WEIGHT", 0.005, 0.05, "Social integration → engagement"),
    SobolParameter("engine._TINTO_DECAY_BASE", 0.02, 0.10, "Weekly engagement decay"),
    SobolParameter("engine._MOTIVATION_INTRINSIC_BOOST", 0.005, 0.04, "Intrinsic motivation boost"),
    SobolParameter("engine._MOTIVATION_AMOTIVATION_PENALTY", 0.01, 0.05, "Amotivation penalty"),
    SobolParameter("engine._TD_EFFECT_FACTOR", 0.01, 0.06, "Transactional distance effect"),
    SobolParameter("engine._CB_FEEDBACK_FACTOR", 0.005, 0.04, "Cost-benefit feedback"),
    SobolParameter("engine._MISSED_STREAK_PENALTY", 0.01, 0.08, "Missed assignment streak erosion"),

    # ── Bean & Metzner: Environmental pressure ──
    SobolParameter("bean._OVERWORK_PENALTY", 0.01, 0.05, "Overwork engagement erosion"),
    SobolParameter("bean._FAMILY_PENALTY", 0.005, 0.04, "Family responsibility penalty"),
    SobolParameter("bean._FINANCIAL_PENALTY", 0.005, 0.03, "Financial stress penalty"),
    SobolParameter("bean._DISABILITY_PENALTY", 0.005, 0.03, "Disability engagement erosion"),

    # ── Kember: Cost-benefit ──
    SobolParameter("kember._QUALITY_FACTOR", 0.01, 0.08, "Quality → cost-benefit sensitivity"),
    SobolParameter("kember._MISSED_PENALTY", 0.01, 0.06, "Missed assignment → cost-benefit"),
    SobolParameter("kember._GPA_CB_FACTOR", 0.003, 0.02, "GPA → cost-benefit sensitivity"),

    # ── Baulke: Dropout phase thresholds ──
    SobolParameter("baulke._NONFIT_ENG_THRESHOLD", 0.30, 0.55, "Non-fit perception trigger"),
    SobolParameter("baulke._DECISION_RISK_MULTIPLIER", 0.10, 0.50, "Phase 5 risk multiplier"),
    SobolParameter("baulke._PHASE_2_TO_3_ENG", 0.20, 0.45, "Phase 2→3 threshold"),
    SobolParameter("baulke._PHASE_3_TO_4_ENG", 0.15, 0.35, "Phase 3→4 threshold"),

    # ── SDT: Motivation dynamics ──
    SobolParameter("sdt._COMPETENCE_QUALITY_FACTOR", 0.02, 0.10, "Quality → competence need"),
    SobolParameter("sdt._COMPETENCE_EROSION", 0.005, 0.04, "Competence erosion rate"),
    SobolParameter("sdt._COMPETENCE_GPA_FACTOR", 0.003, 0.015, "GPA → competence anchoring"),
    SobolParameter("sdt._INTRINSIC_THRESHOLD", 0.45, 0.75, "Threshold for intrinsic shift"),

    # ── Rovai: Persistence ──
    SobolParameter("rovai._REGULATION_FACTOR", 0.01, 0.06, "Self-regulation → engagement buffer"),
    SobolParameter("rovai._FLOOR_SCALE", 0.30, 0.70, "Engagement floor scale"),
    SobolParameter("rovai._DISABILITY_FLOOR_PENALTY", 0.20, 0.60, "Disability floor penalty"),

    # ── Tinto: Integration ──
    SobolParameter("tinto._ACADEMIC_QUALITY_FACTOR", 0.02, 0.10, "Quality → academic integration"),
    SobolParameter("tinto._ACADEMIC_EROSION", 0.005, 0.04, "Academic integration erosion"),
    SobolParameter("tinto._ISOLATION_EROSION", 0.01, 0.06, "Social isolation erosion"),

    # ── Gonzalez: Academic exhaustion ──
    SobolParameter("gonzalez._ASSIGNMENT_LOAD_WEIGHT", 0.01, 0.05, "Assignment load → exhaustion"),
    SobolParameter("gonzalez._RECOVERY_BASE", 0.01, 0.06, "Exhaustion recovery rate"),
    SobolParameter("gonzalez._ENGAGEMENT_IMPACT", 0.01, 0.08, "Exhaustion → engagement drag"),
    SobolParameter("gonzalez._DROPOUT_THRESHOLD", 0.50, 0.85, "Exhaustion dropout threshold"),

    # ── Garrison: Community of Inquiry ──
    SobolParameter("garrison._SOCIAL_DECAY", 0.005, 0.04, "Social presence weekly decay"),
    SobolParameter("garrison._COGNITIVE_QUALITY_FACTOR", 0.01, 0.08, "Quality → cognitive presence"),

    # ── Moore: Transactional distance ──
    SobolParameter("moore._STRUCTURE_WEIGHT", 0.15, 0.50, "Course structure → TD"),
    SobolParameter("moore._DIALOGUE_WEIGHT", 0.15, 0.45, "Dialogue → TD reduction"),

    # ── Engine: Assignment/Exam quality weights (GPA drivers) ──
    SobolParameter("engine._ASSIGN_GPA_WEIGHT", 0.10, 0.40, "Prior GPA → assignment quality"),
    SobolParameter("engine._ASSIGN_ENG_WEIGHT", 0.10, 0.40, "Engagement → assignment quality"),
    SobolParameter("engine._ASSIGN_EFFICACY_WEIGHT", 0.05, 0.35, "Self-efficacy → assignment quality"),
    SobolParameter("engine._EXAM_GPA_WEIGHT", 0.05, 0.35, "Prior GPA → exam quality"),
    SobolParameter("engine._EXAM_ENG_WEIGHT", 0.05, 0.35, "Engagement → exam quality"),
    SobolParameter("engine._EXAM_EFFICACY_WEIGHT", 0.05, 0.35, "Self-efficacy → exam quality"),
    SobolParameter("engine._ASSIGN_SUBMIT_BASE", 0.15, 0.50, "Base assignment submission probability"),
    SobolParameter("engine._GRADE_FLOOR", 0.30, 0.55, "Structural grade floor (partial credit)"),
)


# ─────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class SobolResult:
    """Sobol sensitivity indices for a single output metric."""
    metric: str                         # "dropout_rate", "mean_engagement", "mean_gpa"
    parameter_names: tuple[str, ...]    # parameter names in order
    s1: tuple[float, ...]              # first-order indices
    s1_conf: tuple[float, ...]         # first-order confidence intervals
    st: tuple[float, ...]              # total-order indices
    st_conf: tuple[float, ...]         # total-order confidence intervals
    n_simulations: int                  # total simulations run


@dataclass(frozen=True)
class SobolRanking:
    """Ranked parameter importance for a single metric."""
    parameter: str
    s1: float           # first-order (direct effect)
    st: float           # total-order (direct + interaction effects)
    interaction: float  # st - s1 (pure interaction contribution)
    rank: int           # 1 = most important


# ─────────────────────────────────────────────
# Analyzer
# ─────────────────────────────────────────────

class SobolAnalyzer:
    """
    Variance-based global sensitivity analysis for SynthEd.

    Uses Saltelli sampling (SALib) to efficiently explore the parameter
    space and compute Sobol first-order (S1) and total-order (ST) indices.

    S1: fraction of output variance explained by parameter alone.
    ST: fraction of output variance explained by parameter + all interactions.
    ST - S1: pure interaction contribution.

    Usage:
        analyzer = SobolAnalyzer(n_students=200, seed=42)
        results = analyzer.run(n_samples=128)
        rankings = analyzer.rank(results[0])
    """

    def __init__(
        self,
        n_students: int = 200,
        seed: int = 42,
        parameters: tuple[SobolParameter, ...] | None = None,
    ):
        self.n_students = n_students
        self.seed = seed
        self.parameters = parameters or SOBOL_PARAMETER_SPACE
        self._problem = self._build_problem()
        self._default_config = PersonaConfig()  # cached to avoid repeated construction
        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Verify all parameter names resolve to real attributes.

        Catches typos and stale names at setup time rather than after
        thousands of simulations produce meaningless indices.
        """
        from ..simulation.engine import SimulationEngine
        from ..simulation.environment import ODLEnvironment

        config_fields = {f.name for f in fields(PersonaConfig)}
        engine = SimulationEngine(environment=ODLEnvironment(), seed=0)

        for p in self.parameters:
            prefix, _, attr = p.name.partition(".")
            if prefix == "config":
                if attr not in config_fields:
                    raise ValueError(f"Unknown PersonaConfig field: '{attr}' in {p.name}")
            elif prefix == "engine":
                if not hasattr(engine, attr):
                    raise ValueError(f"Unknown engine attribute: '{attr}' in {p.name}")
            elif prefix in MODULE_ALIASES:
                module = getattr(engine, MODULE_ALIASES[prefix])
                if not hasattr(module, attr):
                    raise ValueError(
                        f"Unknown attribute '{attr}' on {prefix} module in {p.name}"
                    )
            else:
                raise ValueError(f"Unknown parameter prefix: '{prefix}' in {p.name}")

    def _build_problem(self) -> dict:
        """Build SALib problem definition from parameter space."""
        return {
            "num_vars": len(self.parameters),
            "names": [p.name for p in self.parameters],
            "bounds": [[p.lower, p.upper] for p in self.parameters],
        }

    def generate_samples(self, n_samples: int = 128) -> np.ndarray:
        """
        Generate Sobol (Saltelli) sample matrix.

        With calc_second_order=False, total = n_samples * (D + 2).
        Default: 128 * (44 + 2) = 5,888 simulations.
        """
        return sobol_sample.sample(self._problem, n_samples, calc_second_order=False)

    def run(
        self,
        n_samples: int = 128,
        sample_matrix: np.ndarray | None = None,
    ) -> list[SobolResult]:
        """
        Run full Sobol analysis: sample → simulate → analyze.

        Args:
            n_samples: Base sample count for Sobol (total = n*(D+2)).
            sample_matrix: Pre-generated sample matrix (overrides n_samples).

        Returns:
            List of SobolResult for each output metric:
            [dropout_rate, mean_engagement, mean_gpa].
        """
        samples = sample_matrix if sample_matrix is not None else self.generate_samples(n_samples)
        n_total = len(samples)
        logger.info(
            "Sobol analysis: %d parameters, %d simulations (N=%d)",
            len(self.parameters), n_total, n_samples,
        )

        # Run all simulations
        outputs = self._run_simulations(samples)
        dropout_rates = np.array([o["dropout_rate"] for o in outputs])
        mean_engagements = np.array([o["mean_engagement"] for o in outputs])
        mean_gpas = np.array([o["mean_gpa"] for o in outputs])

        # Compute Sobol indices for each metric
        results = []
        for metric_name, metric_values in [
            ("dropout_rate", dropout_rates),
            ("mean_engagement", mean_engagements),
            ("mean_gpa", mean_gpas),
        ]:
            si = sobol_analyze.analyze(
                self._problem, metric_values, calc_second_order=False,
            )
            results.append(SobolResult(
                metric=metric_name,
                parameter_names=tuple(self._problem["names"]),
                s1=tuple(float(v) for v in si["S1"]),
                s1_conf=tuple(float(v) for v in si["S1_conf"]),
                st=tuple(float(v) for v in si["ST"]),
                st_conf=tuple(float(v) for v in si["ST_conf"]),
                n_simulations=n_total,
            ))

        return results

    def rank(self, result: SobolResult, top_n: int | None = None) -> list[SobolRanking]:
        """
        Rank parameters by total-order index (ST) for a given metric.

        Args:
            result: SobolResult from run().
            top_n: Return only top N parameters (None = all).

        Returns:
            Sorted list of SobolRanking, most important first.
        """
        rankings = []
        for i, name in enumerate(result.parameter_names):
            s1_val = max(0.0, result.s1[i])  # clip negative noise
            st_val = max(0.0, result.st[i])
            rankings.append(SobolRanking(
                parameter=name,
                s1=round(s1_val, 4),
                st=round(st_val, 4),
                interaction=round(max(0.0, st_val - s1_val), 4),
                rank=0,
            ))

        rankings.sort(key=lambda r: r.st, reverse=True)

        ranked = []
        for i, r in enumerate(rankings):
            ranked.append(SobolRanking(
                parameter=r.parameter,
                s1=r.s1,
                st=r.st,
                interaction=r.interaction,
                rank=i + 1,
            ))

        if top_n is not None:
            return ranked[:top_n]
        return ranked

    # ─────────────────────────────────────────
    # Internal: simulation runner
    # ─────────────────────────────────────────

    def _run_simulations(self, samples: np.ndarray) -> list[dict]:
        """Run one simulation per sample row, collecting output metrics."""
        outputs = []
        n_total = len(samples)
        log_interval = max(1, n_total // 20)  # log every 5%

        for i, row in enumerate(samples):
            overrides = dict(zip(self._problem["names"], row))
            result = run_simulation_with_overrides(
                overrides, self.n_students, self.seed, self._default_config,
            )
            outputs.append(result)

            if (i + 1) % log_interval == 0:
                pct = (i + 1) / n_total * 100
                logger.info("  Progress: %d/%d (%.0f%%)", i + 1, n_total, pct)

        return outputs
