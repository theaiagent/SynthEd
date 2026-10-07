# Dropout targeting and multi-semester interpretation

## What the calibration estimates

`target_dropout_range` describes cumulative dropout at the end of the configured
run. The mapper estimates a `dropout_base_rate` from simulator measurements for
that horizon. It does not estimate a real institution's dropout risk.

This mapper is separate from the NSGA-II parameter search described in
[Calibration Methodology](CALIBRATION_METHODOLOGY.md). It uses the midpoint of
the requested range to estimate one base rate before generating the cohort.
It replaces the persona configuration's base rate and the validator's dropout
reference/range; it does not change theory coefficients or individual outcomes
to force the requested result. A run outside the range emits a warning and
reports `target_achieved=false`; there is no automatic retry, seed selection,
or adjustment between semesters. Interim reports are descriptive.

The default data contain 15 base-rate measurements per horizon, covering 1–4
semesters of 14 weeks. Each point averages five N=500 cohorts, seeds 42–46.
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

### Invocation and configuration boundaries

For a one-semester CLI run:

```bash
python run_pipeline.py --n 500 --seed 47 --target-dropout 0.30 0.45
```

The bounds must satisfy `0 < lower < upper < 1`. For multiple semesters, use
the configuration API; `run_pipeline.py` has no semester-count option:

```python
from synthed.pipeline import SynthEdPipeline
from synthed.pipeline_config import PipelineConfig

config = PipelineConfig(
    seed=47, n_semesters=4, target_dropout_range=(0.30, 0.45),
    output_dir="output/targeted-four-terms",
)
report = SynthEdPipeline(config=config).run(n_students=500)
```

`run_pipeline.py --config` reads its legacy `persona_config`,
`reference_statistics`, and selected `simulation` settings. It does not load
an arbitrary `PipelineConfig.to_dict()` export or forward `n_semesters` and
targeting from that JSON. Use `PipelineConfig.from_dict()` through the Python
API for the full configuration schema, with the event-week key and carry-over
normalization shown in the [JSON loading example](GUIDE.md#pipelineconfig-recommended).

An unmeasured semester count raises `ValueError`; the pipeline does not fall
back to a neighboring curve. The standalone `CalibrationMap` accepts custom
points, but the pipeline currently constructs the built-in map internally and
has no public map-injection argument. A different term length still selects
by semester count and is flagged as a configuration transfer, not a newly
measured horizon.

`SynthEdPipeline.from_profile("default")` enables targeting using that
profile's 20–45% range. `BenchmarkGenerator.generate()` (also used by
`run_pipeline.py --benchmark`) follows a different path: it checks the observed
rate against the profile range after an untargeted run. It forwards the profile's
persona, environment, reference statistics and seed, but currently does not
forward its institutional or grading configurations. Do not treat those entry
points as equivalent calibration reproductions.

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

These curves were re-measured after restricting exhaustion workload to enrolled
courses and limiting Kember's missed-assignment charge to weeks with a new miss.
The generating hash for `calibration.py` records the preceding lookup
table: this untargeted sweep does not consume it. The 60 current lookup values
are then derived from the saved counts; the holdout artifact fingerprints that
updated table. Historical pre-fix measurements remain in Git and the
[workload](LONG_HORIZON_DIAGNOSIS.md#enrolled-assignment-workload-correction) and
[Kember event](LONG_HORIZON_DIAGNOSIS.md#kember-missed-assignment-event-correction)
comparisons.

The curve and holdout files have no `complete` or `expected_runs` fields. Their
completeness must be checked from the design: exactly **15 base rates × 5 seeds
= 75** unique curve runs, four semester records per run, and **3 horizons × 5
seeds = 15** unique holdout runs. These counts, sequential risk sets, saved
dropout fractions, and all **60** lookup means were checked against the
versioned files during this documentation correction. Both modes of
`measure_dropout_horizons.py` save completed-run checkpoints by direct writes,
not the atomic replacement used by
the diagnosis/comparison scripts. A readable partial file is not proof of a
finished sweep.

The holdout's `curve_sha256` matches the checked-out curve file bytes:
`002781cb012e4a9b2e6c97cbe7780b9e48ebc680f96b8f69a0b5f9dac824b732`.
Its recorded `synthed/calibration.py` hash also matches the current mapper.
However, its recorded Kember source hash
`4682f48534e17bf70eb11f426a1923bb65ffa078e85fb29fd0c34147a1535929`
differs from source revision `7636677`'s audited checkout byte hash
`6a6ea9d35ff8da953391cf74f853108568ee4fa4653836ead97b94ece5204719`,
including after LF/CRLF normalization. Thus the tables are verified archived
measurements supporting the shipped lookup values, not a verified byte-identical
rerun of all current production source. The recorded base revision `7ebc22c`
alone cannot recover the then-uncommitted generating Kember file. This source
provenance gap remains; the measurements were not regenerated for a prose edit.

Validation is run on each completed four-semester cohort, using complete observed
histories and the explicit 56-week horizon. Histories are not padded after dropout
or passed back into theory state. Measurements fail on execution errors rather
than inserting missing or fabricated observations.

### Targeting on independent seeds

The [holdout results](measurements/dropout-targeting-holdout.json) use seeds 47–51,
N=500, default settings, and target `(0.30, 0.45)`. The artifact records the curve
file's SHA-256 checksum, configuration, dependencies and generating-source hashes.
Repeat the design with the current source using:

```bash
python scripts/measure_dropout_horizons.py --target-range 0.30 0.45 --seeds 47 48 49 50 51 --curve-evidence docs/measurements/dropout-horizons.json --output output/dropout-targeting-holdout.json
```

Validation remains enabled; only exports are suppressed.

`--curve-evidence` fingerprints the named JSON; it does not load its values into
the mapper or verify that the runtime lookup was derived from it. The holdout
uses `synthed/calibration.py`'s built-in table. Independently checking all 60
lookup means against the curve counts is therefore necessary provenance work.
The script also accepts any distinct supplied seeds; it does not enforce
disjointness from the curve seeds. The archived sets 42–46 and 47–51 are disjoint.

| Semesters | Estimated base rate | Mean dropout | Seed SD (percentage points) | Observed seed range |
|-----------|---------------------|--------------|----------------------------|---------------------|
| 1 | 0.561667 | 36.88% | 3.50 | 31.2–40.2% |
| 2 | 0.099919 | 36.80% | 1.89 | 34.4–39.4% |
| 4 | 0.018592 | 34.96% | 3.15 | 30.4–38.2% |

All 15 runs met the requested range, and all three horizon means are inside it. The
holdout was not used to retune the lookup table. This checks one target and default
configuration, not arbitrary horizons, populations or targets. Students interact,
so seed-level variability is reported instead of treating all student outcomes as
independent Bernoulli observations. Re-measure after model or RNG changes.

The displayed seed SDs use the sample denominator **k−1** with k=5. The
three-semester curve is measured, but the saved independent-seed targeting
check covers only 1, 2 and 4 semesters. All 15 holdout runs execute 22 validation
checks; their pass counts range from **18 to 20**, so target attainment does
not mean every validation check passed. These artifacts preserve validation
summaries, not the individual coefficients or checks needed to audit each failure.

## Why cumulative dropout grows

For semester `t`, conditional dropout is the number leaving during that semester
divided by the number who entered it. Cumulative dropout counts all departures
against the original cohort. With permanent dropout, cumulative dropout cannot
decrease. Conditional rates need not decline.

At default base rate 0.46, seeds 42–46 give:

| Semester | Mean cumulative dropout | Cumulative seed SD (percentage points) | Conditional dropout, pooled risk sets |
|----------|-------------------------|---------------------------------------|--------------------------------------|
| 1 | 35.60% | 2.87 | 35.60% |
| 2 | 63.48% | 2.97 | 43.29% |
| 3 | 80.28% | 2.89 | 46.00% |
| 4 | 88.60% | 1.62 | 42.19% |

These high default rates remain a modeling limitation, not an externally validated
retention curve. The changes repair known implementation problems: UUID-dependent
peer sampling, overwritten break engagement recovery, lost raw mastery
accumulators, exhaustion load from unenrolled courses, and repeated Kember
missed-event charges in weeks without a new miss. The last correction preserves
the existing streak threshold, graded-item precedence and ongoing cost-benefit
feedback. These fixes do not impose a decreasing hazard or retune theory coefficients
to obtain an attractive curve. Real institutional cohort data and a justified
calibration objective are needed before making such claims.

The [long-horizon diagnosis](LONG_HORIZON_DIAGNOSIS.md) retains the eight-scenario
pre-fix analysis, records the workload and Kember corrections' before/after
comparisons, and specifies the remaining mechanism audit and empirical
calibration steps.

## What an A/B validation grade means

The grade is an unweighted summary of the fraction of executed validation checks
passing. Conditional checks change its denominator. It is not external validation
of a multi-year dropout trajectory.

The thresholds are A ≥90%, B ≥75%, C ≥60%, D ≥40%, and F below 40%. With
22 executed checks, A needs at least 20 passes and B at least 17. This denominator
is observed in these N=500 measurements, not a fixed promise for every run.

With targeting enabled, the dropout reference is the user's requested range;
passing that check demonstrates target compliance. Other checks retain fixed
heuristics: for example, `baulke_phase_distribution` requires terminal-phase
prevalence at most 50%, and early attrition expects at least 30% of departures in
the first half of the run. Such checks may disagree with a high cumulative target.
Read individual results and their assumptions; a lower letter grade across
horizons does not by itself demonstrate lower empirical validity.

The standard correlations use Pearson r for continuous outcomes and
point-biserial r for dropout. They need more than ten usable observations and
usually pass on **sign alone**. Reported reference coefficients and p-values
are not magnitude-matching or significance gates. The engagement–GPA check
compares each learner's mean engagement over observed weeks with their
transcript GPA (rounded to two decimals in validation data); no post-dropout
weeks are imputed. Undefined coefficients must remain visible rather than being
interpreted as zero or as evidence of preserved correlations. Full comparison
artifacts in [Long-horizon diagnosis](LONG_HORIZON_DIAGNOSIS.md) serialize
non-finite validation fields as `null` and identify them explicitly; the regular
pipeline report is not subject to that additional serialization step.
