# Changelog

All notable changes to SynthEd are documented here.

## [Unreleased]

### Added
- **Calibrate tab named validation scorecard** (audit P1-1, PR B) replaces the placeholder inside `#calibrate_content_area` with a collapsible bslib-accordion table listing every test in `report["validation"]["results"]` by name, metric, synthetic value, reference, statistic, p-value, and pass/fail marker. Empty-state handling for "no simulation yet" and "no validation data" states. Interpretive footer on the multiple-testing regime (≈1.1 expected false positives at α=0.05 across ~22 tests under positive dependence). New module `synthed/dashboard/components/calibrate_panel.py`; `app.py` swaps `calibrate_placeholder_ui` for `calibrate_panel_ui` and adds one inline `calibrate_area` render that reads the existing `sim_results` reactive. No new reactives, no OULAD reads. OULAD reference overlay (audit P1-2) is deferred to PR B.2/B.3/B.4 after statistical review found unresolved scale-mismatch (engagement) and filter-parity (score) issues — see `docs/superpowers/specs/2026-04-19-calibrate-tab-pr-b-design.md` §7. Tests: new `tests/test_dashboard_calibrate.py` (31 tests); `tests/test_dashboard_nav.py::test_calibrate_placeholder_has_no_run_button` replaced by `test_calibrate_panel_swap_uses_new_component`. Post-review corrections: (1) `calibrate_area` now calls the shared `_get_validation_results` helper instead of inlining the dispatch (architect Q1); (2) `_scorecard_footer` rewritten to distinguish α-governed hypothesis tests from deterministic range/threshold/sign checks and to surface the `_effective_alpha(N) = max(0.05·√(200/N), 0.001)` scaling (statistician round-4 review); (3) non-dict entries now raise a visible Bootstrap-warning banner above the table instead of being silently dropped.
- **Dashboard accessibility pack** addresses the P1-6 / P1-7 / P1-10 / P3-2 findings deferred from the 2026-04-17 dashboard audit:
  - **P1-6 keyboard focus visibility** (WCAG 2.4.7): `theme.py` adds a `*:focus-visible` rule (2px solid `var(--accent)` + 2px offset) plus stronger 0.5-opacity focus shadows on `.btn`, `.accordion-button`, `.preset-btn`, and a 4px-ring slider-handle indicator. Mouse clicks keep the existing aesthetic via the `:focus-visible` UA heuristic; only keyboard tabbing paints the strong ring.
  - **P1-7 tooltip ARIA**: `_tooltip_icon()` in `components/param_panel.py` now emits `aria-label="Help: <description>"` + `role="img"` on the `?` glyph span, so screen readers announce the parameter help text on focus instead of "question mark" / nothing.
  - **P1-10 numeric-input locale**: `app.py` head injects a small JS that sets `document.documentElement.lang = 'en'` and walks every `input[type="number"]` to apply `lang="en"` + `inputmode="decimal"`. A `MutationObserver` re-applies on dynamically-mounted editors (`distribution_editors`, accordion expansion). Fixes "2,3" rendering for value 2.3 in TR Chrome.
  - **P3-2 section heading contrast**: new `.section-heading` class (uppercase, 700 weight, `--text-primary` color, 0.5 px tracking) restores the heading affordance on the three audit-named muted headings — "Distributions" (`app.py`), "Presets" (`components/param_panel.py`), and the per-distribution label (Gender / Region / Prior Education etc.) in `components/distribution_editor.py`. In-accordion sub-headings already had the `.accordion-body h6` override and are unchanged.
  - Tests: new `tests/test_dashboard_a11y.py` covers tooltip ARIA + locale script presence; `tests/test_dashboard_theme.py` extended with `test_focus_visible_outline_present` and `test_section_heading_class_defined` regression guards.
- **Phase 1.5 `synthed/analysis/` coverage uplift** raises the two laggard files into the safe zone: `nsga2_calibrator.py` 69% → 94% and `sobol_sensitivity.py` 83% → 98%. New tests cover the previously-uncovered `_run_parallel` paths in both modules (real `ProcessPoolExecutor` with `n_workers=2`, minimal `n_students`/`n_trials` for IPC + pickling fidelity), profile-as-`BenchmarkProfile`-object branches in `NSGAIICalibrator.run`/`validate_solution`/`reevaluate_pareto_front`, the no-feasible-solutions error path, sequential trial-exception handling, milestone progress logging, and the `inst.*`/`grading.*` field-validation errors in `SobolAnalyzer`. Aggregate `analysis/` component now **95%** (full suite, was 88%) — comfortably above the new blocking 85% codecov gate. Mocking subprocess workers is intentionally avoided — the parallel branches must exercise real pickling and IPC to catch issues that mocks would mask.
- `synthed/doc_facts.py` now counts `pytest.mark.parametrize` cardinality when tallying the test suite. The previous AST-only tally undercounted by one for every parametrized test (only `test_dashboard.py::test_port_validation_out_of_range[80,70000]` exists today, hence the 821-vs-822 drift between `doc_facts` and `pytest --collect-only`). Recognises the literal-list form of the second positional argument; non-literal forms still fall back to a single test (preserves prior behaviour for dynamic parametrize sources).
- `.codecov.yml` with project-tailored, per-component coverage targets calibrated to the actual structure of the codebase (theory modules 95%, simulation engine 90%, validation/utils/data_output/agents 88-90%, pipeline 95%, analysis 85% blocking after Phase 1.5 uplift, dashboard 70% informational). Project status uses `target: auto` with a 1 pp threshold; patch status is informational. CLI tooling (`synthed/doc_facts.py`) and root-level orchestration scripts (`run_*.py`) excluded from measurement.

### Changed
- **`ValidationResult.passed` contract tightened** (issue #93, follow-up from PR B): `ValidationResult.__post_init__` now rejects non-bool `passed` values with `TypeError`. `numpy.bool_` (emitted by validator comparisons like `ks_p > alpha`) is coerced to Python `bool` — numpy 2.x no longer subclasses `bool`, which would otherwise have tripped the strict check. All 19 `passed=` sites in `synthed/validation/validator.py` verified bool-compliant. Dashboard consumers (`validation_grade`, `scorecard_table` count) can now rely on strict-bool semantics without `is True` guards.
- **`_get_validation_results` becomes the single canonical normalizer** (issue #94, follow-up from PR B): the helper now filters non-dict rows internally and returns `tuple[list[dict], int]` where the second item is the count of malformed entries dropped. `scorecard_table`, `validation_grade`, `validation_grade_sub`, and `chart_validation` all drop their inline `isinstance(r, dict)` guards — four drift-prone filter stances collapse to one. `scorecard_table` signature becomes `(results, dropped=0)`; the dashboard's `calibrate_area` now calls `scorecard_table(*_get_validation_results(report))` to unpack the tuple.
- **Phase 1.5 documentation quality pass**: comprehensive audit and resync of public docs (`README.md`, `docs/THEORY.md`, `docs/CALIBRATION_METHODOLOGY.md`, `docs/GUIDE.md`) against current code. Surgical precision pass with ground-truth verification for every numeric and structural claim.
  - **`docs/GUIDE.md` §Calibration Pipeline restructured** from "Four-phase pipeline (Sobol → Bayesian → Validation → NSGA-II)" to "Standard Pipeline (Sobol → NSGA-II) + Optional Helpers". The prior framing misrepresented `run_calibration.py`, which only runs two phases; `TraitCalibrator` and `validate_against_oulad` are standalone utilities invoked only in `tests/test_trait_calibration.py`, never in production. All code blocks preserved; `analyzer.rank(..., top_n=20)` aligned with production default.
  - **`docs/CALIBRATION_METHODOLOGY.md` §6 Diagnostic Visualizations reframed** from prescriptive ("should accompany") to recommended; added §6.1 implementation status table showing, for each of the 7 listed diagnostics, whether v1.7.0 captures the raw data and whether a chart is rendered. None are rendered in v1.7.0; the Calibrate tab is an explicit placeholder. Chart rendering tracked as a Phase 2 deliverable in the private calibration roadmap.
  - **Validation test count corrected** from "21" to "22 (default; up to 24 with backstory validation)" across README, THEORY (three locations including Mermaid diagram), METHODOLOGY, GUIDE troubleshooting example. Actual breakdown: 3 demographics + 2 academic + 13 correlations + 3 temporal + 1 privacy = 22 default; + 2 backstory = 24 with LLM enrichment.
  - **`docs/THEORY.md` test inventory table resynced**: 10 per-file counts corrected (`persona` 26→27, `engine_grading` 6→14, `environment` 4→7, `dashboard` 42→41, `grading` 47→49, `nsga2_calibrator` 12→18, `pareto_utils` 10→19, `pipeline_integration` 11→25, `sobol` 26→37, `llm_client` 27→28); 3 missing files added (`test_report` 11, `test_dashboard_theme` 5, `test_dashboard_nav` 3). Top-level "811 tests across 46 files" now consistent with the internal table sum (previously summed to 738). L2 Correlations list gained missing `engagement-GPA` entry; L5 Backstory "consistency" split into actual two tests.
  - **`docs/THEORY.md` structural additions**: Table of Contents gained *Institutional Quality* and *Grading and Outcome Classification* entries (sections existed but were unlinked); Project Structure gained `synthed/dashboard/` and `synthed/report/` subtrees (`__main__`, `app`, `theme`, `charts`, `config_bridge`, `components/`; and `generator`, `charts`, `translations`, `templates/`). Factor Clusters table annotated that the three CoI presences (`social_presence`, `cognitive_presence`, `teaching_presence`) live on `SimulationState.coi_state`, not on `StudentPersona`.
  - **`docs/GUIDE.md` `GradingConfig` defaults corrected**: `pass_threshold` 0.50 → 0.64, `distinction_threshold` 0.85 → 0.73, `assessment_mode` `"continuous"` → `"mixed"`. Mode semantics clarified: `"mixed"` = midterm + final; `"continuous"` = midterm only, no final; `"exam_only"` = final only.
  - **`docs/GUIDE.md` multi-semester carry-over table corrected**: "Social integration (decayed 20%)" → "70% retained" (code has `social_integration_decay=0.70` retention factor, not decay fraction); "Exhaustion (reduced 70%)" → "reduced 60%" (code has `exhaustion_recovery=0.60`).
  - **`docs/GUIDE.md` Theory Protocol API documentation** gained missing 4th phase `contribute_engagement_delta` and clarified that execution order is governed by two attributes (`_PHASE_ORDER` for `on_individual_step` dispatch, `_ENGAGEMENT_ORDER` for engagement-phase dispatch).
  - **`docs/GUIDE.md` Parameter Naming Convention table** gained missing `kember.*` and `grading.*` rows; now covers all 13 active prefixes in `SOBOL_PARAMETER_SPACE`.
  - **`docs/CALIBRATION_METHODOLOGY.md` §5 workers clarification**: corrected from "workers = 8" (described as default) to "workers = 1 (CLI default); pass `--workers 8` on 16-core hosts". Added defaults note at the top of §5 distinguishing the production `run_calibration.py` invocation values (pop_size=200, n_trials=62000, n_samples=512) from the smaller class-method-signature defaults intended for quick local testing.
  - **Minor numeric/example fixes in `docs/GUIDE.md`**: 1-semester dropout estimate "~38%" preserved (matches `CalibrationMap` interpolation at `base=0.46`); troubleshooting calibrated range corrected to "~0.25 to ~0.48" (full 1-semester range across `CALIBRATION_DATA` grid); `Dashboard Calibrate tab` feature list gained "cross-seed distance comparison (42 vs 2024)" to match the placeholder at `synthed/dashboard/app.py:66-76`; troubleshooting example `Quality: D (12/21 tests passed)` updated to `12/22` for consistency with the new total.
  - **`synthed/analysis/sobol_sensitivity.py`** prefix convention comment synced with the actual parameter space: removed stale `"epstein."` entry (no entries exist in `SOBOL_PARAMETER_SPACE`); added missing `"grading."` entry (four entries exist at lines 154-158). No behavior change.
  - Follow-up issue [#87](https://github.com/theaiagent/SynthEd/issues/87) tracks auto-generating the `docs/THEORY.md` Test Suite inventory table via `doc_facts` to eliminate the drift source at the root.

### Fixed
- **Flaky `test_high_ssq_lower_dropout` / `test_low_ssq_higher_dropout`** (`tests/test_baulke_institutional.py`): the 3-seed × n=200 design gave a per-seed dropout std ≈0.0337 (SE ≈0.0195 across 3 seeds), so the 0.005 assertion threshold was ~0.26σ — well within seed variance. CI observed `diff=0.002` on Python 3.10, triggering fail-fast that also cancelled the 3.12 job. Raised seed count to 10 (seeds 41..50) and epsilon to 0.010 symmetrically for both directional tests; new SE ≈0.011 puts the threshold at ~0.9σ — still directional, no longer flaky. Full suite: 812 passed in 124s locally.

### Removed
- `synthed/dashboard/app.py::_RUN_SIMULATION_INPUT_ID` constant. It was a workaround introduced for `tests/test_dashboard_nav.py::test_calibrate_placeholder_has_no_run_button`, which sliced the module source on `def calibrate_placeholder_ui` / `\ndef ` boundaries and would have hit the `"run_simulation"` literal anywhere in the intervening lines. The test now uses `ast.get_source_segment` to extract only the `calibrate_placeholder_ui` body, so the literal at the call site (`ui.input_action_button("run_simulation", ...)` and `@reactive.event(input.run_simulation)`) no longer needs to be hidden behind a constant. Behaviour-equivalent — the input ID stays `"run_simulation"`.
- `calibration_output/nsga2_default.json` — stale 4 KB artifact from a pre-v1.7.0 quick test (Apr 12 timestamp, 500 evaluations) that was not referenced anywhere in the methodology documentation. The two seed-specific files (`nsga2_default_seed42.json`, `nsga2_default_seed2024.json`) and their combined `nsga2_all_profiles.json` are the v1.7.0 release artifacts and remain.

## [1.7.0] - 2026-04-18

### Changed
- **Calibration knee-point cross-seed log demoted to informational**: the previous binary "ROBUST/DIVERGENT" verdict against a 0.1 normalized-RMS threshold was a heuristic, not a Fisher Information–derived gate. Cross-seed parameter scatter is the expected signature of the model's structural non-identifiability (20 free parameters × 2 scalar objectives), not an optimizer regression.
- **`docs/CALIBRATION_METHODOLOGY.md` reworked**: added §7 "Limitations & Identifiability" documenting the parameter null space, Monte Carlo noise floor (~1.5–2 pp dropout σ at n=1000), parameter-interpretation caveats, and the planned identifiability improvements. Saltelli (2002) citation corrected (*Computer Physics Communications* 145(2):280-297, with DOI). §1 parameter-scope clarified (68 Sobol candidates / 70 EngineConfig fields / 20 NSGA-II actively optimized). Computational budget table updated with measured wall-clock times. §3 framing aligned with §7 (single non-identifiability story). §7.4 GPA-weight cross-seed numerical claim corrected after data re-check.
- **`docs/GUIDE.md` numerical corrections**: default benchmark profile expected dropout 35-60% → 20-45% (matches `expected_dropout_range=(0.20, 0.45)` in code), 1-semester default dropout estimate ~41% → ~38% (matches `CalibrationMap` interpolation), `CALIBRATION_DATA` measurement date 2026-03-31 → 2026-04-14, removed obsolete TraitCalibrator-era "GPA gap in calibration" troubleshooting entry (NSGA-II achieves `gpa_error=0.004`, the entry's 8.6% gap advice was stale).
- **Dashboard mode split (PR A skeleton)**: renamed the "Configure" nav tab to "Research" and added a new "Calibrate" nav tab with a placeholder describing upcoming calibration tooling. No behavior change — all current functionality is preserved under Research. The Calibrate tab is inert in this release; follow-up work will add OULAD-indexed calibration features (reference overlays, validation test scorecard, Pareto viewer, HV convergence).
- **Spectrum refactoring**: 3 binary + 1 integer persona field converted to 3 continuous [0,1] floats — `is_employed`+`weekly_work_hours` → `employment_intensity`, `has_family_responsibilities` → `family_responsibility_level`, `has_reliable_internet` → `internet_reliability`
- Factory uses Beta distributions: Beta(2.5,3) employment, Beta(2,4) family, Beta(8,2)/Beta(4,3) internet (SES-dependent)
- Bean & Metzner: `_OVERWORK_PENALTY` → `_EMPLOYMENT_PRESSURE_FACTOR` (0.04), `_OVERWORK_THRESHOLD_HOURS` removed, continuous pressure formulas
- Kember: `_OC_STRESS_THRESHOLD` removed, fully continuous opportunity cost via `employment_intensity * financial_stress * _OC_FACTOR`
- Academic Exhaustion: 1.5x scaling compensation for employment /40→/60 domain shift
- Engine: probability-weighted login hours, continuous live session attendance penalty
- Sobol parameter space: 69 → 68 params (`_OC_STRESS_THRESHOLD` removed, `_OVERWORK_PENALTY` renamed)
- `CALIBRATION_DATA` re-measured post spectrum refactoring (dropout rates shifted ~22% lower)
- README Key Features reorganized into 4 categories, Zenodo description restructured

### Fixed
- **Calibration result aggregation bug**: `nsga2_all_profiles.json` now contains all calibration seeds with an explicit `seed` field for disambiguation. Previously `all_results` was reset inside the per-seed loop in `run_calibration.py`, so the combined-profile JSON only retained the last seed's results.
- **Dashboard light theme navbar** (was invisible, 1.1:1 contrast): migrated `page_navbar` off deprecated `bg=`/`inverse=True` to `navbar_options(class_="navbar-adaptive")`. Dropping `inverse=True` removes `data-bs-theme="dark"` from the nav element which was defeating `body.light-mode` background override via Bootstrap source order. Logo + active tab now render 17:1+ contrast in both themes.
- **Dashboard tablet 768px run-bar overlap**: replaced fixed 3× `ui.column(4, ...)` row with `ui.layout_columns(col_widths={"sm":12,"lg":4})` so run button, preflight check, and status stack vertically below 992px (sidebar stays side-by-side at 768px — no media query collapses it — so main area drops below 600px and can't fit three horizontal columns).
- **Dashboard run-bar status text contrast**: Bootstrap's default `.text-secondary` color (dark gray) was winning over our CSS variable on the dark navbar, producing ~1.88:1 contrast for the "N=..., seed=..." status text (WCAG AA fail). Added an explicit `color: var(--text-secondary) !important` rule to `.text-end.text-secondary` so the status text now uses our theme variable, and raised `TEXT_SECONDARY` from `#94A3B8` (7.4:1 on `--bg`) to `#B0BCC8` (9.8:1) for consistent above-AA margin across all custom `var(--text-secondary)` usages (labels, `h6`, nav links, tooltips).
- GPA calibration target corrected: gpa_mean 2.3→3.03 (actual OULAD score proxy 75.80/100×4.0)
- NSGA-II force-include: grading params (grade_floor, pass_threshold, GPA weights) always included in optimization
- **OULAD reference statistics**: dropout 0.42→0.312 (Withdrawn only, Fail≠Dropout), gender male 0.48→0.55, employment 0.78→0.69, dropout_base_rate 0.80→0.46, dropout_range (0.35,0.55)→(0.20,0.45)
- `configs/default.json` synced with corrected PersonaConfig/ReferenceStatistics defaults
- `CALIBRATION_DATA` re-measured with corrected PersonaConfig defaults (2026-04-14)
- `docs/CALIBRATION_METHODOLOGY.md` power analysis recalculated with p=0.312 (SE, MDE, NAF, CI tables)
- Sobol/NSGA-II weight normalization: constrained weight groups (assignment, exam, submit) now normalized in `_sim_runner.py` before EngineConfig creation, preventing crash when parameters are sampled independently
- Calibration parameters: `n_students` 100→500, `n_samples` 128→512, `n_trials` 12,800→62,000, `pop_size` 160→200, validation seeds 3→10
- Sequential calibration path refactored from `study.optimize()` to manual ask/tell loop with per-generation HV tracking

### Added
- **HV convergence tracking**: `compute_hypervolume()` in `pareto_utils.py` tracks hypervolume per NSGA-II generation, stored in `ParetoResult.hv_history`
- **Pareto front re-evaluation**: `reevaluate_pareto_front()` re-evaluates solutions at N=2,000 with 3 seeds for noise-free knee-point selection
- **Replicated calibration**: 2 independent NSGA-II seeds (42, 2024) with `compare_knee_points()` for robustness comparison
- **Calibration methodology**: `docs/CALIBRATION_METHODOLOGY.md` — reference document with power analysis, NAF framework, 18 citations (now including Brun et al. 2001 and Gutenkunst et al. 2007 for the identifiability discussion)

### Removed
- Internal UI/UX audit document (`docs/dashboard-ui-audit-2026-04-17.md`) removed from the public repository. Findings have been incorporated into the relevant implementation PRs.

## [1.6.0] - 2026-04-12

### Changed
- `contribute_engagement_delta(ctx: TheoryContext) -> float` added to `TheoryModule` Protocol as engagement composition phase — 9 theories now return engagement deltas via protocol dispatch instead of inline engine calls
- `_ENGAGEMENT_ORDER` class attribute on engagement theories (Tinto=100, BeanMetzner=200, PositiveEvents=300, Rovai=400, SDT=500, Moore=600, Garrison=700, Gonzalez=800, Kember=900)
- `_update_engagement` refactored from 110-line monolith to 27-line protocol dispatch loop (engine.py 590→520 lines)

## [1.5.0] - 2026-04-09

### Added
- `TheoryModule` Protocol with phase-based dispatch (`on_individual_step`, `on_network_step`, `on_post_peer_step`)
- `TheoryContext` frozen dataclass as uniform argument envelope for theory modules
- `discover_theories()` auto-discovery function replacing hardcoded theory imports
- Engine Phase 1/2 loops now iterate over discovered theories via protocol dispatch
- `_PHASE_ORDER` class attribute on migrated theories (Tinto=10, Garrison=20, SDT=30, Epstein=40, Baulke=50)

## [1.4.0] - 2026-04-08

### Added
- `InstitutionalConfig.support_services_quality` modulates Baulke dropout phase thresholds via `scale_by()` — 13 thresholds scaled, better institutions produce lower dropout
- `PipelineConfig` frozen dataclass — groups 16 pipeline params with JSON `to_dict()`/`from_dict()` serialization
- Deprecation bridge: legacy `SynthEdPipeline(seed=42)` kwargs still work with `DeprecationWarning`

## [1.3.0] - 2026-04-05

### Added
- `grading_method="relative"` support — t-score standardization with cohort-relative outcome classification, automatic fallback for small cohorts
- `normalize_t_scores()` utility for t-score to 0-1 conversion
- `SobolAnalyzer` parallel execution via `n_workers` parameter (ProcessPoolExecutor)
- Warning when `n_students < 100` (calibration reliability)

### Changed
- `SimulationEngine._simulate_student_week` split into 5 focused methods
- `_assign_outcomes` refactored into absolute/relative dispatcher with shared eligibility filter
- `_validate_correlations` uses declarative test table via `_correlation_test` helper
- `ODLEnvironment.get_course_by_id` uses O(1) dict lookup
- Calibration mode skips temp directory I/O
- `ReferenceStatistics` and `ValidationResult` extracted to `validation/types.py`

## [1.2.0] - 2026-04-05

### Added
- **EngineConfig**: Frozen dataclass holding all 70 engine tuning constants — assignment/exam quality weights, engagement deltas, interaction parameters — with `__post_init__` validation (weight sums, ordering constraints, positivity guards)
- **`--workers N` CLI flag** for `run_calibration.py` — parallel NSGA-II calibration via ProcessPoolExecutor
- **`doc_facts --fix`**: Auto-update stale numeric metrics (test count, Sobol params) across README, THEORY, .zenodo.json
- **Codecov coverage test** for `openai` ImportError branch

### Changed
- Engine override mechanism: `setattr()` replaced with `dataclasses.replace()` on frozen `EngineConfig` — field-name allowlisting prevents arbitrary attribute injection
- `_sim_runner.py`: Cached `_ENGINE_FIELDS` / `_INST_FIELDS` frozensets at module level (was recomputing per call)
- Theory module overrides: `__dunder__` and unknown-attribute guards added to `setattr` path
- `inst_overrides` now validated against `InstitutionalConfig` fields (was unfiltered)
- Sobol threshold fix: `pass_threshold` and `distinction_threshold` sorted when both sampled independently
- Calibration output: stale old-profile JSON files removed, new `nsga2_default.json` added (12,800 trials, IN RANGE)

### Fixed
- Sobol sampling could generate `distinction_threshold < pass_threshold`, violating GradingConfig invariant

## [1.1.0] - 2026-04-03

### Added
- **GradingConfig**: Configurable institution-level grading policy (18 parameters) — Beta/Normal/Uniform distributions, weighted semester grades, dual-hurdle pass requirements, exam-only and continuous assessment modes, late penalty, exam eligibility threshold
- **Outcome classification**: Distinction/Pass/Fail/Withdrawn assignment at end of simulation run, with floor-adjusted transcript scale thresholds
- **ProcessPoolExecutor parallelism** for NSGA-II calibration — 4-8x speedup via Optuna ask/tell API
- **Sobol grading parameters**: pass_threshold, distinction_threshold, late_penalty in sensitivity analysis
- **Validation tests**: outcome distribution (pass_rate/distinction_rate) and engagement-GPA correlation
- **CodeRabbit** automated PR review configuration

### Changed
- Consolidated 4 benchmark profiles into single "default" profile (mega university parameters) — users customize via PersonaConfig/InstitutionalConfig/GradingConfig
- `summary_statistics` extracted to `synthed/simulation/statistics.py` (engine.py 800→740 lines)
- Default pass_threshold=0.64, distinction_threshold=0.73 (empirically calibrated from simulation percentiles)
- CalibrationMap re-measured post engine changes (forum quality RNG, scale_by modulation)
- Sobol space: removed dead dist_alpha/dist_beta, added outcome-affecting params (69 total)
- T-score standardization uses population std (ddof=0) instead of sample std

### Removed
- Benchmark profiles "high_dropout_developing", "moderate_dropout_western", "low_dropout_corporate", "mega_university" replaced by single "default" profile
- `_DeprecatedProfileDict` backward compatibility wrapper

### Fixed
- Grade floor now applied before outcome classification (was comparing raw quality against transcript-scale thresholds)
- Division-by-zero guard in summary_statistics for empty states
- dual_hurdle with final_score=None now fails the hurdle (was silently passing)
- grading_method="relative" rejected with clear error (was silently ignored)
- Float tolerance for weight sums: 1e-9 → 1e-6 (prevents false rejection of valid floats)

## [1.0.0] - 2026-04-02

### Added
- Dual-track GPA system: transcript GPA (grade floor applied) and perceived mastery (raw quality)
- Opportunity cost mechanism in Kember cost-benefit analysis for employed, stressed students
- Environmental shocks: stochastic life events (job loss, health crisis, family emergency) via Bean & Metzner
- InstitutionalConfig: 5 institution-level quality parameters modulating theory constants
  - instructional_design_quality, teaching_presence_baseline, support_services_quality
  - technology_quality, curriculum_flexibility
- NSGA-II multi-objective calibration via Optuna NSGAIISampler
  - 2 objectives (dropout error, GPA error), 3 constraints
  - Pareto front with geometric knee-point selection
  - Per-profile calibration with Sobol parameter selection
- Calibration mode flag for faster simulation runs (skips CSV export)
- 4 benchmark profiles with institutional quality parameters

### Changed
- Sobol parameter space expanded from 52 to 66 parameters
- Benchmark profiles include InstitutionalConfig (required field)
- Pipeline accepts optional institutional_config parameter

### Removed
- 4 unused ODLEnvironment fields (lms_availability, support_responsiveness, peer_interaction_density, institutional_dialogue_norm)

## [0.7.0] - 2026-04-02

### Added
- Benchmark report generation via `--benchmark` CLI flag with markdown comparison table and JSON results
- `--benchmark-profile` flag for running a single institutional profile
- Structural grade floor (`_GRADE_FLOOR=0.45`) reducing GPA calibration gap from 8.6% to 3.3% vs OULAD
- GitHub Sponsors support (FUNDING.yml)
- Community files: CONTRIBUTING.md, SECURITY.md, Code of Conduct, CODEOWNERS, issue/PR templates

### Changed
- Benchmark profiles recalibrated with hybrid approach (adjusted dropout_base_rate + realistic expected_dropout_range)
- Loss weight rebalance: dropout 0.50 to 0.40, GPA 0.30 to 0.40, engagement 0.20
- `CALIBRATION_DATA` re-measured post grade-floor (N=500, 5 seeds, 11 data points)
- `_GRADE_FLOOR` added to Sobol parameter space (53 params total)

## [0.6.3] - 2026-04-01

### Added
- 8 new coverage tests: auto_bounds edge cases, pipeline OULAD export, cost check blocking, Baulke GPA triggers, LLM HTTP warning, invalid scores

### Changed
- GPA gap reduced from 15% to 8.6% with 80 Optuna trials (sweet spot identified)
- Calibration documentation updated with trial count comparison table

## [0.6.2] - 2026-04-01

### Added
- GPA-dropout correlation validation test (point-biserial)
- Dropout early attrition timing validation test
- Edge case tests for auto_bounds (margin=0, missing columns)
- Empty CSV guards in OULAD target extraction

### Changed
- Dropout rate default changed from point estimate (0.50) to range-based (0.35-0.55)
- Age distribution KS test now uses deterministic one-sample kstest against theoretical CDF
- README restructured via Diataxis framework: slimmed from 578 to 127 lines
- Content reorganized into User Guide (docs/GUIDE.md) and Theory & Architecture (docs/THEORY.md)
- CI pipeline-smoke N increased to 100 for stability

### Fixed
- Stale parameter count comment corrected to 52

## [0.6.1] - 2026-04-01

### Added
- `auto_bounds()` function for adaptive Sobol parameter space generation from PersonaConfig defaults
- Configurable margin, validation range clipping, non-tuneable constant exclusion
- Per-source filtering (include_config, include_engine, include_theories)
- USAGE.md comprehensive user manual (14 sections)

## [0.6.0] - 2026-04-01

### Added
- Sobol sensitivity analysis (SALib): variance decomposition across 51 parameters with S1 and ST indices
- Bayesian optimization (Optuna TPE): weighted composite loss (50% dropout + 30% GPA + 20% engagement CV)
- OULAD comparative validation with held-out module split and letter grading
- `select_top_parameters()` bridging Sobol rankings to Optuna search space
- Shared simulation runner (`_sim_runner.py`) for DRY between Sobol and Optuna
- Assignment/exam quality weights added to Sobol parameter space (7 new GPA-driving parameters)
- `std_final_engagement` in engine summary statistics
- Column validation on OULAD CSV reads
- Dependencies: SALib>=1.4.0, optuna>=3.0.0

## [0.5.0] - 2026-03-31

### Added
- LLM backstory cluster: 7 templates, 12 life events, 8 regions, base_url for local/Ollama providers, cache TTL/LRU, cost warning, streaming
- Optional name generation: 10 regional name pools (488 first, 235 last names), off by default (`--names` to enable)
- GPA feedback loop: cumulative GPA feeds into Kember cost-benefit, Baulke non-fit/triggers, and SDT competence
- Multi-semester prior GPA update: earned GPA blends into prior_gpa (60/40 weighted) during carry-over
- Coping factor: state-level Bean & Metzner pressure attenuation with diminishing returns, 70% retention across semesters
- Zenodo metadata (.zenodo.json + CITATION.cff) with ORCID IDs

### Changed
- SeedSequence-based RNG isolation for name generation
- Log identifiers use persona.id instead of persona.name

## [0.4.2] - 2026-03-31

### Added
- 2 new validation tests: garrison_coi_engagement and epstein_network_degree_engagement correlation (19 tests total)
- README: multi-semester carry-over vs reset table, Use Cases section, behavioral fidelity positioning

### Changed
- Calibration data re-measured post-revert (N=500, 5 seeds)

### Fixed
- 2 validation tests were silently not executing (fields only in outcomes_data, validator looked in students_data)

### Removed
- Survivor resilience + pressure dampening carry-over (Approach C) reverted after architect review found theoretical grounding violations

## [0.4.1] - 2026-03-31

### Added
- 49 new tests boosting coverage from 95% to 100% (226 tests across 19 files)
- Default Calibration Targets table in README
- CalibrationMap added to architecture diagram

### Changed
- `CALIBRATION_DATA` re-measured post-v0.4.0 (N=500, 5 seeds) to account for RNG sequence shift from withdrawal feature

### Fixed
- `TypeError` in `summary_statistics()` when sorting mixed str/int keys in dropout phase distribution

## [0.4.0] - 2026-03-31

### Added
- Configurable dropout targeting: `target_dropout_range=(0.40, 0.55)` with automatic dropout_base_rate estimation via piecewise linear interpolation
- `CalibrationMap` with 11 empirical data points
- Range-based validation (replaces z-test when target range is set)
- Per-semester interim reports (on_track / below_target / above_target)
- CLI flag `--target-dropout 0.40 0.55`
- `SynthEdPipeline.from_profile()` classmethod
- UUIDv7 student IDs (RFC 9562): time-sortable, collision-free
- Dual ID system: `id` (UUIDv7) and `display_id` (S-0001 sequential)
- Unavoidable withdrawal events: serious illness, family emergency, forced relocation, career change, military deployment, death, legal issues
- GPA computation: cumulative GPA (4.0 scale) from assignment and exam quality scores
- `dropout_base_rate` wired into simulation via `_dropout_risk_scale` (was dead code)

### Changed
- Student IDs changed from 8-character hex to 36-character UUIDv7
- `PersonaConfig.dropout_base_rate` minimum changed from 0.0 to 0.01
- New default: `PersonaConfig.unavoidable_withdrawal_rate = 0.003`
- `outcomes.csv` schema: new columns display_id, withdrawal_reason, final_gpa
- `students.csv` schema: new column display_id

## [0.3.0] - 2026-03-30

### Added
- Scale-adjusted validation: `_effective_alpha(n)` reduces significance for large populations
- CI/CD: Dependabot, CodeQL, Codecov, dynamic pytest badge, branch protection
- 106 tests across 15 test files (93% branch coverage)

### Fixed
- Network scaling for large groups (>40 students): O(n^2) to O(n*k)
- Degree cap: 20 peers per activity, 25 hard safety net
- Mean degree at N=10000 reduced from 145.3 to 15.4
- Performance at N=10000 improved from 103s to 26s

## [0.2.2] - 2026-03-30

### Added
- 5 configurable factory distributions via PersonaConfig: socioeconomic, prior_education, device, goal_orientation, learning_style
- Dynamic semester name auto-generated from current date
- Configurable LLM pricing with injectable `LLMClient(pricing={...})`

### Changed
- ~150 inline magic numbers extracted to class-level `_UPPERCASE` named constants across 10 theory modules and engine.py

### Fixed
- `setup.py`: `exec()` replaced with regex for version parsing
- Backstory assignment uses `dataclasses.replace()` for immutability

## [0.2.1] - 2026-03-30

### Added
- Dynamic pytest badge via Gist (schneegans/dynamic-badges-action)
- Contributing section, Legal Disclaimer, and Responsible Use sections in README

### Changed
- Centralized version: `__version__` in `synthed/__init__.py` as single source of truth
- Default config (`configs/default.json`) aligned with current ODL PersonaConfig defaults

### Fixed
- Immutability fix: `_enrich_with_llm` now uses `dataclasses.replace()` instead of direct mutation
- LLM enrichment: retry with exponential backoff and response validation
- README accuracy: test file count and test_persona count corrections

## [0.2.0] - 2026-03-30

### Added
- SDT dynamic motivation: motivation type evolves during simulation based on autonomy, competence, and relatedness
- Positive environmental events: financial aid disbursement, semester breaks, peer study groups
- CoI to Kember link: teaching presence and CoI composite influence perceived cost-benefit
- Network link decay: peer ties weaken by 0.02/week without reinforcement
- Academic exhaustion theory module (Gonzalez et al., 2025): cumulative exhaustion with recovery capacity degradation
- Multi-semester simulation with carry-over mechanics (engagement recovery, social decay, fresh start effect, exhaustion relief)
- Python logging replaces all print() statements
- Input validation on PersonaConfig and pipeline parameters
- LLM backstory export to students.csv
- Sensitivity analysis module for OAT parameter sweeps
- 4 benchmark profiles: developing country, western university, corporate training, mega university
- GitHub Actions CI/CD: tests across Python 3.10/3.11/3.12, ruff lint, pipeline smoke tests

### Changed
- Engine refactored from 725 to 427 lines: 11 theory modules extracted to `simulation/theories/`

## [0.1.1] - 2026-03-30

### Added
- CI/CD pipeline (GitHub Actions: tests, lint, smoke tests)
- Test Suite documentation section (46 tests across 9 files)
- Legal Disclaimer and Responsible Use sections
- Contributors section
- Status badges (CI, license, Python, tests, code style, active development)

### Fixed
- Validation example output aligned with current results
- README section order reorganized for readability

## [0.1.0] - 2026-03-30

### Added
- 11 theory modules: Tinto, Bean & Metzner, Kember, Moore (Transactional Distance), Deci & Ryan (SDT), Garrison (CoI), Rovai, Baulke (6-phase dropout), Epstein & Axtell (ABSS), Gonzalez (exhaustion), positive environmental events
- Multi-semester simulation with carry-over mechanics
- Peer social network: emergent link formation, engagement contagion, dropout cascades, link decay
- 17+ validation tests across all theoretical frameworks
- Sensitivity analysis: OAT parameter sweeps for dropout predictors
- 4 benchmark profiles: developing country, western university, corporate training, mega university
- CSV data export pipeline
