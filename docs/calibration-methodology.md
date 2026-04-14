# SynthEd Calibration Methodology

> Academic reference document for the NSGA-II calibration pipeline.
> Prepared for symposium presentation (April 2026).

## 1. Overview

SynthEd calibrates 70 engine constants against the Open University Learning Analytics Dataset (OULAD; Kuzilek et al., 2017) using a three-stage pipeline:

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

**Reference:** Saltelli, A. (2002). "Making best use of model evaluations to compute sensitivity indices." *Computer Methods in Applied Mechanics and Engineering*, 280, 3161-3190.

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

**Justification:**
- With 68 parameters, the Pareto principle typically applies: 20-30% of parameters explain 80%+ of output variance
- ST already includes all interaction effects — a parameter with ST = 0.005 contributes at most 0.5% of variance through any combination of interactions
- The `config.*` (PersonaConfig) and `inst.*` (InstitutionalConfig) parameters are excluded from optimization (fixed per profile), effectively reducing the candidate pool to ~55 parameters

**Validation criterion:** The cumulative ST of the top 20 parameters must explain ≥ 90% of total variance. If < 70%, increase to 25-30 and raise n_trials proportionally.

**Reference:** Saltelli, A. et al. (2010). "Variance based sensitivity analysis of model output." *Computer Physics Communications*, 181(2), 259-270.

## 3. Why NSGA-II Multi-Objective Optimization?

### Purpose

Find engine constant values that simultaneously minimize:
1. **Dropout error:** |achieved_dropout - target_dropout|
2. **GPA error:** |achieved_gpa - target_gpa|

subject to constraints:
- engagement ≥ 0.1 (hard floor)
- dropout_rate ∈ [0.35, 0.60] (feasibility range)

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
           = (1.96 + 0.842)² × 0.42 × 0.58 / δ²
           = 7.849 × 0.2436 / δ²
```

| Effect size (δ) | Required N | Interpretation |
|-----------------|------------|----------------|
| 3 pp (0.03) | 2,124 | Fine-grained calibration |
| 5 pp (0.05) | 765 | Moderate calibration |
| 7 pp (0.07) | 390 | Coarse calibration |
| 10 pp (0.10) | 191 | Rough calibration |

**Standard error at selected N values:**

| N | SE | 95% CI half-width | MDE (power=0.80) |
|---|----|--------------------|-------------------|
| 100 | 4.94% | ±9.68% | 13.8 pp |
| 200 | 3.49% | ±6.84% | 9.8 pp |
| 300 | 2.85% | ±5.59% | 8.0 pp |
| **500** | **2.21%** | **±4.33%** | **6.2 pp** |
| 750 | 1.80% | ±3.53% | 5.0 pp |
| 1000 | 1.56% | ±3.06% | 4.4 pp |

**Decision rationale:** N=500 (SE=2.21%) is the pragmatic optimum. It provides:
- MDE of 6.2 pp — sufficient for NSGA-II to distinguish meaningfully different parameter sets
- Signal-to-Noise Ratio (SNR) ≈ 2.3 for 5pp differences — workable with evolutionary selection pressure over 310 generations
- Acceptable computational cost per evaluation (~0.9 seconds)

Going to N=750 (SE=1.80%) would improve discriminability but increase total compute by 50% with diminishing returns for the optimizer.

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
- σ_noise = Standard Error (SE) of a single simulation's dropout_rate = 0.0221 (at N=500, p=0.42)
- σ_signal = standard deviation of the true objective function (dropout_error) across solutions that the optimizer must discriminate between

The value of σ_signal depends on the optimization phase:

| Phase | σ_signal | NAF | Interpretation |
|-------|----------|-----|----------------|
| Global exploration (early generations) | 0.052 | 1.18 | Solutions span the full feasible range [0.35, 0.60]; large fitness differences are easy to detect |
| Mid-convergence | 0.03 | 1.54 | Population clusters near the optimum; moderate differences remain |
| Near-optimum refinement (late generations) | 0.02 | 2.22 | Competing solutions differ by only 2-3 percentage points; noise dominates |

**Global σ_signal derivation:** In the feasible region, dropout_error = |achieved - 0.42| ranges from 0 to 0.18. Under uniform coverage: σ = 0.18/√12 ≈ 0.052.

**Budget computation using the conservative mid-convergence estimate (σ_signal = 0.03):**

```
NAF = 1 + 0.0221² / 0.03² = 1 + 0.000489 / 0.0009 = 1.54

Minimum evaluations = pop_size × 10D × NAF
                    = 200 × 200 × 1.54
                    = 61,600
```

**Our choice of 62,000** matches this conservative estimate (61,600 rounded up). This ensures adequate budget not only for global exploration but also for the mid-convergence phase where population refinement occurs.

Additionally, the **re-evaluation step** provides a second layer of noise mitigation: after NSGA-II completes, every Pareto front solution is re-evaluated at N=2,000 (SE=1.10%), eliminating noise-induced errors in knee-point selection. This two-phase strategy is well-established in noisy optimization (Jin & Branke, 2005): use a principled evaluation budget for search, then re-evaluate the final solution set with higher fidelity.

At pop_size=200, 62,000 evaluations yield 310 generations — comfortably within the Deb (2002) recommended range of 10D-20D generations (200-400).

**Convergence verification:** Hypervolume Indicator (HV) tracking per generation. Convergence is declared when HV improvement < 0.1% over 20 consecutive generations. If convergence is reached before generation 310, the remaining generations serve as confirmation of stability.

**References:**
- Branke, J. (2001). "Evolutionary optimization in uncertain environments — a survey." *CEC 2001*.
- Ishibuchi, H., Imada, R., Setoguchi, Y., & Nojima, Y. (2017). "How to specify a reference point in hypervolume calculation." *GECCO 2017*.

### Strengthening: Re-evaluation and Replication

**Re-evaluation (N=2,000):** After NSGA-II completes, each Pareto front solution is re-evaluated with N=2,000 students. This reduces the SE of each solution's objectives from 2.21% (N=500) to 1.10% (N=2,000), ensuring the knee-point selection is not distorted by calibration-phase noise.

**Replicated calibration:** The full NSGA-II is run with two different optimizer seeds (42 and 2024). If both runs converge to similar knee-point parameter vectors (Euclidean distance < 0.1 in normalized space), the calibration is robust. If they diverge, the landscape has multiple optima and the Pareto front is underexplored.

## 4. Cross-Seed Validation

### Purpose

Verify that the calibrated parameters produce stable outputs across different random seeds — i.e., the results are driven by the calibrated parameters, not by stochastic artifacts.

### Parameter: `Validation N = 1,000`

```
SE = √(0.42 × 0.58 / 1000) = 1.56%
95% CI = ±1.96 × 0.0156 = ±3.06 pp
```

At N=1,000, a measured dropout of 42% has 95% CI [38.9%, 45.1%] — comfortably within the target range [35%, 60%].

For SE < 2%: N ≥ p(1-p) / 0.02² = 0.2436 / 0.0004 = 609. Our N=1,000 exceeds this with margin.

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

At k=10, we can claim (95% confidence) that 95% of seeds produce dropout rates within a ~9 pp band around the mean. This is defensible for a symposium.

**Decision rationale:** k=10 is the standard minimum for simulation output analysis (Law, 2015). It provides df=9 for the t-distribution (mild penalty vs. normal), a sub-1pp CI half-width on the mean, and a ~9pp tolerance interval.

**References:**
- Law, A.M. (2015). *Simulation Modeling and Analysis* (5th ed.). McGraw-Hill Education.
- Howe, W.G. (1969). "Two-sided tolerance limits for normal populations." *JASA*, 64(326), 610-620.

## 5. Complete Parameter Configuration

### Calibration Parameters

```python
# Sobol global sensitivity analysis
sobol_n_samples = 512          # Saltelli base count; total sims = 512 × 70 = 35,840
sobol_n_students = 500         # Students per Sobol simulation
sobol_top_n = 20               # Top parameters selected for NSGA-II

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
workers = 8                    # Parallel processes (50% of 16 cores)
```

### Computational Budget

| Stage | Simulations | N per sim | Est. time (8 workers) |
|-------|-------------|-----------|----------------------|
| Sobol | 35,840 | 500 | ~65 min |
| NSGA-II (seed 42) | 62,000 | 500 | ~115 min |
| NSGA-II (seed 2024) | 62,000 | 500 | ~115 min |
| Re-evaluation | ~60 | 2,000 | ~1 min |
| Validation | 10 | 1,000 | <1 min |
| **Total** | **~160,000** | | **~5 hours** |

### Statistical Summary

| Metric | Value | Source |
|--------|-------|--------|
| Sobol Confidence Interval (CI) half-width on ST | ≤ 0.065 | n_samples=512, c=0.75 |
| NSGA-II fitness Standard Error (SE) on dropout | 2.21% | N=500, p=0.42 |
| NSGA-II Minimum Detectable Effect (MDE) | 6.2 pp | power=0.80, α=0.05 |
| NSGA-II generations | 310 | 62,000/200 |
| Validation CI half-width (mean) | 0.95 percentage points (pp) | k=10, s=0.0133, t=2.262 |
| Validation tolerance width (95/95) | 8.99 pp | k=10, k_tol=3.379 |
| SE < 2% threshold | N ≥ 609 | p(1-p)/0.02² |

## 6. Diagnostics for Symposium

The following diagnostic visualizations should accompany calibration results:

1. **Hypervolume Indicator (HV) convergence curve** — HV vs. generation number for both NSGA-II seeds. Demonstrates convergence rather than budget exhaustion.

2. **Sobol ST bar chart with CI** — Top 20 parameters ranked by ST, with bootstrap confidence intervals. Justifies the top-N cutoff.

3. **Cumulative variance plot** — Cumulative sum of ST for all 68 parameters. Shows the "elbow" at rank 20.

4. **Pareto front scatter** — 2D plot (dropout_error vs. gpa_error) with knee-point highlighted. Shows the trade-off surface.

5. **Seed stability boxplot** — Boxplot of dropout_rate and GPA across 10 validation seeds. Demonstrates inter-seed robustness.

6. **Cohen's d effect sizes** — Effect size between SynthEd outputs and OULAD reference statistics for each validation metric.

7. **Replicated calibration comparison** — Overlay Pareto fronts from seed=42 and seed=2024. Agreement = robust calibration.

## 7. References

- Archer, G.E.B., Saltelli, A., & Sobol, I.M. (1997). Sensitivity measures, ANOVA-like techniques and the use of bootstrap. *JSCS*, 58(2), 99-120.
- Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley.
- Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. *IEEE TEC*, 6(2), 182-197.
- Deb, K. & Jain, H. (2014). An evolutionary many-objective optimization algorithm using reference-point-based nondominated sorting approach. *IEEE TEC*, 18(4), 577-601.
- Howe, W.G. (1969). Two-sided tolerance limits for normal populations. *JASA*, 64(326), 610-620.
- Iooss, B. & Lemaître, P. (2015). A review on global sensitivity analysis methods. In G. Dellino & C. Meloni (Eds.), *Uncertainty Management in Simulation-Optimization of Complex Systems: Algorithms and Applications* (pp. 101-122). Springer. https://doi.org/10.1007/978-1-4899-7547-8_5
- Ishibuchi, H., Imada, R., Setoguchi, Y., & Nojima, Y. (2017). How to specify a reference point in hypervolume calculation. *GECCO 2017*.
- Jin, Y. & Branke, J. (2005). Evolutionary optimization in uncertain environments: A survey. *IEEE TEC*, 9(3), 303-317.
- Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). Open university learning analytics dataset. *Scientific Data*, 4, 170171.
- Law, A.M. (2015). *Simulation Modeling and Analysis* (5th ed.). McGraw-Hill Education.
- Ligmann-Zielinska, A. et al. (2020). One size does not fit all: A roadmap of purpose-driven mixed-method pathways for sensitivity analysis of agent-based models. *JASSS*, 23(1), 6.
- Saltelli, A. (2002). Making best use of model evaluations to compute sensitivity indices. *CMAME*, 280, 3161-3190.
- Saltelli, A. et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley.
- Saltelli, A. et al. (2010). Variance based sensitivity analysis of model output. *CPC*, 181(2), 259-270.
- Ten Broeke, G., Van Voorn, G., & Ligtenberg, A. (2016). Which sensitivity analysis method should I use for my agent-based model? *JASSS*, 19(1), 5.
