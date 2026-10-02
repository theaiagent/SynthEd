# Dropout targeting and multi-semester interpretation

## What the calibration estimates

`target_dropout_range` describes cumulative dropout at the end of the configured
run. The mapper estimates a `dropout_base_rate` from simulator measurements for
that horizon. It does not estimate a real institution's dropout risk.

The default data contain 15 base-rate measurements per horizon, covering 1–4
semesters of 14 weeks. Each point averages 500 students across seeds 42–46.
Base rates 0.01, 0.025, 0.05 and 0.075 extend the previous grid into the valid
lower region of `PersonaConfig`. The 0.01 limit comes from that model's input
domain. Seed and grid selections are experimental choices, not theoretical
coefficients. The individual risk floor remains 0.02, so lowering the base rate
does not make every target attainable.

Interpolation connects adjacent **base-rate** measurements. Monte Carlo noise
can produce reversals or flat segments. When several segments match the target,
the report exposes the candidate base rates and `mapping_status=multiple_matches`;
the lowest candidate is chosen deterministically. For a flat segment, its reported
endpoints represent an interval of matching parameters. Outside the measured mean range,
the nearest observed mean is used with `clamped=true`. No horizon borrows another
horizon's curve. Custom configurations and population sizes other than the measured
N=500 are flagged as transfer estimates with low coverage confidence.

The retained `confidence` field is a compatibility label for mapping coverage.
It is not a confidence interval or a probability of target attainment. Consult
actual results, seed variation, and `target_achieved`.

## Reproducible measurements

Run from an editable repository installation:

```bash
python scripts/measure_dropout_horizons.py --output output/dropout-horizons.json
```

The committed [raw measurements](measurements/dropout-horizons.json) contain all
75 runs, semester risk-set sizes, dropout counts, validation summaries, dependency
versions, resolved default settings and generating-source hashes. The Git revision
identifies the base checkout; the hashes identify the Python files used while the
fixes were uncommitted. Each four-semester run supplies its earlier prefixes;
regression tests compare those prefixes with standalone shorter runs.

Validation is run on each completed four-semester cohort, using complete observed
histories and the explicit 56-week horizon. Histories are not padded after dropout
or passed back into theory state. Measurements fail on execution errors rather
than inserting missing or fabricated observations.

### Targeting on independent seeds

The [holdout results](measurements/dropout-targeting-holdout.json) use seeds 47–51,
N=500, default settings, and target `(0.30, 0.45)`. The artifact records the curve
file's SHA-256 checksum, configuration, dependencies and generating-source hashes.
Reproduce with:

```bash
python scripts/measure_dropout_horizons.py --target-range 0.30 0.45 --seeds 47 48 49 50 51 --curve-evidence docs/measurements/dropout-horizons.json --output output/dropout-targeting-holdout.json
```

Validation remains enabled; only exports are suppressed.

| Semesters | Estimated base rate | Mean dropout | Seed SD (percentage points) | Observed seed range |
|-----------|---------------------|--------------|----------------------------|---------------------|
| 1 | 0.403750 | 36.24% | 2.97 | 32.2–39.2% |
| 2 | 0.072037 | 37.20% | 3.43 | 32.0–41.6% |
| 4 | 0.010794 | 38.72% | 2.62 | 36.4–42.8% |

All 15 runs met the requested range. This checks one target and default
configuration, not arbitrary horizons, populations or targets. Students interact,
so seed-level variability is reported instead of treating all student outcomes as
independent Bernoulli observations. Re-measure after model or RNG changes.

## Why cumulative dropout grows

For semester `t`, conditional dropout is the number leaving during that semester
divided by the number who entered it. Cumulative dropout counts all departures
against the original cohort. With permanent dropout, cumulative dropout cannot
decrease. Conditional rates need not decline.

At default base rate 0.46, seeds 42–46 give:

| Semester | Mean cumulative dropout | Cumulative seed SD (percentage points) | Conditional dropout, pooled risk sets |
|----------|-------------------------|---------------------------------------|--------------------------------------|
| 1 | 39.60% | 2.03 | 39.60% |
| 2 | 73.48% | 1.86 | 56.09% |
| 3 | 89.76% | 2.22 | 61.39% |
| 4 | 96.04% | 1.98 | 61.33% |

These high default rates remain a modeling limitation, not an externally validated
retention curve. The changes repair known implementation problems: UUID-dependent
peer sampling, overwritten break engagement recovery, and lost raw mastery
accumulators. They do not impose a decreasing hazard or retune theory coefficients
to obtain an attractive curve. Real institutional cohort data and a justified
calibration objective are needed before making such claims.

## What an A/B validation grade means

The grade is an unweighted summary of the fraction of executed validation checks
passing. Conditional checks change its denominator. It is not external validation
of a multi-year dropout trajectory.

With targeting enabled, the dropout reference is the user's requested range;
passing that check demonstrates target compliance. Other checks retain fixed
heuristics: for example, `baulke_phase_distribution` requires terminal-phase
prevalence at most 50%, and early attrition expects at least 30% of departures in
the first half of the run. Such checks may disagree with a high cumulative target.
Read individual results and their assumptions; a lower letter grade across
horizons does not by itself demonstrate lower empirical validity.
