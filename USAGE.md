# SynthEd User Manual

A practical guide for researchers using SynthEd to generate synthetic ODL data, calibrate against institutional data, and validate output quality.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Population Configuration](#population-configuration)
4. [Dropout Targeting](#dropout-targeting)
5. [Multi-Semester Simulation](#multi-semester-simulation)
6. [Benchmark Profiles](#benchmark-profiles)
7. [Calibration Pipeline](#calibration-pipeline)
8. [Custom Reference Data](#custom-reference-data)
9. [OULAD-Compatible Export](#oulad-compatible-export)
10. [LLM Enrichment](#llm-enrichment)
11. [Output Files](#output-files)
12. [Validation Suite](#validation-suite)
13. [Advanced: Engine Constants](#advanced-engine-constants)
14. [Troubleshooting](#troubleshooting)

---

## Installation

```bash
git clone https://github.com/theaiagent/SynthEd.git
cd SynthEd
pip install -e ".[dev]"

# Verify
python -c "import synthed; print('OK')"
```

**Requirements:** Python 3.10+, numpy, scipy, SALib, optuna.

---

## Quick Start

### CLI

```bash
# Default: 200 students, 14-week semester
python run_pipeline.py

# Custom population
python run_pipeline.py --n 500

# Target specific dropout range
python run_pipeline.py --n 300 --target-dropout 0.40 0.55

# OULAD-compatible export
python run_pipeline.py --n 300 --oulad

# With culturally diverse names
python run_pipeline.py --n 200 --names
```

### Python API

```python
from synthed.pipeline import SynthEdPipeline

pipeline = SynthEdPipeline(output_dir="./output", seed=42)
report = pipeline.run(n_students=300)

print(f"Dropout: {report['simulation_summary']['dropout_rate']:.1%}")
print(f"GPA: {report['simulation_summary']['mean_final_gpa']:.2f}")
print(f"Quality: {report['validation']['summary']['overall_quality']}")
```

---

## Population Configuration

`PersonaConfig` controls population-level demographics. Every float field influences simulated behavior.

```python
from synthed.agents.persona import PersonaConfig

config = PersonaConfig(
    # Bean & Metzner: External factors
    employment_rate=0.78,           # fraction employed (0-1)
    has_family_rate=0.52,           # fraction with family responsibilities
    financial_stress_mean=0.55,     # mean financial stress (0-1)

    # Academic background
    prior_gpa_mean=2.3,             # mean prior GPA (0-4)
    prior_gpa_std=0.8,

    # Rovai: Student skills
    digital_literacy_mean=0.50,     # mean digital literacy (0-1)
    self_regulation_mean=0.42,      # mean self-regulation (0-1)

    # Dropout calibration
    dropout_base_rate=0.80,         # base dropout risk scaling (0.01-1.0)

    # Disability (Rovai: accessibility)
    disability_rate=0.10,           # fraction with disability (0-1)
)

pipeline = SynthEdPipeline(persona_config=config, seed=42)
report = pipeline.run(n_students=300)
```

### Matching Your Institution

Set parameters from your institution's aggregate statistics:

| Your Data | SynthEd Parameter |
|-----------|-------------------|
| 65% students employed | `employment_rate=0.65` |
| Mean GPA 2.8 | `prior_gpa_mean=2.8` |
| 40% family responsibilities | `has_family_rate=0.40` |
| 8% disability rate | `disability_rate=0.08` |

---

## Dropout Targeting

Instead of manually tuning `dropout_base_rate`, specify the desired dropout range:

```python
pipeline = SynthEdPipeline(
    target_dropout_range=(0.30, 0.45),  # auto-calibrates
    seed=42,
)
report = pipeline.run(n_students=300)
```

The system uses `CalibrationMap` to estimate the `dropout_base_rate` needed.

---

## Multi-Semester Simulation

```python
pipeline = SynthEdPipeline(
    output_dir="./multi",
    seed=42,
    n_semesters=4,
)
report = pipeline.run(n_students=300)
```

Between semesters: engagement recovers (+0.05), dropout phase regresses by 1, prior GPA blends with earned GPA (60/40), coping factor retains 70%.

---

## Benchmark Profiles

Pre-defined institutional contexts:

```python
pipeline = SynthEdPipeline.from_profile("high_dropout_developing")
report = pipeline.run(n_students=500)
```

| Profile | Expected Dropout |
|---------|-----------------|
| `high_dropout_developing` | 60-90% |
| `moderate_dropout_western` | 30-60% |
| `low_dropout_corporate` | 5-30% |
| `mega_university` | 55-85% |

---

## Calibration Pipeline

Three-phase pipeline that tunes SynthEd parameters against real data.

### Phase 1: Sobol Sensitivity Analysis

Identifies which parameters most influence outcomes:

```python
from synthed.analysis.sobol_sensitivity import SobolAnalyzer

analyzer = SobolAnalyzer(n_students=200, seed=42)
results = analyzer.run(n_samples=128)  # 128 * (D+2) simulations

# Rank by total-order index for dropout
rankings = analyzer.rank(results[0], top_n=15)
for r in rankings:
    print(f"{r.rank:2d}. {r.parameter:<40s} ST={r.st:.4f}")
```

### Phase 2: Bayesian Optimization

Optimizes top parameters against reference data:

```python
from synthed.analysis.trait_calibrator import TraitCalibrator, select_top_parameters
from synthed.analysis.oulad_targets import extract_targets

# Extract targets from OULAD (or your own data)
targets = extract_targets("oulad/")

# Select top-15 from Sobol
top_params = select_top_parameters(rankings, top_n=15)

# Run Optuna optimization
calibrator = TraitCalibrator(
    targets=targets,
    n_students=200,
    seed=42,
    parameters=top_params,
)
result = calibrator.run(n_trials=100)

print(f"Best loss: {result.best_loss:.4f}")
print(f"Dropout: {result.target_dropout:.1%} -> {result.achieved_dropout:.1%}")
print(f"GPA: {result.target_gpa:.3f} -> {result.achieved_gpa:.3f}")
```

### Phase 3: Held-Out Validation

Validates calibrated parameters on unseen data:

```python
from synthed.analysis.oulad_validator import validate_against_oulad

report = validate_against_oulad(
    calibrated_params=result.best_params,
    oulad_dir="oulad/",
    n_students=200,
    seed=42,
)

print(f"Grade: {report.grade} ({report.passed_count}/{report.total_count})")
for m in report.metrics:
    status = "PASS" if m.passed else "FAIL"
    print(f"  [{status}] {m.name}: {m.synthed_value:.4f} vs {m.oulad_value:.4f}")
```

### Auto-Bounds: Adaptive Parameter Space

When you change `PersonaConfig` defaults, the hardcoded parameter bounds may not cover your values. Use `auto_bounds()` to generate bounds automatically:

```python
from synthed.analysis.auto_bounds import auto_bounds

# Default config — bounds centered on default values
params = auto_bounds()

# Custom config — bounds adapt to your institution
my_config = PersonaConfig(employment_rate=0.95, prior_gpa_mean=3.5)
params = auto_bounds(config=my_config, margin=0.3)  # +/- 30% around defaults

# Use in Sobol or calibrator
analyzer = SobolAnalyzer(n_students=200, parameters=params)
calibrator = TraitCalibrator(targets=targets, parameters=params)
```

`auto_bounds()` options:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `margin` | 0.5 | Variation range (0.5 = +/-50%) |
| `include_config` | True | Include PersonaConfig fields |
| `include_engine` | True | Include engine constants |
| `include_theories` | True | Include theory module constants |
| `exclude` | `frozenset()` | Specific parameters to skip |

---

## Custom Reference Data

You don't need OULAD. Create an `OuladTargets` object from your own institutional data:

```python
from synthed.analysis.oulad_targets import OuladTargets

my_targets = OuladTargets(
    # From your institution's data
    overall_dropout_rate=0.25,
    module_dropout_rates={"CS101": 0.30, "MATH201": 0.20},
    score_mean=72.0,
    score_std=15.0,
    score_median=75.0,
    gpa_mean=2.88,    # score_mean / 100 * 4.0
    gpa_std=0.60,
    engagement_mean=25.0,   # clicks/day or similar metric
    engagement_std=12.0,
    engagement_median=22.0,
    engagement_cv=0.48,     # std / mean (scale-independent)
    disability_rate=0.08,
    gender_male_rate=0.45,
    n_students=5000,
)

# Use with calibrator
calibrator = TraitCalibrator(targets=my_targets, n_students=200)
result = calibrator.run(n_trials=100)
```

### What Statistics Do You Need?

| Required | How to Compute | SynthEd Comparison |
|----------|---------------|-------------------|
| Overall dropout rate | Withdrawn / Total | Direct comparison |
| Mean GPA | Average of final grades, 0-4 scale | Direct comparison |
| Engagement CV | std(engagement) / mean(engagement) | Scale-independent shape |
| Score mean | Average assessment score (0-100) | Approximate via GPA * 25 |

**Note:** SynthEd engagement (0-1 probability) and institutional engagement (clicks, logins, etc.) use different scales. The calibrator uses coefficient of variation (CV) for scale-independent comparison. You need `engagement_std` and `engagement_mean` from your data.

---

## OULAD-Compatible Export

Generate data matching the Open University Learning Analytics Dataset schema:

```bash
python run_pipeline.py --n 300 --oulad
```

```python
pipeline = SynthEdPipeline(output_dir="./output", seed=42, export_oulad=True)
report = pipeline.run(n_students=300)
```

Produces 7 CSV files in `output/oulad/` with exact OULAD column names.

### Module Filter for Split Analysis

```python
from synthed.analysis.oulad_targets import extract_targets

# Only analyze specific OULAD modules
targets_bbb = extract_targets("oulad/", modules={"BBB", "FFF"})
targets_ccc = extract_targets("oulad/", modules={"CCC"})
```

---

## LLM Enrichment

Add narrative backstories to synthetic students (optional, requires API key):

```bash
export OPENAI_API_KEY="your-key"
python run_pipeline.py --n 100 --llm

# Local Ollama
python run_pipeline.py --n 100 --llm --base-url http://localhost:11434/v1

# Cost control
python run_pipeline.py --n 500 --llm --cost-threshold 2.0
```

Backstories explain *why* each student behaves the way they do — useful for publications and presentations. No effect on simulation mechanics.

---

## Output Files

| File | Description | Key Columns |
|------|-------------|-------------|
| `students.csv` | Initial persona attributes | student_id, display_id, age, personality traits, motivation |
| `interactions.csv` | Timestamped LMS events | student_id, week, interaction_type, quality_score |
| `outcomes.csv` | Final results | student_id, has_dropped_out, final_gpa, final_engagement |
| `weekly_engagement.csv` | Time series | student_id, week-by-week scores |
| `pipeline_report.json` | Full metadata + validation | |

---

## Validation Suite

19 statistical tests across 5 levels:

```bash
python -m pytest tests/ -v --tb=short
```

| Level | Tests | What It Checks |
|-------|-------|----------------|
| L1: Distributions | KS-test, chi-squared | Age, gender, GPA match reference |
| L2: Correlations | Pearson, point-biserial | Theory-expected relationships hold |
| L3: Temporal | Trend analysis | Dropout students show declining engagement |
| L4: Privacy | k-anonymity | No re-identification risk |
| L5: Backstory | Content checks | LLM output is consistent and non-empty |

Quality grades: **A** (80%+), **B** (60%+), **C** (40%+), **D** (<40%).

---

## Advanced: Engine Constants

Override simulation engine and theory module constants for experiments:

```python
from synthed.analysis._sim_runner import run_simulation_with_overrides
from synthed.agents.persona import PersonaConfig

# Run a single simulation with custom parameters
metrics = run_simulation_with_overrides(
    overrides={
        "config.employment_rate": 0.90,
        "engine._TINTO_DECAY_BASE": 0.08,
        "bean._FINANCIAL_PENALTY": 0.025,
        "baulke._DECISION_RISK_MULTIPLIER": 0.15,
    },
    n_students=200,
    seed=42,
    default_config=PersonaConfig(),
)
print(f"Dropout: {metrics['dropout_rate']:.1%}")
print(f"GPA: {metrics['mean_gpa']:.2f}")
```

### Parameter Naming Convention

| Prefix | Target | Example |
|--------|--------|---------|
| `config.*` | PersonaConfig field | `config.employment_rate` |
| `engine.*` | SimulationEngine constant | `engine._TINTO_DECAY_BASE` |
| `tinto.*` | TintoIntegration | `tinto._ACADEMIC_EROSION` |
| `bean.*` | BeanMetznerPressure | `bean._OVERWORK_PENALTY` |
| `kember.*` | KemberCostBenefit | `kember._MISSED_PENALTY` |
| `baulke.*` | BaulkeDropoutPhase | `baulke._DECISION_RISK_MULTIPLIER` |
| `sdt.*` | SDTMotivationDynamics | `sdt._INTRINSIC_THRESHOLD` |
| `rovai.*` | RovaiPersistence | `rovai._FLOOR_SCALE` |
| `garrison.*` | GarrisonCoI | `garrison._SOCIAL_DECAY` |
| `gonzalez.*` | GonzalezExhaustion | `gonzalez._ENGAGEMENT_IMPACT` |
| `moore.*` | MooreTransactionalDistance | `moore._STRUCTURE_WEIGHT` |

---

## Troubleshooting

**"validate_range: employment_rate must be between 0.0 and 1.0"**
PersonaConfig fields have strict validation. Check your values.

**"Unknown PersonaConfig field" during Sobol**
A parameter name in SobolParameter doesn't match any PersonaConfig field. Check spelling or use `auto_bounds()`.

**Validation grade D or F**
Small population sizes (N<100) produce high stochastic variance. Use N=200+ for reliable validation.

**LLM enrichment fails with 429**
Rate limit hit. SynthEd retries automatically with exponential backoff. For large populations, use `--cost-threshold`.

**Windows CRLF warnings**
Normal and harmless. Git autocrlf setting.

**Calibration GPA gap**
SynthEd's assignment quality formula has a structural ceiling around GPA ~2.6. For institutions with mean GPA > 3.0, more Optuna trials (100+) or formula-level changes may be needed.
