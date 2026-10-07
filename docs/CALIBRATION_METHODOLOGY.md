# SynthEd Calibration Methodology

> Reference document for the NSGA-II calibration pipeline.

## 1. Overview

SynthEd screens 68 tunable simulation parameters spanning 13 prefixes (engine, theory anchors, grading, institutional, persona), then optimizes 20 against the scalar OULAD reference targets stored in `synthed/benchmarks/profiles.py`. Persona/institutional float fields are fixed to profile values; non-selected engine/theory/grading fields retain implementation defaults. (Note: the dashboard's "Engine Constants" panel exposes all 70 fields of the `EngineConfig` dataclass; only 15 of those are in the Sobol candidate set.)

```
Sobol Global Sensitivity Analysis → NSGA-II Multi-Objective Optimization → Cross-Seed Validation
```

This document records the method choices, current source behavior, and limits of the versioned evidence. The NSGA-II CLI does not read OULAD CSVs, select a held-out institutional cohort, install its saved candidates into production defaults, or regenerate the dropout lookup table. Production targeting is a separate operation; see [Dropout Targeting](DROPOUT_TARGETING.md). Historical calibration summaries predate the later workload and Kember corrections. No new measurement is implied by this documentation correction.

## 2. Why Sobol Global Sensitivity Analysis?

### Purpose

Before optimization, we must identify which of the 68 tunable parameters meaningfully affect simulation outputs. Screening limits the dimension of the subsequent search under the configured budget. Sobol analysis decomposes the total output variance into contributions from individual parameters and their interactions.

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

where D = 68 parameters. Two base matrices and D hybrid matrices provide the N × (D + 2) rows for S1 (first-order) and ST (total-order) estimation.

**Reference:** Saltelli, A. (2002). "Making best use of model evaluations to compute sensitivity indices." *Computer Physics Communications*, 145(2), 280-297.

### Parameter: `n_samples = 512`

The full CLI uses 512 base samples (35,840 simulation rows, N=500 per row).
Quick mode uses 128 (8,960 rows, N=100); direct `SobolAnalyzer.run()` defaults
are 128 base samples with the constructor's N=200. These are configured budgets,
not verified detection or confidence guarantees.

`SobolAnalyzer.run()` returns S1, ST and bootstrap confidence half-widths for
dropout, mean engagement and mean GPA. A fixed sample count does not establish
a half-width of 0.065 or reliable detection at ST=0.05. The previous table used
an assumed c=0.75, not measured intervals. Inspect actual intervals and ranking
stability for a new study; the CLI currently does not persist those results.

### Parameter: `sobol_top_n = 20`

The CLI uses the dropout ST ranking. It excludes 8 `config.*` and 5 `inst.*` candidates, leaving exactly 55 eligible parameters, and selects 20 in full mode or 10 in quick mode. The Sobol screen itself uses `PersonaConfig()` and runner defaults, not the named benchmark profile.

**Force-included parameters:** Because Sobol ranks parameters by dropout_rate sensitivity, GPA-affecting parameters may rank low despite being critical for the GPA objective. Four grading parameters are force-included regardless of Sobol rank:

- `grading.grade_floor` — most direct GPA lever: `floor + (1-floor) * quality`
- `grading.pass_threshold` — affects Pass/Fail/Distinction classification
- `engine._ASSIGN_GPA_WEIGHT` — prior GPA influence on assignment quality
- `engine._EXAM_GPA_WEIGHT` — prior GPA influence on exam quality

These 4 force-included parameters count toward the top-20 budget (4 forced + 16 from Sobol ranking = 20 total), keeping search dimensionality constant.

> **Note:** This force-include set is specific to the current SynthEd grading formula and OULAD calibration target. The authoritative list is maintained in `run_calibration.py::GPA_FORCE_INCLUDE`. If the engine's grading model is refactored or alternative institutional profiles with different GPA calculation strategies are introduced, this list should be reviewed for applicability.

Quick mode uses four forced entries plus six ranked entries. `pass_threshold`
affects outcome classification but does not
make pass/distinction rates objectives. Parameter count is an operational choice.

ST includes interactions involving a parameter. Summing ST values can count the
same interaction more than once; it is not cumulative explained variance. The
CLI implements neither the previously described 90% cumulative-ST gate nor an
automatic dimension increase. The literature references in §8 provide background,
not evidence that this selection captures a specified share of simulator variance.

## 3. Why NSGA-II Multi-Objective Optimization?

### Purpose

Find engine constant values that simultaneously minimize:
1. **Dropout error:** |achieved_dropout - target_dropout| where target_dropout = 0.312 (stored profile reference)
2. **GPA error:** |achieved_gpa - target_gpa| where target_gpa = 3.03 (stored profile reference)

subject to constraints:
- engagement ≥ 0.1 (hard floor)
- dropout_rate ∈ [0.20, 0.45] (feasibility range)

### Why NSGA-II over alternatives?

| Method | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Grid search** | Exhaustive | Curse of dimensionality: 10^20 grid points for 20D | Infeasible |
| **Bayesian (TPE/GP)** | Surrogate-based search | Requires a different search design | Not evaluated here |
| **NSGA-II** | Native multi-objective; constraint handling; well-studied convergence | Requires population-level evaluation budget | **Selected** |
| **NSGA-III** | Better for 3+ objectives | Overkill for 2 objectives; similar cost | Unnecessary |
| **MOEA/D** | Good decomposition | Less intuitive knee-point selection | No advantage |

NSGA-II was selected because:
1. **Native bi-objective optimization** — produces a Pareto front of non-dominated solutions
2. **Constraint handling** via feasibility-first tournament selection
3. **Knee-point selection** — the geometric knee provides the implemented compromise rule, not a statistical optimality guarantee
4. **Well-established** in simulation calibration (Deb et al., 2002; Deb & Jain, 2014)

### Implementation

We use Optuna's `NSGAIISampler` with ask/tell API for batch parallelism:

```python
sampler = NSGAIISampler(seed=seed, population_size=pop_size,
                       constraints_func=constraints_func)
study = optuna.create_study(
    directions=["minimize", "minimize"],  # dropout_error, gpa_error
    sampler=sampler,
)
```

**Reference:** Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). "A fast and elitist multiobjective genetic algorithm: NSGA-II." *IEEE Transactions on Evolutionary Computation*, 6(2), 182-197.

### Measured quantities and effective overrides

The shared runner obtains these values from `simulation_summary`:

- Dropout is all departures divided by the original cohort, including unavoidable
  withdrawals.
- Mean GPA is mean `cumulative_gpa` among students with at least one graded item,
  including students who later withdrew. Transcript GPA applies
  `grade_floor + (1 - grade_floor) × raw_quality`, then the GPA scale. It differs
  from raw `perceived_mastery`, which theory modules use, and from raw
  `semester_grade`. Default grade floor is **0.45**; absolute classification
  applies the floor to semester grade separately.
- Mean final engagement is computed over **retained students** using their last
  observed engagement. Despite a contrary inline constraint comment, this
  aggregate excludes dropouts. If no GPA or engagement aggregate is available,
  `_extract_metrics()` logs a warning and substitutes **0.0**; inspect such runs.

`pass_rate` and `distinction_rate` are recorded as Optuna trial attributes, but
are not objectives or constraints. Correlation-check results and the overall
validation grade are also not optimization objectives or feasibility gates.

Every trial runs a fresh one-semester, default 14-week pipeline with the same
simulation seed as that optimizer run. This reduces one source of variation
between candidates but does not hold later random draws or peer interactions
fixed when model behavior changes.

`_build_fixed_overrides()` copies float fields from the profile's persona and
institutional configurations. `_sim_runner.py` does not forward the profile's
`environment`, `grading_config`, or `reference_stats` wholesale: it starts with
runner defaults and applies the sampled/fixed overrides. For example, the
profile declares `pass_threshold=0.65`, whereas plain `GradingConfig()` uses
**0.64**; the sampled threshold overrides that field during CLI optimization.
The scalar objective targets still come from the profile. This is not identical
to evaluating every setting of `SynthEdPipeline.from_profile()`.

Assignment and exam quality weight groups are normalized to sum to one when an
override affects them. Submission weights are scaled down only if their sum
exceeds one. Consequently, saved sampled weight values are **inputs to the
normalization**, not necessarily the final effective engine weights. Replay them
through the same override logic. When both classification thresholds are sampled,
the runner sorts them before constructing `GradingConfig`.

### Parameter: `n_students = 500`

Each NSGA-II evaluation simulates N students for 14 weeks. The historical budget
rationale used the independent-Bernoulli approximation:

```
SE(p) = √(p(1-p)/N)
```

The following arithmetic assumes independent observations and normal
approximations, p=0.312, α=0.05 and power=0.80. Students in SynthEd interact, so
these figures are **illustrative planning values**, not verified simulator SEs,
confidence intervals or minimum detectable effects. A simulation power study or
independent cohort/seed design is required to substantiate such claims.

**Standard error at selected N values:**

| N | SE | 95% CI half-width | MDE (power=0.80) |
|---|----|--------------------|-------------------|
| 100 | 4.63% | ±9.08% | 12.98 pp |
| 200 | 3.28% | ±6.42% | 9.18 pp |
| 300 | 2.67% | ±5.24% | 7.49 pp |
| **500** | **2.07%** | **±4.06%** | **5.80 pp** |
| 750 | 1.69% | ±3.32% | 4.74 pp |
| 1000 | 1.47% | ±2.87% | 4.10 pp |

**Trade-off:** N=500 limits per-evaluation cost. Larger cohorts and more independent
seeds can improve uncertainty assessment but cost more; these tables do not
establish an optimal N or a runtime guarantee.

**Reference:** Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley.

### Parameter: `pop_size = 200`

The NSGA-II population size determines genetic diversity and Pareto front coverage.
The full CLI uses 200 for 20 selected parameters. This is a configured search
choice, not a proven minimum or sufficiency rule of `10 × D` for this simulator.

### Parameter: `n_trials = 62,000`

The full run budgets 62,000 attempted trials per optimizer seed, giving 310
batches at population 200. Failed trials consume this budget. Quick mode uses
500 trials and population 20 (25 batches); direct `run()` defaults are 8,000
and 80, with no forced parameters unless supplied by the caller.

Hypervolume is recorded after batches with a nonempty best front, using reference
point (0.25, 2.0). There is no implemented 0.1% improvement gate, 20-generation
stability test or early stopping. Budget completion does not establish convergence.
The previous noise-amplification calculation assumed unmeasured signal variances;
it cannot establish 59,200 as a required budget or 62,000 as sufficient.

### Strengthening: Re-evaluation and Replication

**Re-evaluation (N=2,000):** Full mode evaluates each in-memory Pareto candidate at
seeds (42, 123, 456), averages outputs and reselects a knee. Quick mode skips it.
This can reduce sampling variation but cannot eliminate it. The method does not
re-filter feasibility or recompute nondominance after averaging.

`find_knee_point()` normalizes both axes and selects the point farthest from the
line between endpoints. With one or two points it returns the first; degenerate
endpoints also have a fallback. The selected point is not a statistical optimum
certificate.

**Replicated calibration:** The full NSGA-II uses seeds 42 and 2024. The
`compare_knee_points < 0.1` rule is informational, not a release gate or a
Fisher Information-derived threshold. See §7.3 for the measured distance and
limits of the local identifiability argument.

## 4. Cross-Seed Validation

### Purpose

Describe how the selected candidate's outputs vary across simulation seeds. This provides a stability diagnostic; the seed design below determines its inferential limits.

### Parameter: `Validation N = 1,000`

Both CLI modes evaluate the selected knee at N=1,000. The binomial SE approximation
is 1.47 percentage points at p=0.312, with a normal half-width of 2.87 points;
these are not verified uncertainty estimates for the interacting agent model.
Direct `validate_solution()` defaults to N=500 and seeds (42, 123, 456).

### Parameter: `Validation seeds = 10`

The CLI uses (42, 123, 456, 789, 2024, 1337, 7777, 9999, 31415, 27182).
These are not fully held-out: 42/2024 overlap search and 42/123/456 overlap
Pareto re-evaluation. It reports means and population SDs (`numpy.std`, ddof=0),
not individual observations, confidence intervals or tolerance intervals.
`validation.in_range` checks only mean dropout against 20–45%; it does not
certify every seed's range, GPA fit or success of all normal validation checks.

For a separate inferential design with independent, approximately normal seed
estimates, a mean interval would use the **sample** SD s (ddof=1):

```
CI = x̄ ± t_{α/2, k-1} × s / √k
```

The following t factors illustrate the dependence on seed count; they are not
intervals computed by the CLI.

**t-critical values and CI properties:**

| k (seeds) | df | t_{0.025, df} | CI factor (t/√k) | Relative width |
|-----------|-----|---------------|-------------------|----------------|
| 3 | 2 | 4.303 | 2.484 | 3.47× |
| 5 | 4 | 2.776 | 1.242 | 1.74× |
| **10** | **9** | **2.262** | **0.715** | **1.00×** |
| 15 | 14 | 2.145 | 0.554 | 0.77× |
| 20 | 19 | 2.093 | 0.468 | 0.65× |
| 30 | 29 | 2.045 | 0.373 | 0.52× |

The former example s=0.0133 and 95/95 tolerance-width table are not supported by
the saved calibration summaries. Ten seeds alone do not justify a sub-1-point
mean interval or a 9-point band containing 95% of future seed outcomes.

The analysis runner suppresses exports with `_calibration_mode=True` but still
runs the normal validation suite. The wrapper returns aggregate simulation
metrics; the CLI does not persist the full validation reports.

Validation reports distinguish `passed`, `failed` and `not_assessed`. Undefined
or ineligible measurements remain visible with a reason and null numeric values;
they do not count as failures. The quality pass rate is `passed / assessed_tests`,
where `assessed_tests = passed + failed`; no assessed checks yields 0.0 and
`N/A (Not assessed)`. Always report `total_tests`, `assessed_tests` and
`not_assessed` alongside quality. `assessment_complete` is false when any emitted
check is unassessed. A grade with partial coverage describes only the assessed
subset. Historical summary-only reports keep their original grades; their total
is treated as assessed. Compare coverage before comparing old and new grades.
This reporting change does not alter simulation parameters, optimization
objectives, correlation directions or hypothesis-test thresholds.

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
workers = 1                    # CLI default; actual utilization depends on workload and hardware
```

### CLI, seeds and failure behavior

Sequential Sobol evaluation propagates the first simulation exception. Parallel
Sobol evaluation first submits all rows to a shared pool, preserving row order in
the results. Failed or unfinished rows receive up to **two isolated retries** in
fresh one-worker pools: at most one first-pass execution plus two retries per
row. Each isolated wait has a **300-second** timeout. The initial collection
budget is `min(300 × number_of_rows, 86400)` seconds. Running workers are not
forcibly killed by `shutdown(wait=False, cancel_futures=True)`.

An unrecovered row aborts the analysis. It is not dropped or replaced with zero;
the Saltelli matrix requires every row in the original order.

The analyzer's `seed` controls the simulator seed for each Sobol row, but the
SALib sampling/bootstrap calls do not pass a seed. The CLI does not save a sample
matrix, so `--seed` alone does not reproduce the full screening/ranking process.
The API accepts `sample_matrix` for callers that retain one.

In full mode `--seed` changes the Sobol simulation seed only; optimizer/trial
seeds remain (42, 2024). In quick mode it also selects the optimizer/trial seed.
`--workers` is clamped to [1, CPU count] (fallback ceiling 8). The CLI has no
semester-count, output-directory, trial-count or saved-matrix option. Its only
built-in profile is `default`; output files in `calibration_output/` may be
replaced by a new invocation.

Parallel NSGA-II asks for the whole batch before returning results in trial
order; sequential mode asks/evaluates/tells one trial at a time. The same seed
need not produce identical searches across worker modes. Trial simulation failures
are recorded as failed trials, with no Sobol-style retry; outer failures can
abort the profile. The CLI catches profile failures and writes `error` entries
to the combined JSON. Inspect these entries because old per-seed success files
can remain after a failure.

Quick mode uses N=100, 128 Sobol base samples, ten selected parameters, population
20 and 500 trials. It skips re-evaluation but retains the ten N=1,000 final runs.

### Computational Budget

Without failures/retries, full mode schedules **159,840** Sobol/search evaluations
(35,840 + 2 × 62,000), plus three runs per original Pareto candidate across both
searches, plus **20** final evaluation runs. With the archived front sizes of
three and four, this would total **159,881** simulation calls. Quick mode schedules
**9,470** (8,960 + 500 + 10). These counts have different per-stage population
sizes; they are not runtime estimates.

The historical seed summaries record **12,749.9 s** and **11,938.4 s** for
`calibration_time_s`. That timer covers `cal.run()`, excluding the separate CLI
Sobol stage, subsequent re-evaluation and final evaluation. Hardware, worker
count and end-to-end duration are not recorded there; a current runtime promise
cannot be derived from them.

**Trade-off:** these budgets bound search work while restricting the free
parameters. Larger cohorts, more seeds and saved trial-level evidence increase
cost and storage but improve uncertainty assessment and auditability. Neither
reducing dimensions nor increasing trials guarantees validity or convergence.

## 6. Diagnostic Visualizations

The CLI writes `nsga2_<profile>_seed<seed>.json` and a combined
`nsga2_all_profiles.json`. Successful summaries contain the original Pareto size,
attempted evaluation count, search duration, selected knee, parameter names,
hypervolume history, and aggregate final evaluation statistics. The combined
file adds the optimizer seed; failed profiles instead have `seed`, `profile`
and `error`.

| Diagnostic | What the current CLI actually preserves |
|------------|----------------------------------------|
| HV trace | `hv_history`; both archived seeds contain 310 entries |
| Sobol S1/ST, confidence intervals, sample matrix | Computed in memory; not saved by the CLI |
| Full Pareto scatter / front overlay | Front exists in memory; JSON saves only its size and knee |
| Seed stability boxplot | Individual evaluation observations are not saved; only means and SDs |
| Knee parameter comparison | Can be computed from the two saved parameter dictionaries |
| Complete validation scorecard / correlations | Evaluated inside the runner, not retained in these NSGA-II summaries |

An ST ranking plot requires retained Sobol results; a cumulative sum of ST must
not be labeled explained variance. The existing summary files cannot reconstruct
full fronts, per-seed boxplots, trial failures, or effect-size uncertainty. Future
runs need explicit persistence for those diagnostics. Do not regenerate historical
evidence solely because the documentation changed.

## 7. Limitations & Identifiability

### 7.1 Historical evidence and provenance

The tracked `calibration_output/nsga2_default_seed42.json` and
`nsga2_default_seed2024.json` were last updated in commit **73ec261**. Each reports
62,000 evaluations, 20 parameters and 310 HV entries; the combined file agrees
with the individual summaries. These are historical candidate evaluations:

| Optimizer seed | Pareto size | Knee dropout / GPA | Final dropout mean / SD | Final GPA mean / SD |
|----------------|------------:|--------------------|-------------------------|---------------------|
| 42 | 3 | 0.2985 / 3.0263 | 0.2988 / 0.0196 | 3.0236 / 0.0028 |
| 2024 | 4 | 0.3292 / 3.0215 | 0.3224 / 0.0145 | 3.0204 / 0.0044 |

Against the stored reference targets, the final dropout means differ by **−1.32**
and **+1.04 percentage points**, and GPA by **−0.0064** and **−0.0096**. Passing the
20–45% mean-dropout range is a much weaker claim than matching both targets or
whole distributions.

These summaries lack generating-source hashes, dependencies, resolved configs,
per-trial results and individual final evaluation seeds/outcomes. Their values
cannot establish a current production result or verify the full historical run
design on their own. The later targeting and mechanism measurements have more
explicit manifests, but evaluate different configurations and questions.

### 7.2 Historical support-services effect report

Issue #86's 50-seed (41–90), N=200 support-services study is quoted in
`tests/test_baulke_institutional.py`: dropout at SSQ=0.5 minus SSQ=0.8 had mean
**0.0482**, SD **0.0325**, p10 **0.0140**; dropout at SSQ=0.2 minus SSQ=0.5 had mean
**0.0687**, SD **0.0308**, p10 **0.0295**. The second contrast describes the effect
of **lowering** support from 0.5 to 0.2, not increasing it from 0.2 to 0.5.

These are historical figures preserved in test documentation, without a tracked
raw measurement manifest in `docs/measurements/` or `calibration_output/`. The
integration assertions use a **0.008** margin on ten-seed means. A reported
empirical tenth percentile is not a power calculation for that test, and these
figures do not establish current effects after subsequent model changes.

### 7.3 Parameter identifiability

Twenty selected parameters are fitted to two scalar objectives. Where a smooth
local approximation is appropriate, the objective Jacobian has rank at most two
and hence at least **18 local first-order null directions**. This dimension count
does not prove a global equivalence manifold, quantify practical identifiability,
or account for nonsmooth simulation rules and active constraints.

Using the archived rounded dictionaries, `compare_knee_points()` returns
**0.378359**. It divides each difference by the larger absolute value in the pair,
then takes the RMS; it does not normalize by Sobol parameter bounds. Individual
normalized differences are **0.005967** for `grade_floor`, **0.045685** for
`pass_threshold`, **0.133947** for `_EXAM_GPA_WEIGHT`, and **0.424371** for
`_ASSIGN_GPA_WEIGHT`.

The CLI's **0.1** comparison threshold is informational. Agreement of two
optimizer runs, even for the grading fields, does not identify a physical or
institutional constant. Disagreement also does not by itself diagnose optimizer
failure. Effective normalized engine weights require the replay logic in §3.

### 7.4 Practical interpretation

Use the saved parameters as candidate simulation settings with a limited measured
scope. Marginal fit does not establish correlation fidelity, privacy, predictive
utility, institutional transportability, or multi-semester retention validity.
The production defaults are not automatically replaced by either saved knee.

The normal validator's A/B/C/D/F grade is an unweighted fraction of assessed
checks (`passed + failed`); `not_assessed` rows are excluded. Several correlation checks require only the expected sign, with p-values
reported but not used as pass gates; their reference magnitudes are not matching
tolerances. Passing them does not show that correlations are preserved across
code revisions. Read the individual checks and population/horizon definitions in
[Dropout Targeting](DROPOUT_TARGETING.md#what-an-ab-validation-grade-means).

The GPA distribution check uses two-sample KS against an equally sized normal
reference clipped to [0, 4]. For a fixed integer validator seed (default 42),
reference parameters and count, each call recreates the same reference sample.
Decisions are independent of previous calls and retain a fresh validator's first
numeric result. Reports disclose the reference form, seed and count. Common
sampling repeats the same finite-reference error; different seeds/counts can
change results. Clipping creates endpoint masses and ties, so this reproducibility
repair does not validate continuous-distribution KS p-values or calibrate the
simulation. The KS method, effective alpha and model parameters are unchanged.

### 7.5 Possible future work (not implemented)

Additional objectives could include pass rate, distinction rate and withdrawal
timing, subject to suitable empirical references. Adding two outcome rates to the
current two objectives gives four; adding a timing statistic gives **five**.
Their dependence and information content must be assessed rather than assuming
each removes one unidentified direction.

More optimizer seeds can describe search variability. Their quantiles would be
**empirical optimizer-result bands**, not Bayesian posterior intervals. A new
cross-seed distance threshold, convergence criterion, statistical-power claim or
institutional acceptance margin needs a justified design and evidence. None is
established by the current summaries.

## 8. References

The original bibliography is retained as methodological background and historical
context. It is not evidence for the removed numerical power/convergence guarantees.
Current implementation claims above are checked against `run_calibration.py`,
`synthed/analysis/{sobol_sensitivity,nsga2_calibrator,_sim_runner,pareto_utils}.py`,
`synthed/simulation/statistics.py`, and `synthed/validation/validator.py`.

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
