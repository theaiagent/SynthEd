# Long-horizon dropout: diagnosis and calibration plan

The eight-scenario diagnosis below is historical evidence introduced in commit
`511a4d7`, before the enrolled-assignment workload and Kember event corrections.
The artifact records base checkout `205c58e`, plus generating-source hashes for
the work present during measurement; its recorded Git revision is not `511a4d7`.
The measurements behind the shipped lookup are in
[Dropout Targeting](DROPOUT_TARGETING.md). The later workload and Kember
comparisons are retained separately below.

The validation counts and grades in these archived measurements are preserved
as recorded. Current reports use assessed checks as the grade denominator and
emit two visible unassessed backstory rows when text is absent, bringing the
default total to 24 with temporal assessment. Pipeline validation also forwards
actual outcome labels for configured pass/distinction checks. These reporting
repairs do not alter the model measurements below; see
[Validation Suite](THEORY.md#-validation-suite).

## Scope and reproduction

This is a diagnosis of that model revision, not an empirical retention benchmark.
The diagnostic interventions did not change production coefficients. Measurements use the default base
rate 0.46, 500 students, four 14-week semesters, and seeds 42–46, matching the
design in [Dropout Targeting](DROPOUT_TARGETING.md). These are exploratory seeds
already used for the targeting curves, not an independent confirmation sample.

The [raw evidence](measurements/dropout-horizon-diagnostics.json) contains eight
scenarios × five seeds = 40 runs, configurations, generating-source hashes,
dependency versions, risk-set counts, engagement contributions, and all executed
validation checks. The Git revision identifies the base checkout; source hashes
identify the uncommitted diagnostic script used to generate the artifact.

```bash
python -m scripts.diagnose_dropout_horizons --scenarios baseline without:BeanMetznerPressure without:TintoIntegration without:SDTMotivationDynamics without:GarrisonCoI without:GonzalezExhaustion no_missed_streak_penalty reset_phase_between_terms --output output/dropout-horizon-diagnostics.json
```

This command specifies the experimental design. Running it on today's checkout
uses today's mechanisms and is not a reproduction of the historical numbers
below. Historical reproduction requires the generating source, configuration
and dependency versions identified by the artifact. Preserve the versioned
evidence and use a separate output file for a new measurement.
The diagnostic manifest's **77 source hashes** match the files in `511a4d7`
when the recorded LF/CRLF checkout form is allowed. This recovers the source
snapshot; it does not replace a rerun or dependency-version verification.

Only completed runs are checkpointed, using atomic file replacement to preserve
the previous checkpoint if serialization or publication fails. `complete` remains
false until all `expected_runs` finish; exceptions propagate. Undefined validation statistics
are encoded as JSON `null` with explicit `undefined_validation_fields`; the
original test's pass/fail result and details remain visible. In particular,
constant network degrees can leave the degree–engagement correlation undefined.
Neither a missing correlation nor a lower dropout rate constitutes a pass.
Small-cohort checks that the validator omits are listed in
`skipped_validation_checks`, with eligible counts and the validator's minimum
requirements. The manifest covers default checks; optional backstory checks and
outcome-rate reference checks are outside this CLI's default configuration.

### Evidence inventory and audit boundaries

All files below are versioned under `docs/measurements/`, with N=500. During the
documentation audit, run keys were checked for completeness and duplicates;
semester risk sets and dropout fractions were recomputed where stored. The
tables below were recalculated from those saved runs, without new simulations.

| Artifact | Recorded base revision | Design and verified run count | Completion field |
|----------|------------------------|-------------------------------|------------------|
| `dropout-horizon-diagnostics.json` | `205c58e` | 8 scenarios × seeds 42–46 = 40, each four terms | `complete=true`, expected 40 |
| `assignment-scope-before.json` | `511a4d7` | horizons 1/2/4 × seeds 42–46 = 15 | `complete=true`, expected 15 |
| `assignment-scope-after.json` | `511a4d7` | horizons 1/2/4 × seeds 42–46 = 15 | `complete=true`, expected 15 |
| `kember-event-scope.json` | `7ebc22c` | horizons 1/2/4 × seeds 42–46 = 15 | `complete=true`, expected 15 |
| `dropout-horizons.json` | `7ebc22c` | 15 base rates × seeds 42–46 = 75, each four terms | absent; count/design checked |
| `dropout-targeting-holdout.json` | `7ebc22c` | horizons 1/2/4 × seeds 47–51 = 15 | absent; count/design checked |

The first four files preserve individual validation checks. The curve and
holdout files retain only validation summaries; unlike the diagnostic and
comparison writers, their writer uses direct checkpoint writes. A partial
checkpoint cannot be accepted merely because it parses or lacks an error field.

Byte hashes need care on a checkout that converts line endings: for example,
`measure_assignment_scope.py` in the workload artifacts differs from the current
script only by LF/CRLF. A separate unresolved mismatch remains in the recorded
Kember file for the corrected comparison, curve and holdout artifacts; it is
not explained by LF/CRLF. See the exact hashes in
[Dropout Targeting](DROPOUT_TARGETING.md#reproducible-measurements). The saved
results and all 60 shipped lookup means agree numerically, but these manifests
do not establish a byte-identical reproduction from current source.

## What happens between semesters

Mean cumulative dropout is 39.60%, 73.48%, 89.76%, and 96.04%. This is partly
arithmetic: cumulative departures cannot decrease. However, the pooled
conditional rate also rises from 39.60% in term 1 to 56.09% in term 2 and around
61% in terms 3–4. The conditional denominator is the number entering that term,
not the original cohort.

The observer snapshots each entrant before any weekly event, including external
withdrawal, and snapshots survivors at each term end before break adjustments.
State means below give each seed equal weight. Phase percentages pool the
observed entrants across seeds and therefore answer a different descriptive
question; neither is an independence-based confidence interval.

| Term entered | Mean engagement at entry | Mean cost–benefit at entry | Entrants in phases 2–3, pooled |
|--------------|--------------------------|---------------------------|-------------------------------|
| 1 | 0.523 | 0.481 | 0.00% (0 / 2,500) |
| 2 | 0.211 | 0.468 | 86.62% (1,308 / 1,510) |
| 3 | 0.185 | 0.403 | 90.95% (603 / 663) |
| 4 | 0.180 | 0.344 | 86.33% (221 / 256) |

Term 1 survivors end at mean engagement 0.161. The configured break recovery
adds 0.05, producing approximately 0.211 on re-entry. The phase regression of
one step also leaves most returning students partway through the dropout
process. Thus later terms begin from a substantially different state from term 1.
Changing the targeting base rate can match a requested cumulative result, but
does not establish that these state trajectories match real learners.

## Where weekly engagement changes come from

The observer calls the real theory methods once, recording their returned
deltas. Each value below is first averaged over active student-weeks within a
seed and term, then averaged over the five seeds. Students already withdrawn
do not contribute fictional later observations.

| Direct theory contribution | Term 1 | Term 4 |
|----------------------------|--------|--------|
| Bean & Metzner | −0.02514 | −0.01321 |
| Tinto | +0.00380 | −0.02214 |
| SDT | −0.00927 | −0.01338 |
| Garrison CoI | −0.00466 | −0.01537 |
| Gonzalez exhaustion | −0.00745 | −0.01079 |

These five channels were selected for ablation because they show substantial
negative mean contributions in the baseline; this is exploratory selection.
The artifact also includes the other four engagement contributors and net peer
effects. The inline residual combines academic rewards/penalties, missed-streak
penalties, exam stress, the engagement floor, and clipping. Its positive value
in later terms must not be labeled a positive behavioral mechanism: clipping
can offset large negative proposed deltas once engagement is near its floor.

A raw delta is not a causal share of dropout. Feedback, selection, floor/clipping,
and interactions make both the trajectory and the risk set change over time.

## Controlled model interventions

For `without:ClassName`, only that class's returned engagement delta is replaced
by zero. Its state changes, random draws and other methods still run. For
example, zeroing Gonzalez's engagement return retains exhaustion accumulation
and its separate influence on Bäulke progression. Tinto's positive returns are
removed along with its negative returns.

`no_missed_streak_penalty` sets only the inline engagement coefficient to zero;
missed assignments still affect other modules and dropout decisions.
`reset_phase_between_terms` regresses surviving phases to zero at breaks; all
other carry-over settings remain at their defaults. These interventions isolate
specified code paths, not whole theories or real-world treatments.

| Scenario | Term 1 dropout | Term 4 dropout | Term 4 seed SD (pp) | Paired difference from baseline (pp) |
|----------|----------------|----------------|--------------------|--------------------------------------|
| Baseline | 39.60% | 96.04% | 1.98 | — |
| No Bean & Metzner direct delta | 25.80% | 89.16% | 2.83 | −6.88 |
| No Tinto direct delta | 40.88% | 97.20% | 0.73 | +1.16 |
| No SDT direct delta | 39.24% | 96.60% | 1.21 | +0.56 |
| No Garrison direct delta | 37.52% | 94.72% | 2.24 | −1.32 |
| No Gonzalez direct delta | 38.56% | 95.88% | 1.75 | −0.16 |
| No inline missed-streak penalty | 27.52% | 89.72% | 3.36 | −6.32 |
| Reset phase at each break | 39.60% | 90.56% | 0.65 | −5.48 |

All means and sample SDs (denominator k−1, k=5) use the five seed-level runs.
Paired differences compare the same seed, but later random-stream positions
can diverge as behavior changes;
this does not hold all future shocks identical. SD is descriptive dispersion,
not a confidence interval. The effects cannot be added, and small differences
do not establish a reliable ordering of theories.

No single tested removal produces a low four-term rate. Removing Tinto's direct
effect even increases the observed mean, despite its negative late-term delta.
These results support investigating the coupled dynamics; they do not justify
deleting a theory or arbitrarily increasing recovery until a curve looks better.
All 40 runs execute 22 validation checks; passing counts range from 14 to 18.
The existing checks include heuristic and horizon-sensitive expectations, so
these counts are diagnostic information, not external validity scores.

## Next implementation specification

1. **Establish the time and population reference.** Obtain an institutional
   cohort table with term length, entrants, withdrawals, censoring, completion,
   and consistent student/program definitions. Separate course withdrawal from
   program departure. A target cumulative percentage alone is insufficient to
   identify conditional hazards or recovery dynamics. Do not invent a declining
   hazard, recovery rate, or acceptance margin without a source.
2. **Audit the remaining mechanism contracts before retuning.** The enrolled
   workload and Kember event discrepancies have been corrected as documented
   below; their historical diagnostic results must not be presented as current
   ablations. Document the unit of each repeated pressure and recovery term.
   Specifically test whether the intended
   missed-assignment construct is a sequence of assignment opportunities or a
   weekly condition, how long its penalty persists between due dates, and whether
   exhaustion workload reflects the student's enrolled courses. Record which
   state variables should persist, recover, or restart at term boundaries. Use
   minimal failing examples for demonstrated implementation discrepancies.
3. **Fit trajectories with a bounded parameter set.** Use term-specific
   conditional departure rates and available engagement/recovery observations.
   Avoid counting cumulative and conditional rates as independent evidence.
   Estimate uncertainty across whole simulated cohorts/seeds because students
   interact. Select weights, parameter bounds and tolerances from the reference
   data and documented modeling assumptions. Preserve raw mastery/transcript
   separation and keep GPA and correlation checks visible during fitting.
4. **Require independent evaluation.** Freeze parameter choices before checking
   new seeds and, when available, a held-out institutional cohort. Report all
   risk sets, failed checks and undefined statistics. Check exact reproducibility,
   persona immutability and shorter-run/prefix equivalence. Do not accept a model
   solely because total dropout or its validation letter grade improved.
5. **Publish any behavior change separately.** Explain each changed mechanism,
   its evidence and compatibility impact. Re-measure targeting curves and their
   holdout checks after model changes, update documentation, then obtain Python,
   security and statistical review before merge.

**Trade-off:** recording contributions and testing bounded interventions makes
the model inspectable and avoids an unsupported coefficient change. It does not
yet provide empirically justified defaults, and matching several trajectories
will require more reference data and simulation work than fitting one total.

## Enrolled-assignment workload correction

The mechanism audit found a concrete scope error: `ODLEnvironment` lists due
assignments for every course, but Gonzalez exhaustion treated the entire list as
each student's workload. The correction intersects those due course IDs with
`SimulationState.courses_active`. An empty enrollment adds no assignment load;
the other stressors and recovery still apply. No coefficients or missed-streak
rules were changed.

Tests first reproduced the fault. They now verify that an unenrolled course's
assignment schedule cannot change a learner's full simulation, including state,
records, peer network and RNG state, across seeds 42, 7 and 123. Unit checks also
cover empty enrollment, enrolled load and institutional scaling.

The same measurement script was run before and after the fix, using N=500,
seeds 42–46 and separate 1/2/4-semester runs without targeting. Both
[before](measurements/assignment-scope-before.json) and
[after](measurements/assignment-scope-after.json) artifacts include full validation,
generating-source hashes and aggregate statistics. The script can be copied into
the pre-fix checkout at `511a4d7` to reproduce the former; the hashes identify
the generating bytes, including the script that was then uncommitted. A hash
identifies content but cannot recover an unavailable source file by itself.

```bash
python -m scripts.measure_assignment_scope --output output/assignment-scope.json
```

| Semesters | Mean dropout before → after | Mean GPA before → after | Mean engagement–GPA r before → after |
|-----------|-----------------------------|-------------------------|--------------------------------------|
| 1 | 39.60% → 38.72% | 2.8580 → 2.8591 | 0.5305 → 0.5385 |
| 2 | 73.48% → 71.84% | 2.8493 → 2.8501 | 0.4715 → 0.4829 |
| 4 | 96.04% → 95.28% | 2.8463 → 2.8470 | 0.3918 → 0.4122 |

Each cell averages five seed-level results. GPA includes students with graded
items, as defined by `summary_statistics`. Correlations are descriptive means of
the validator's per-seed reported coefficients, not pooled estimates or tests.
The engagement–GPA input pairs use each student's mean observed-week engagement
and transcript GPA rounded to two decimals; the full-precision GPA mean in the
adjacent column is a separate aggregate. Validation coefficients themselves are
serialized to four decimals before the means shown here are calculated.
The same seeds match initial conditions; feedback can change subsequent random
draws and cohort composition. These results do not imply that every individual
or seed must improve. All 30 runs retain the 22 default validation checks.

Validation pass counts are unchanged in the one-term runs. The two-term seed-46
run gains the network-degree check; at four terms, seed 43 loses that check
because degree becomes constant, while seed 46 gains the conscientiousness and
network-degree checks. Undefined coefficients remain explicit `null` values.
Mean correlation signs are preserved wherever estimable in these five-seed
comparisons, but magnitudes change and the already-negative four-term CoI
correlation persists. This is not evidence that every correlation improves or
that five seeds establish equivalence.

**Trade-off:** the correction restores student-specific workload without tuning
the model to a preferred dropout rate. It changes seeded trajectories and thus
requires refreshed targeting curves and independent-seed checks. Four-term
dropout remains high: this scope fix does not resolve the broader dynamics or
establish external validity. The subsequent missed-assignment audit led to the
Kember correction below.

## Kember missed-assignment event correction

Kember previously deducted its missed-assignment cost every eligible week while
the streak remained at least two, including weeks with no new miss. The correction
requires a `missed_assignment` event matching the current semester-local week in
the learner's memory. The engine records these events before theory dispatch and
clears them at semester transitions. Without a known matching week, no new charge
is applied.

This is an implementation contract: the existing 0.03 charge occurs once per
eligible weekly step, not once per missed course. The streak threshold of two
and positive graded-item precedence are unchanged. Past cost-benefit reductions,
opportunity cost and ongoing engagement feedback still apply. No coefficient,
SDT mechanism or inline engine missed-streak penalty was changed. Tests cover
stale and future events, missing time, multiple misses, graded-item precedence,
and real engine assignment events across three seeds.

The [pre-correction baseline](measurements/assignment-scope-after.json) and
[corrected results](measurements/kember-event-scope.json) use N=500, seeds 42–46
and separate 1/2/4-semester runs without targeting. The corrected artifact contains
all 15 expected runs, full validation and source hashes. Reproduce it with the
existing outcome-comparison script:

```bash
python -m scripts.measure_assignment_scope --output output/kember-event-scope.json
```

Both artifacts fingerprint the lookup table present before their respective
untargeted sweeps; neither consumes that table. The measurement script's byte
hash differs because of LF/CRLF checkout line endings; its code is unchanged.
The implemented correction is the Kember event gate. The saved targeting
holdout fingerprints the updated lookup table and its curve evidence. Its Kember
hash and the corrected comparison's Kember hash agree with each other but differ
from current source, as noted above; the base revision alone does not recover
that generating file. The commands here describe the measurement procedure,
not a verified exact replay of that archived source snapshot.

| Semesters | Mean dropout before → after | Mean GPA before → after | Mean engagement–GPA r before → after |
|-----------|-----------------------------|-------------------------|--------------------------------------|
| 1 | 38.72% → 35.60% | 2.8591 → 2.8577 | 0.5385 → 0.5481 |
| 2 | 71.84% → 63.48% | 2.8501 → 2.8475 | 0.4829 → 0.4873 |
| 4 | 95.28% → 88.60% | 2.8470 → 2.8422 | 0.4122 → 0.3961 |

These are means of five seed-level results, using the same GPA and correlation
definitions as the workload comparison. Paired four-term dropout changes range
from −8.6 to −5.2 percentage points, averaging −6.68 points. Matching seeds does
not hold later random draws or cohort composition fixed. No equivalence margin
was specified, so the small GPA differences do not establish equivalence.

All 30 before/after runs retain 22 validation checks. One-term pass counts are
unchanged. At two terms, seed 43 loses the network-degree check; at four terms,
seeds 42 and 43 gain it. Other check outcomes are unchanged. Mean Pearson
correlation signs are preserved where estimable, but magnitudes change; the
four-term engagement–GPA correlation decreases and the negative CoI correlation
persists. Undefined coefficients remain explicit `null` values. These findings
do not imply that all correlations improve or that every validation check passes.

All 60 targeting lookup points were derived from the 75 completed four-term runs
in the archived sweep; their values were checked against the counts in this audit.
With the updated curves, all 15 independent-seed runs (47–51, horizons 1/2/4)
met the 30–45% target; the holdout did not retune the curves. Full means, seed
variation and limits are in [dropout targeting](DROPOUT_TARGETING.md).

**Trade-off:** the correction removes repeated charges for an old event and
materially reduces simulated dropout, while changing seeded trajectories and
some GPA/correlation results. The corrected artifact's four-term mean is 88.60%;
this does not establish a realistic retention trajectory. The remaining mechanism
contracts and empirical calibration still require investigation.
