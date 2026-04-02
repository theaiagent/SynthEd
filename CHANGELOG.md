# Changelog

All notable changes to SynthEd are documented here.

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
