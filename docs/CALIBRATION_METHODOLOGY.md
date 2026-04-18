# SynthEd Calibration Methodology

> Reference document for the NSGA-II calibration pipeline.

## 1. Overview

SynthEd calibrates 68 tunable simulation parameters spanning 13 modules (engine, theory anchors, grading, institutional, persona) against the Open University Learning Analytics Dataset (OULAD; Kuzilek et al., 2017) using a three-stage pipeline. After Sobol screening, 20 of these are actively optimized by NSGA-II; the remainder are fixed at profile defaults. (Note: the dashboard's "Engine Constants" panel exposes all 70 fields of the `EngineConfig` dataclass; only 15 of those are in the Sobol candidate set.)

```
Sobol Global Sensitivity Analysis → NSGA-II Multi-Objective Optimization → Cross-Seed Validation
```

This document explains why each method was chosen, how parameters were selected, and the statistical power analysis supporting those choices.

## 2. Why Sobol Global Sensitivity Analysis?

### Purpose

Before optimization, we must identify which of the 68 tunable parameters meaningfully affect simulation outputs. Optimizing all 68 simultaneously would require an intractable search budget. Sobol analysis decomposes the total output variance into contributions from individual parameters and their interactions.

### Why Sobol over alternatives?

| Method | Pros | Cons | Verdict |
|--------|------|------|---------|
| **One-at-a-Time (OAT)** | Simple, fast | Misses interactions; assumes linear effects | Insufficient for nonlinear ABM |
| **Morris screening** | Efficient for large D | Qualitative (ranks, not quantifies); no interaction decomposition | Screening only |
| **Sobol (variance-based)** | Quantifies total contribution including all interactions via Total-order index (ST); model-free | Computationally expensive: N×(D+2) simulations | **Selected** |
| **FAST/eFAST** | Efficient for first-order | Poor interaction estimation for high D | Not suitable |

Sobol was selected because:
1. **Total-order indices (ST)** capture both direct effects and all interactions with other parameters — critical for an Agent-Based Model (ABM) with nonlinear theory module interactions
2. **Model-free** — no assumptions about functional form
3. **Quantitative** — provides numerical variance fractions, not just rankings
4. **Well-established** in ABM calibration literature (Ligmann-Zielinska et al., 2020; Ten Broeke et al., 2016)

### Saltelli Sampling Scheme

We use the Saltelli (2002) quasi-random sampling scheme with `calc_second_order=False`:

```
Total simulations = n_samples × (D + 2)
```

where D = 68 parameters. This generates a base sample matrix and D perturbation matrices, allowing efficient computation of both S1 (first-order) and ST (total-order) indices.

**Reference:** Saltelli, A. (2002). "Making best use of model evaluations to compute sensitivity indices." *Computer Physics Communications*, 145(2), 280-297.

### Parameter: `n_samples = 512`

**Justification:**

The confidence interval width for Sobol indices scales as:

```
SE(ST) ≈ c / √n_samples
```

where c ∈ [0.5, 1.0] is problem-dependent (Archer et al., 1997).

| n_samples | CI half-width (c=0.75) | Min detectable ST | Total sims |
|-----------|------------------------|-------------------|------------|
| 128 | 0.130 | 0.130 | 8,960 |
| 256 | 0.092 | 0.092 | 17,920 |
| **512** | **0.065** | **0.065** | **35,840** |
| 1024 | 0.046 | 0.046 | 71,680 |

At n_samples=128, parameters with ST < 0.13 cannot be distinguished from zero. This means the ranking of parameters in positions 10-30 (typically ST ∈ [0.02, 0.10]) is unreliable.

At n_samples=512, parameters with ST > 0.065 are reliably detected. This covers the inclusion threshold of ST > 0.05 recommended by Iooss & Lemaître (2015).

Saltelli et al. (2008) recommend n_samples ≥ 500 for D > 50, and n_samples ≥ 10×D for first-order indices. Our choice of 512 satisfies the first criterion and yields N/D = 512/68 = 7.5, approaching the 10× recommendation.

**References:**
- Saltelli, A. et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley.
- Archer, G.E.B., Saltelli, A., & Sobol, I.M. (1997). "Sensitivity measures, ANOVA-like techniques and the use of bootstrap." *Journal of Statistical Computation and Simulation*, 58(2), 99-120.
- Iooss, B. & Lemaitre, P. (2015). "A review on global sensitivity analysis methods." In *Uncertainty Management in Simulation-Optimization of Complex Systems*, Springer.

### Parameter: `sobol_top_n = 20`

After Sobol analysis, the top 20 parameters by ST are selected for NSGA-II optimization. The remaining 48 are fixed at profile defaults.

**Force-included parameters:** Because Sobol ranks parameters by dropout_rate sensitivity, GPA-affecting parameters may rank low despite being critical for the GPA objective. Four grading parameters are force-included regardless of Sobol rank:

- `grading.grade_floor` — most direct GPA lever: `floor + (1-floor) * quality`
- `grading.pass_threshold` — affects Pass/Fail/Distinction classification
- `engine._ASSIGN_GPA_WEIGHT` — prior GPA influence on assignment quality
- `engine._EXAM_GPA_WEIGHT` — prior GPA influence on exam quality

These 4 force-included parameters count toward the top-20 budget (4 forced + 16 from Sobol ranking = 20 total), keeping search dimensionality constant.

> **Note:** This force-include set is specific to the current SynthEd grading formula and OULAD calibration target. The authoritative list is maintained in `run_calibration.py::GPA_FORCE_INCLUDE`. If the engine's grading model is refactored or alternative institutional profiles with different GPA calculation strategies are introduced, this list should be reviewed for applicability.

**Justification:**
- With 68 parameters, the Pareto principle typically applies: 20-30% of parameters explain 80%+ of output variance
- ST already includes all interaction effects — a parameter with ST = 0.005 contributes at most 0.5% of variance through any combination of interactions
- The `config.*` (PersonaConfig) and `inst.*` (InstitutionalConfig) parameters are excluded from optimization (fixed per profile), effectively reducing the candidate pool to ~55 parameters
- Force-include ensures NSGA-II has levers for both objectives (dropout_error and gpa_error), preventing the optimizer from being blind to GPA

**Validation criterion:** The cumulative ST of the top 20 parameters must explain ≥ 90% of total variance. If < 70%, increase to 25-30 and raise n_trials proportionally.

**Reference:** Saltelli, A. et al. (2010). "Variance based sensitivity analysis of model output." *Computer Physics Communications*, 181(2), 259-270.

## 3. Why NSGA-II Multi-Objective Optimization?

### Purpose

Find engine constant values that simultaneously minimize:
1. **Dropout error:** |achieved_dropout - target_dropout| where target_dropout = 0.312 (OULAD Withdrawn rate)
2. **GPA error:** |achieved_gpa - target_gpa| where target_gpa = 3.03 (OULAD assessment score 75.80/100 × 4.0)

subject to constraints:
- engagement ≥ 0.1 (hard floor)
- dropout_rate ∈ [0.20, 0.45] (feasibility range)

### Why NSGA-II over alternatives?

| Method | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Grid search** | Exhaustive | Curse of dimensionality: 10^20 grid points for 20D | Infeasible |
| **Bayesian (TPE/GP)** | Sample-efficient | Single-objective; multi-objective variants immature | Not ideal for 2-obj |
| **NSGA-II** | Native multi-objective; constraint handling; well-studied convergence | Requires population-level evaluation budget | **Selected** |
| **NSGA-III** | Better for 3+ objectives | Overkill for 2 objectives; similar cost | Unnecessary |
| **MOEA/D** | Good decomposition | Less intuitive knee-point selection | No advantage |

NSGA-II was selected because:
1. **Native bi-objective optimization** — produces a Pareto front of non-dominated solutions
2. **Constraint handling** via feasibility-first tournament selection
3. **Knee-point selection** — the geometric knee of the Pareto front represents the best compromise between objectives
4. **Well-established** in simulation calibration (Deb et al., 2002; Deb & Jain, 2014)

### Implementation

We use Optuna's `NSGAIISampler` with ask/tell API for batch parallelism:

```python
sampler = NSGAIISampler(seed=seed)
study = optuna.create_study(
    directions=["minimize", "minimize"],  # dropout_error, gpa_error
    sampler=sampler,
)
```

**Reference:** Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). "A fast and elitist multiobjective genetic algorithm: NSGA-II." *IEEE Transactions on Evolutionary Computation*, 6(2), 182-197.

### Parameter: `n_students = 500`

Each NSGA-II evaluation simulates N students for 14 weeks. The achieved dropout_rate is a binomial proportion with standard error:

```
SE(p) = √(p(1-p)/N)
```

**Power analysis (α=0.05, two-sided, power=0.80):**

```
Required N = (z_{α/2} + z_β)² × p(1-p) / δ²
           = (1.96 + 0.842)² × 0.312 × 0.688 / δ²
           = 7.849 × 0.2147 / δ²
```

| Effect size (δ) | Required N | Interpretation |
|-----------------|------------|----------------|
| 3 pp (0.03) | 1,872 | Fine-grained calibration |
| 5 pp (0.05) | 674 | Moderate calibration |
| 7 pp (0.07) | 344 | Coarse calibration |
| 10 pp (0.10) | 169 | Rough calibration |

**Standard error at selected N values:**

| N | SE | 95% CI half-width | MDE (power=0.80) |
|---|----|--------------------|-------------------|
| 100 | 4.63% | ±9.08% | 12.98 pp |
| 200 | 3.28% | ±6.42% | 9.18 pp |
| 300 | 2.68% | ±5.25% | 7.50 pp |
| **500** | **2.07%** | **±4.06%** | **5.80 pp** |
| 750 | 1.69% | ±3.32% | 4.74 pp |
| 1000 | 1.47% | ±2.87% | 4.11 pp |

**Decision rationale:** N=500 (SE=2.07%) is the pragmatic optimum. It provides:
- MDE of 5.8 pp — sufficient for NSGA-II to distinguish meaningfully different parameter sets
- Signal-to-Noise Ratio (SNR) ≈ 2.4 for 5pp differences — workable with evolutionary selection pressure over 310 generations
- Acceptable computational cost per evaluation (~0.9 seconds)

Going to N=750 (SE=1.69%) would improve discriminability but increase total compute by 50% with diminishing returns for the optimizer.

**Reference:** Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley.

### Parameter: `pop_size = 200`

The NSGA-II population size determines genetic diversity and Pareto front coverage.

**Rule of thumb (Deb et al., 2002):**
```
pop_size ≥ 10 × D  (D = number of decision variables)
```

With D=20 optimized parameters: 10 × 20 = 200.

For problems with constraints (we have 3), additional population diversity is needed to maintain feasible solutions. Our 200 exactly meets the 10D threshold.

With only 2 objectives, larger populations are not necessary for diversity (unlike 3+ objective problems where NSGA-III with reference points would be needed).

### Parameter: `n_trials = 62,000`

Total function evaluations. At pop_size=200, this yields 310 generations.

**Convergence analysis:**

The Evolutionary Multi-Objective Optimization (EMO) literature recommends 10D-20D generations for convergence (Deb & Jain, 2014; Ishibuchi et al., 2017):

```
Minimum generations: 10 × D = 10 × 20 = 200 → n_trials = 40,000
Upper bound:         20 × D = 20 × 20 = 400 → n_trials = 80,000
```

**Noise Amplification Factor (NAF):**

In stochastic optimization, each fitness evaluation contains Monte Carlo noise. The Noise Amplification Factor (NAF) quantifies how much additional computational budget is needed compared to a noise-free problem (Jin & Branke, 2005):

```
NAF = 1 + σ_noise² / σ_signal²
```

where:
- σ_noise = Standard Error (SE) of a single simulation's dropout_rate = 0.0207 (at N=500, p=0.312)
- σ_signal = standard deviation of the true objective function (dropout_error) across solutions that the optimizer must discriminate between

The value of σ_signal depends on the optimization phase:

| Phase | σ_signal | NAF | Interpretation |
|-------|----------|-----|----------------|
| Global exploration (early generations) | 0.040 | 1.27 | Solutions span the full feasible range [0.20, 0.45]; large fitness differences are easy to detect |
| Mid-convergence | 0.03 | 1.48 | Population clusters near the optimum; moderate differences remain |
| Near-optimum refinement (late generations) | 0.02 | 2.07 | Competing solutions differ by only 2-3 percentage points; noise dominates |

**Global σ_signal derivation:** In the feasible region, dropout_error = |achieved - 0.312| ranges from 0 to 0.138 in [0.20, 0.45]. Under uniform coverage: σ = 0.138/√12 ≈ 0.040.

**Budget computation using the conservative mid-convergence estimate (σ_signal = 0.03):**

```
NAF = 1 + 0.0207² / 0.03² = 1 + 0.000428 / 0.0009 = 1.48

Minimum evaluations = pop_size × 10D × NAF
                    = 200 × 200 × 1.48
                    = 59,200
```

**Our choice of 62,000** exceeds this conservative estimate (59,200), providing additional margin. This ensures adequate budget not only for global exploration but also for the mid-convergence phase where population refinement occurs.

Additionally, the **re-evaluation step** provides a second layer of noise mitigation: after NSGA-II completes, every Pareto front solution is re-evaluated at N=2,000 (SE=1.04%), eliminating noise-induced errors in knee-point selection. This two-phase strategy is well-established in noisy optimization (Jin & Branke, 2005): use a principled evaluation budget for search, then re-evaluate the final solution set with higher fidelity.

At pop_size=200, 62,000 evaluations yield 310 generations — comfortably within the Deb (2002) recommended range of 10D-20D generations (200-400).

**Convergence verification:** Hypervolume Indicator (HV) tracking per generation. Convergence is declared when HV improvement < 0.1% over 20 consecutive generations. If convergence is reached before generation 310, the remaining generations serve as confirmation of stability.

**References:**
- Jin, Y. & Branke, J. (2005). "Evolutionary optimization in uncertain environments — a survey." *IEEE Transactions on Evolutionary Computation*, 9(3), 303-317.
- Ishibuchi, H., Imada, R., Setoguchi, Y., & Nojima, Y. (2017). "How to specify a reference point in hypervolume calculation." *GECCO 2017*.

### Strengthening: Re-evaluation and Replication

**Re-evaluation (N=2,000):** After NSGA-II completes, each Pareto front solution is re-evaluated with N=2,000 students. This reduces the SE of each solution's objectives from 2.07% (N=500) to 1.04% (N=2,000), ensuring the knee-point selection is not distorted by calibration-phase noise.

**Replicated calibration:** The full NSGA-II is run with two different optimizer seeds (42 and 2024). The cross-seed knee-point distance (`compare_knee_points` in `pareto_utils.py`) is reported as an **informational** measurement — the historical "robust if < 0.1" rule was a heuristic, not a Fisher Information-derived threshold. Cross-seed parameter divergence is the expected signature of the parameter non-identifiability discussed in §7.3 (20 free parameters fit to 2 scalar objectives), not evidence of optimizer failure. The Pareto front re-evaluation reduces noise-induced selection error in knee-point identification regardless of cross-seed parameter scatter.

## 4. Cross-Seed Validation

### Purpose

Verify that the calibrated parameters produce stable outputs across different random seeds — i.e., the results are driven by the calibrated parameters, not by stochastic artifacts.

### Parameter: `Validation N = 1,000`

```
SE = √(0.312 × 0.688 / 1000) = 1.47%
95% CI = ±1.96 × 0.0147 = ±2.87 pp
```

At N=1,000, a measured dropout of 31.2% has 95% CI [28.3%, 34.1%] — comfortably within the target range [20%, 45%].

For SE < 2%: N ≥ p(1-p) / 0.02² = 0.2147 / 0.0004 = 537. Our N=1,000 exceeds this with margin.

### Parameter: `Validation seeds = 10`

The inter-seed confidence interval uses a t-distribution with k-1 degrees of freedom:

```
CI = x̄ ± t_{α/2, k-1} × s / √k
```

**t-critical values and CI properties:**

| k (seeds) | df | t_{0.025, df} | CI factor (t/√k) | Relative width |
|-----------|-----|---------------|-------------------|----------------|
| 3 | 2 | 4.303 | 2.485 | 3.49× |
| 5 | 4 | 2.776 | 1.242 | 1.74× |
| **10** | **9** | **2.262** | **0.715** | **1.00×** |
| 15 | 14 | 2.145 | 0.554 | 0.77× |
| 20 | 19 | 2.093 | 0.468 | 0.65× |
| 30 | 29 | 2.045 | 0.373 | 0.52× |

At k=3 (current): df=2, t=4.303 — the CI is 3.5× wider than at k=10. With observed std=0.0133:
```
k=3:  CI half-width = 4.303 × 0.0133 / √3 = 0.0330 (3.30 pp)
k=10: CI half-width = 2.262 × 0.0133 / √10 = 0.0095 (0.95 pp)
```

**Tolerance interval (γ=0.95, 1-α=0.95):**

| k | k_tol (Howe, 1969) | Tolerance width (2 × k_tol × s) |
|---|-------------------|----------------------------------|
| 3 | 9.916 | 26.4 pp |
| 5 | 5.079 | 13.5 pp |
| **10** | **3.379** | **8.99 pp** |
| 15 | 2.954 | 7.86 pp |

At k=10, we can claim (95% confidence) that 95% of seeds produce dropout rates within a ~9 pp band around the mean. This is the operational tolerance interval.

**Decision rationale:** k=10 is the standard minimum for simulation output analysis (Law, 2015). It provides df=9 for the t-distribution (mild penalty vs. normal), a sub-1pp CI half-width on the mean, and a ~9pp tolerance interval.

**References:**
- Law, A.M. (2015). *Simulation Modeling and Analysis* (5th ed.). McGraw-Hill Education.
- Howe, W.G. (1969). "Two-sided tolerance limits for normal populations." *JASA*, 64(326), 610-620.

## 5. Complete Parameter Configuration

> **Note on defaults.** The values in this section reflect the **production calibration invocation** in `run_calibration.py` (full run, not `--quick`), which is the authoritative configuration cited throughout §2–§4. Direct calls to `NSGAIICalibrator.run()`, `SobolAnalyzer.run()`, or `NSGAIICalibrator.validate_solution()` use smaller method-signature defaults (`pop_size=80`, `n_trials=8000`, `n_samples=128`, `validation n_students=500`) intended for quick local testing. When reading the methodology, assume the `run_calibration.py` values unless a quick-run is explicitly discussed.

### Calibration Parameters

```python
# Sobol global sensitivity analysis
sobol_n_samples = 512          # Saltelli base count; total sims = 512 × (D + 2) = 512 × 70 = 35,840 for D = 68
sobol_n_students = 500         # Students per Sobol simulation
sobol_top_n = 20               # Top parameters selected for NSGA-II
gpa_force_include = {           # Always included regardless of Sobol rank
    # Note: OULAD/GPA-specific. If calibrating to non-GPA profiles, review applicability.
    # Authoritative source: run_calibration.py::GPA_FORCE_INCLUDE
    "grading.grade_floor",      # Direct GPA lever
    "grading.pass_threshold",   # Pass/Fail classification
    "engine._ASSIGN_GPA_WEIGHT",# GPA → assignment quality
    "engine._EXAM_GPA_WEIGHT",  # GPA → exam quality
}

# NSGA-II multi-objective optimization
nsga2_n_students = 500         # Students per NSGA-II evaluation
nsga2_pop_size = 200           # Population per generation (10D for D=20)
nsga2_n_trials = 62_000        # Total evaluations (310 generations)
nsga2_seeds = [42, 2024]       # Replicated calibration

# Re-evaluation
reeval_n_students = 2_000      # Per Pareto solution re-scoring
reeval_per_solution_seeds = 3  # Seeds per re-evaluation

# Validation
validation_n_students = 1_000  # Students per validation run
validation_seeds = [42, 123, 456, 789, 2024, 1337, 7777, 9999, 31415, 27182]

# Compute
workers = 1                    # CLI default (`--workers 1`); pass `--workers 8` on a 16-core host for ~50% utilization
```

### Computational Budget

| Stage | Simulations | N per sim | Est. time (8 workers) |
|-------|-------------|-----------|----------------------|
| Sobol | 35,840 | 500 | ~65 min |
| NSGA-II (seed 42) | 62,000 | 500 | ~210 min (measured: 12,749.9 s on the v1.7.0 run) |
| NSGA-II (seed 2024) | 62,000 | 500 | ~200 min (measured: 11,938.4 s on the v1.7.0 run) |
| Re-evaluation | ≤ pareto_size × 3 (typically 9–60) | 2,000 | ~1 min |
| Validation | 10 | 1,000 | <1 min |
| **Total** | **~160,000** | | **~8 hours** (measured on the v1.7.0 run with 8 workers) |

### Statistical Summary

| Metric | Value | Source |
|--------|-------|--------|
| Sobol Confidence Interval (CI) half-width on ST | ≤ 0.065 | n_samples=512, c=0.75 |
| NSGA-II fitness Standard Error (SE) on dropout | 2.07% | N=500, p=0.312 |
| NSGA-II Minimum Detectable Effect (MDE) | 5.8 pp | power=0.80, α=0.05 |
| NSGA-II generations | 310 | 62,000/200 |
| Validation CI half-width (mean) | 0.95 percentage points (pp) | k=10, s=0.0133, t=2.262 |
| Validation tolerance width (95/95) | 8.99 pp | k=10, k_tol=3.379 |
| SE < 2% threshold | N ≥ 537 | p(1-p)/0.02² |

## 6. Diagnostic Visualizations

The following diagnostic visualizations are **recommended** to accompany calibration results. As of v1.7.0 the calibration pipeline captures the raw data needed for most of them (e.g. `hv_history` per generation in each seed's output JSON, the full Pareto front in the same file, Sobol ST indices in the Sobol output), but chart *rendering* is deferred to the Phase 2 calibration release — see the Calibrate-tab placeholder in `synthed/dashboard/app.py` and the roadmap entry in `docs/superpowers/specs/2026-04-18-calibration-roadmap.md` for the planned implementation scope. Users who need these views immediately can build them from the JSON outputs in `calibration_output/`.

### 6.1 Implementation status (v1.7.0)

| # | Diagnostic | Data captured in v1.7.0 | Chart rendered |
|---|------------|-------------------------|----------------|
| 1 | HV convergence curve | ✅ `hv_history` in each `nsga2_default_seed*.json` | ❌ Planned (Phase 2) |
| 2 | Sobol ST bar chart with CI | ✅ Sobol output JSON (ST indices + bootstrap CI) | ❌ Planned (Phase 2) |
| 3 | Cumulative variance plot | ✅ Derivable from Sobol ST indices | ❌ Planned (Phase 2) |
| 4 | Pareto front scatter with knee | ✅ `pareto_front` + knee-point in seed JSON | ❌ Planned (Phase 2 — Calibrate tab) |
| 5 | Seed stability boxplot | ✅ 10-seed validation output | ❌ Planned (Phase 2) |
| 6 | Cohen's d effect sizes | ⚠️ Computable from validation output + OULAD reference | ❌ Planned (Phase 2) |
| 7 | Replicated calibration overlay | ✅ Both seed JSON files | ❌ Planned (Phase 2) |

### 6.2 Recommended diagnostics

1. **Hypervolume Indicator (HV) convergence curve** — HV vs. generation number for both NSGA-II seeds. Demonstrates convergence rather than budget exhaustion.

2. **Sobol ST bar chart with CI** — Top 20 parameters ranked by ST, with bootstrap confidence intervals. Justifies the top-N cutoff.

3. **Cumulative variance plot** — Cumulative sum of ST for all 68 parameters. Shows the "elbow" at rank 20.

4. **Pareto front scatter** — 2D plot (dropout_error vs. gpa_error) with knee-point highlighted. Shows the trade-off surface.

5. **Seed stability boxplot** — Boxplot of dropout_rate and GPA across 10 validation seeds. Demonstrates inter-seed robustness.

6. **Cohen's d effect sizes** — Effect size between SynthEd outputs and OULAD reference statistics for each validation metric.

7. **Replicated calibration comparison** — Overlay Pareto fronts from seed=42 and seed=2024. Agreement at the *output* level (dropout, GPA) confirms search reproducibility; cross-seed *parameter* divergence is informational only and reflects the structural non-identifiability discussed in §7.3.

## 7. Limitations & Identifiability

### 7.1 Scope of the credibility claim in v1.7.0

The calibration pipeline described in §2-§5 demonstrates that SynthEd can match the **marginal** OULAD targets `dropout_rate` and `gpa_mean` to within the simulator's Monte Carlo noise floor across multiple seeds. This is necessary but not sufficient evidence of *deep* distributional fidelity. v1.7.0 therefore positions the calibration as a **method release** — the pipeline is reproducible and auditable — rather than as evidence that the calibrated parameter values are themselves estimates of underlying constants.

Future versions will incrementally tighten the validation: multi-objective calibration to reduce the parameter null space, holdout-presentation generalization tests, predictive-utility (TSTR) experiments, and mechanism-ablation studies.

### 7.2 Monte Carlo noise floor of the simulator

Cross-seed validation at n=1,000 students with 10 seeds (§4) yields the following empirical standard deviations on the calibrated profile:

- **Dropout rate**: σ ≈ 0.015–0.020 (1.5–2.0 percentage points)
- **GPA mean (4-point scale)**: σ ≈ 0.003–0.005

Any objective difference smaller than ~1 pp dropout (≈0.5 σ) or ~0.005 GPA is **below the noise floor** of the simulator at the validation sample size. NSGA-II cannot distinguish solutions whose objective values fall inside this band, and reported fit improvements within this band should not be interpreted as meaningful.

### 7.3 Parameter identifiability

The calibration optimizes 20 free parameters (Sobol-screened from 68 — see §2 *Parameter: `sobol_top_n = 20`*) against 2 scalar objectives. The local Jacobian of the forward map (parameters → objectives) has rank at most 2 (assuming the two objectives, `dropout_error` and `gpa_error`, are locally linearly independent — if they happen to be locally collinear along the optimum manifold, the effective rank could fall to 1 and the null space could grow to 19-D), so there are **at least 18 effectively unconstrained directions** in parameter space at any solution: many distinct parameter vectors produce statistically indistinguishable outputs on (dropout, GPA). Cross-seed comparison of knee-point parameter vectors at distance metric `compare_knee_points` consistently shows differences on the order of 0.3–0.4 (normalized RMS) even when both seeds achieve sub-percentage-point agreement on the calibration targets — observed empirically in the v1.7.0 outputs `calibration_output/nsga2_default_seed42.json` and `nsga2_default_seed2024.json`, reproducible by running `compare_knee_points` from `synthed/analysis/pareto_utils.py` on those files.

This is the expected statistical signature of a **non-identifiable model under marginal-only calibration** (cf. Brun et al. 2001; Gutenkunst et al. 2007 on "sloppy models"). It is not a defect of the optimizer; it is a structural property of fitting a high-dimensional simulator to a low-dimensional target. The `compare_knee_points < 0.1` threshold previously used in `run_calibration.py` is **informational only** as of v1.7.0, not a release gate, because the threshold itself is not derived from a Fisher Information analysis of the simulator.

### 7.4 Practical implications for users of v1.7.0

- **Output level (synthetic cohorts)**: safe to use. Whichever knee-point parameter vector is shipped, dropout and GPA distributions match the OULAD reference within the noise floor in §7.2.
- **Parameter level (calibrated constants)**: the values reported in `calibration_output/nsga2_default_seed*.json` are **one valid solution among many**. The non-grading parameters (e.g. `_DECISION_RISK_MULTIPLIER`, `_MISSED_STREAK_PENALTY`, `_TINTO_DECAY_BASE`) should not be interpreted, plotted, or compared as physical constants until the multi-objective calibration described in §7.5 is in place. Of the four force-included grading parameters, only the two grading-formula parameters (`grade_floor`, `pass_threshold`) converge tightly across seeds (normalized cross-seed difference < 0.05) and are safe to interpret in v1.7.0; the GPA-weight parameters show partial convergence — `_EXAM_GPA_WEIGHT` (normalized difference ~0.13) is moderate, and `_ASSIGN_GPA_WEIGHT` (normalized difference ~0.42) is in the same poorly-identified regime as the unconstrained non-grading parameters and should be interpreted with caution.

### 7.5 Planned identifiability improvements

The next major calibration release will introduce three structural fixes addressing the limitations described in §7.3:

1. **Promote `pass_rate` and `distinction_rate` to NSGA-II objectives** — these metrics are already computed in `user_attrs` at no additional simulation cost. The two candidates address different mechanisms: `pass_rate` is partly exit-driven (overlapping with `dropout_rate`) while `distinction_rate` is purely grading-driven (independent of the dropout mechanism). The naive identifiability gain ("≥18 → ≥16 unconstrained directions") is an upper bound; the true gain depends on the empirical orthogonality of the four-objective set, which will be quantified in the Phase 2 work via the empirical objective correlation matrix on the existing Sobol sample and a collinearity-index analysis (Brun et al. 2001) on the objective Jacobian before the new objectives are committed.
2. **Add `withdrawal_week_distribution` KS-test as a fourth objective** — replaces a marginal scalar constraint with a distributional one, tightening identifiability.
3. **Run NSGA-II across 5 seeds** (not 2) and report parameters as **posterior bands** (median + 5–95 percentile per parameter) rather than point estimates.

These changes are expected to reduce cross-seed knee-point distance below 0.20 on the revised metric, with the new threshold derived from a Fisher Information / noise-floor analysis.

## 8. References

- Archer, G.E.B., Saltelli, A., & Sobol, I.M. (1997). Sensitivity measures, ANOVA-like techniques and the use of bootstrap. *JSCS*, 58(2), 99-120.
- Brun, R., Reichert, P., & Künsch, H.R. (2001). Practical identifiability analysis of large environmental simulation models. *Water Resources Research*, 37(4), 1015-1030.
- Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley.
- Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. *IEEE TEC*, 6(2), 182-197.
- Deb, K. & Jain, H. (2014). An evolutionary many-objective optimization algorithm using reference-point-based nondominated sorting approach. *IEEE TEC*, 18(4), 577-601.
- Gutenkunst, R.N., Waterfall, J.J., Casey, F.P., Brown, K.S., Myers, C.R., & Sethna, J.P. (2007). Universally sloppy parameter sensitivities in systems biology models. *PLoS Computational Biology*, 3(10), e189.
- Howe, W.G. (1969). Two-sided tolerance limits for normal populations. *JASA*, 64(326), 610-620.
- Iooss, B. & Lemaître, P. (2015). A review on global sensitivity analysis methods. In G. Dellino & C. Meloni (Eds.), *Uncertainty Management in Simulation-Optimization of Complex Systems: Algorithms and Applications* (pp. 101-122). Springer. https://doi.org/10.1007/978-1-4899-7547-8_5
- Ishibuchi, H., Imada, R., Setoguchi, Y., & Nojima, Y. (2017). How to specify a reference point in hypervolume calculation. *GECCO 2017*.
- Jin, Y. & Branke, J. (2005). Evolutionary optimization in uncertain environments: A survey. *IEEE TEC*, 9(3), 303-317.
- Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). Open university learning analytics dataset. *Scientific Data*, 4, 170171.
- Law, A.M. (2015). *Simulation Modeling and Analysis* (5th ed.). McGraw-Hill Education.
- Ligmann-Zielinska, A. et al. (2020). One size does not fit all: A roadmap of purpose-driven mixed-method pathways for sensitivity analysis of agent-based models. *JASSS*, 23(1), 6.
- Saltelli, A. (2002). Making best use of model evaluations to compute sensitivity indices. *Computer Physics Communications*, 145(2), 280-297. https://doi.org/10.1016/S0010-4655(02)00280-1
- Saltelli, A. et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley.
- Saltelli, A. et al. (2010). Variance based sensitivity analysis of model output. *CPC*, 181(2), 259-270.
- Ten Broeke, G., Van Voorn, G., & Ligtenberg, A. (2016). Which sensitivity analysis method should I use for my agent-based model? *JASSS*, 19(1), 5.
