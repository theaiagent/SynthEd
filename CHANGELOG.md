# Changelog

All notable changes to SynthEd are documented here.

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
