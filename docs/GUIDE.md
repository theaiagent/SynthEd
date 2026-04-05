# SynthEd User Guide

Practical guide for generating synthetic ODL data, calibrating against institutional data, and validating output quality.

## Table of Contents

- [Installation](#-installation)
- [CLI Usage](#-cli-usage)
- [Python API](#-python-api)
- [Population Configuration](#-population-configuration)
- [Grading Configuration](#-grading-configuration)
- [Dropout Targeting](#-dropout-targeting)
- [Multi-Semester Simulation](#-multi-semester-simulation)
- [Benchmark Profiles](#-benchmark-profiles)
- [Calibration Pipeline](#-calibration-pipeline)
- [Custom Reference Data](#-custom-reference-data)
- [OULAD-Compatible Export](#-oulad-compatible-export)
- [LLM Enrichment](#-llm-enrichment)
- [Output Files](#-output-files)
- [Customization](#-customization)
- [Troubleshooting](#-troubleshooting)

---

## 📦 Installation

```bash
git clone https://github.com/theaiagent/SynthEd.git
cd SynthEd
pip install -e ".[dev]"

# Verify
python -c "import synthed; print('OK')"
```

**Requirements:** Python 3.10+, numpy, scipy, SALib, optuna.

---

## 🖥️ CLI Usage

```bash
# Default: 200 students, 14-week semester
python run_pipeline.py

# Custom population
python run_pipeline.py --n 500

# Target specific dropout range
python run_pipeline.py --n 300 --target-dropout 0.40 0.55

# OULAD-compatible 7-table export
python run_pipeline.py --n 300 --oulad

# With culturally diverse student names
python run_pipeline.py --n 200 --names

# Verbose logging
python run_pipeline.py --verbose
```

### With LLM Enrichment (Optional)

```bash
export OPENAI_API_KEY="your-key-here"
python run_pipeline.py --n 100 --llm --model gpt-4o-mini

# Local Ollama provider
python run_pipeline.py --n 100 --llm --base-url http://localhost:11434/v1

# Cost threshold ($2 max)
python run_pipeline.py --n 500 --llm --cost-threshold 2.0
```

---

## 🐍 Python API

```python
from synthed.pipeline import SynthEdPipeline

# Single semester
pipeline = SynthEdPipeline(output_dir="./output", seed=42)
report = pipeline.run(n_students=300)

print(f"Dropout: {report['simulation_summary']['dropout_rate']:.1%}")
print(f"GPA: {report['simulation_summary']['mean_final_gpa']:.2f}")
print(f"Quality: {report['validation']['summary']['overall_quality']}")
```

```python
# Target a specific dropout range
pipeline = SynthEdPipeline(
    output_dir="./targeted",
    seed=42,
    target_dropout_range=(0.40, 0.55),  # system auto-calibrates
)
report = pipeline.run(n_students=300)
```

---

## ⚙️ Population Configuration

`PersonaConfig` controls population-level demographics:

```python
from synthed.agents.persona import PersonaConfig

config = PersonaConfig(
    employment_rate=0.78,           # fraction employed (0-1)
    has_family_rate=0.52,           # family responsibilities
    financial_stress_mean=0.55,     # mean financial stress (0-1)
    prior_gpa_mean=2.3,             # mean prior GPA (0-4)
    digital_literacy_mean=0.50,     # mean digital literacy (0-1)
    self_regulation_mean=0.42,      # mean self-regulation (0-1)
    dropout_base_rate=0.80,         # base dropout risk scaling (0.01-1.0)
    disability_rate=0.10,           # fraction with disability (0-1)
)

pipeline = SynthEdPipeline(persona_config=config, seed=42)
report = pipeline.run(n_students=300)
```

### Matching Your Institution

| Your Data | SynthEd Parameter |
|-----------|-------------------|
| 65% students employed | `employment_rate=0.65` |
| Mean GPA 2.8 | `prior_gpa_mean=2.8` |
| 40% family responsibilities | `has_family_rate=0.40` |
| 8% disability rate | `disability_rate=0.08` |

---

## 🏛️ Institutional Configuration

`InstitutionalConfig` models 5 institution-level quality parameters that modulate theory constants via multiplicative scaling (identity at 0.5):

```python
from synthed.simulation.institutional import InstitutionalConfig

ic = InstitutionalConfig(
    instructional_design_quality=0.7,   # Course design clarity
    teaching_presence_baseline=0.6,     # Instructor presence
    support_services_quality=0.8,       # Tutoring, counseling
    technology_quality=0.9,             # LMS usability
    curriculum_flexibility=0.6,         # Course adaptability
)
pipeline = SynthEdPipeline(institutional_config=ic, seed=42)
report = pipeline.run(n_students=300)
```

All values range 0-1 (default 0.5 = neutral). Values above 0.5 improve student outcomes; below 0.5 degrade them.

---

## 📊 Grading Configuration

`GradingConfig` controls institution-level grading policy: grade distribution, semester weighting, pass/fail thresholds, and outcome classification.

```python
from synthed.simulation.grading import GradingConfig, GradingScale

# Default: 100-point scale, 40/60 midterm/final, Beta(5,3)
config = GradingConfig()

# 4.0 GPA scale with piecewise conversion
config = GradingConfig(scale=GradingScale.SCALE_4)

# Corporate exam-only
config = GradingConfig(
    assessment_mode="exam_only",
    midterm_weight=0.0, final_weight=1.0,
    midterm_components={},
    pass_threshold=0.85,
)

# Use in pipeline
from synthed.pipeline import SynthEdPipeline
pipeline = SynthEdPipeline(grading_config=config)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scale` | `GradingScale.SCALE_100` | Grading scale (100-point or 4.0 GPA) |
| `distribution` | `"beta"` | Grade distribution: `"beta"`, `"normal"`, `"uniform"` |
| `midterm_weight` | `0.4` | Midterm contribution to semester grade |
| `final_weight` | `0.6` | Final exam contribution to semester grade |
| `pass_threshold` | `0.50` | Minimum transcript score to pass |
| `distinction_threshold` | `0.85` | Minimum transcript score for distinction |
| `grade_floor` | `0.45` | Floor applied to transcript GPA (not perceived mastery) |
| `assessment_mode` | `"continuous"` | `"continuous"` (midterm+final) or `"exam_only"` |

**Notes:**
- `grade_floor` affects transcript GPA and outcome classification only. Theory modules (Kember, SDT, Baulke) use `perceived_mastery` (raw, no floor) for dropout signals.
- Sobol sensitivity analysis uses the `grading.*` prefix for GradingConfig parameters.
- GradingConfig is a frozen dataclass -- use `dataclasses.replace()` for overrides.

### Relative Grading (Curve-Based)

```python
# Relative grading (curve-based)
pipeline = SynthEdPipeline(
    grading_config=GradingConfig(grading_method="relative"),
    output_dir="./output", seed=42,
)
```

Relative mode applies t-score standardization across the cohort. Students are classified by their standing relative to peers rather than fixed thresholds. Falls back to absolute grading for cohorts smaller than 2 or with zero variance.

---

## 🎯 Dropout Targeting

Instead of manually tuning `dropout_base_rate`, specify the desired range:

```python
pipeline = SynthEdPipeline(
    target_dropout_range=(0.30, 0.45),  # auto-calibrates
    seed=42,
)
report = pipeline.run(n_students=300)
```

| Semesters | Default Dropout Rate (base=0.80) | Quality |
|-----------|----------------------------------|---------|
| 1 (14 weeks) | ~41% | A (Excellent) |
| 2 (28 weeks) | ~69% | B (Good) |
| 4 (56 weeks) | ~92% | B (Good) |

---

## 🔄 Multi-Semester Simulation

```python
pipeline = SynthEdPipeline(
    output_dir="./multi",
    seed=42,
    n_semesters=4,
)
report = pipeline.run(n_students=300)
```

**What carries over between semesters:**

| Carries Over | Resets |
|-------------|--------|
| Academic integration | Weekly engagement history |
| Social integration (decayed 20%) | Memory/event log |
| Engagement (with +0.05 recovery) | Missed assignments streak |
| Dropout phase (regressed by 1) | Dropout status |
| Cost-benefit (with +0.03 recovery) | Network links (decayed) |
| Prior GPA (60/40 blend with earned GPA) | |
| Coping factor (70% retained) | |
| Exhaustion (reduced 70%) | |

---

## 🏛️ Benchmark Profiles

Pre-defined institutional contexts with CLI support:

```bash
python run_pipeline.py --benchmark                                     # Default profile + report
python run_pipeline.py --benchmark --benchmark-profile default         # Single profile
```

```python
from synthed.pipeline import SynthEdPipeline

pipeline = SynthEdPipeline.from_profile("default")
report = pipeline.run(n_students=500)

# Generate comparison report
from synthed.benchmarks.generator import BenchmarkGenerator
gen = BenchmarkGenerator()
md = gen.generate_report(output_dir="./benchmarks")  # writes benchmark_report.md + benchmark_results.json
```

| Profile | Scenario | Expected Dropout |
|---------|----------|-----------------|
| `default` | Large-scale, diverse student population | 35-60% |

---

## 🔬 Calibration Pipeline

Four-phase pipeline for tuning SynthEd parameters against real data (e.g., OULAD).

### Phase 1: Sobol Sensitivity Analysis

Identifies which parameters most influence outcomes:

```python
from synthed.analysis.sobol_sensitivity import SobolAnalyzer

analyzer = SobolAnalyzer(n_students=200, seed=42)
results = analyzer.run(n_samples=128)

rankings = analyzer.rank(results[0], top_n=15)
for r in rankings:
    print(f"{r.rank:2d}. {r.parameter:<40s} ST={r.st:.4f}")
```

### Phase 2: Bayesian Optimization

Optimizes top parameters against reference data:

```python
from synthed.analysis.trait_calibrator import TraitCalibrator, select_top_parameters
from synthed.analysis.oulad_targets import extract_targets

targets = extract_targets("oulad/")
top_params = select_top_parameters(rankings, top_n=15)

calibrator = TraitCalibrator(targets=targets, n_students=200, parameters=top_params)
result = calibrator.run(n_trials=100)

print(f"Dropout: {result.target_dropout:.1%} -> {result.achieved_dropout:.1%}")
print(f"GPA: {result.target_gpa:.3f} -> {result.achieved_gpa:.3f}")
```

### Phase 3: Held-Out Validation

```python
from synthed.analysis.oulad_validator import validate_against_oulad

report = validate_against_oulad(
    calibrated_params=result.best_params,
    oulad_dir="oulad/",
    n_students=200,
)
print(f"Grade: {report.grade} ({report.passed_count}/{report.total_count})")
```

### Auto-Bounds: Adaptive Parameter Space

When you change `PersonaConfig` defaults, use `auto_bounds()` to generate matching bounds:

```python
from synthed.analysis.auto_bounds import auto_bounds

# Default config
params = auto_bounds()

# Custom config — bounds adapt automatically
my_config = PersonaConfig(employment_rate=0.95, prior_gpa_mean=3.5)
params = auto_bounds(config=my_config, margin=0.3)
```

| Parameter | Default | Effect |
|-----------|---------|--------|
| `margin` | 0.5 | Variation range (0.5 = +/-50%) |
| `include_config` | True | Include PersonaConfig fields |
| `include_engine` | True | Include engine constants |
| `include_theories` | True | Include theory module constants |
| `exclude` | `frozenset()` | Specific parameters to skip |

### Phase 4: NSGA-II Multi-Objective Calibration

When dropout and GPA objectives conflict, NSGA-II explores the Pareto front instead of collapsing to a single weighted loss:

```python
from synthed.analysis.nsga2_calibrator import NSGAIICalibrator

calibrator = NSGAIICalibrator(n_students=100, seed=42, n_workers=4)
result = calibrator.run("default", n_trials=12800)
print(f"Pareto front: {len(result.pareto_front)} solutions")
print(f"Knee-point dropout error: {result.knee_point.dropout_error:.4f}")
```

The knee-point solution balances both objectives and is recommended as the default starting point for further tuning.

---

## 📊 Custom Reference Data

You don't need OULAD. Create targets from your own data:

```python
from synthed.analysis.oulad_targets import OuladTargets

my_targets = OuladTargets(
    overall_dropout_rate=0.25,
    module_dropout_rates={"CS101": 0.30, "MATH201": 0.20},
    score_mean=72.0, score_std=15.0, score_median=75.0,
    gpa_mean=2.88, gpa_std=0.60,
    engagement_mean=25.0, engagement_std=12.0,
    engagement_median=22.0, engagement_cv=0.48,
    disability_rate=0.08, gender_male_rate=0.45,
    n_students=5000,
)

calibrator = TraitCalibrator(targets=my_targets, n_students=200)
result = calibrator.run(n_trials=100)
```

**Note:** SynthEd engagement (0-1 probability) and institutional engagement (clicks, logins) use different scales. The calibrator uses coefficient of variation (CV = std/mean) for scale-independent comparison.

---

## 📁 OULAD-Compatible Export

```bash
python run_pipeline.py --n 300 --oulad
```

Produces 7 CSV files in `output/oulad/` matching exact OULAD column names:

| File | Rows |
|------|------|
| `courses.csv` | 1 per course |
| `assessments.csv` | ~6 per course |
| `vle.csv` | ~5-6 per course |
| `studentInfo.csv` | 1 per student x course |
| `studentRegistration.csv` | 1 per student x course |
| `studentAssessment.csv` | Variable |
| `studentVle.csv` | Variable |

### Module Filter for Split Analysis

```python
from synthed.analysis.oulad_targets import extract_targets

targets_bbb = extract_targets("oulad/", modules={"BBB", "FFF"})
```

---

## 🤖 LLM Enrichment

Generates narrative backstories from each student's actual persona attributes (age, employment, financial stress, motivation, etc.) to explain *why* they behave the way they do:

```bash
export OPENAI_API_KEY="your-key"
python run_pipeline.py --n 100 --llm
```

- **Persona-grounded:** Backstories are generated *from* real persona attributes via `to_prompt_description()`, not randomly. A student with `financial_stress=0.8` and `is_employed=True` gets a backstory reflecting financial hardship and work-life balance.
- **Providers:** OpenAI, Ollama (`--base-url`), any OpenAI-compatible API
- **Cost control:** `--cost-threshold 2.0` prompts for confirmation
- **Cache:** 7-day TTL, 10K-entry LRU eviction
- **Current scope:** Backstories do not feed back into simulation mechanics. Dropout, engagement, and GPA are computed from persona attributes and theory modules. Future LLM-augmented mode will use backstories as agent context for generating forum posts and assignment text.

---

## 📂 Output Files

| File | Description | Key Columns |
|------|-------------|-------------|
| `students.csv` | Initial persona attributes | student_id, display_id, age, personality traits |
| `interactions.csv` | Timestamped LMS events | student_id, week, interaction_type, quality_score |
| `outcomes.csv` | Final results | student_id, has_dropped_out, final_gpa, final_engagement |
| `weekly_engagement.csv` | Time series | student_id, week-by-week scores |
| `pipeline_report.json` | Full metadata + validation | |

---

## 🔧 Customization

### Custom Institution Profile (JSON)

```json
{
  "persona_config": {
    "age_range": [22, 60],
    "employment_rate": 0.80,
    "dropout_base_rate": 0.75
  },
  "reference_statistics": {
    "age_mean": 32.0,
    "dropout_rate": 0.43
  }
}
```

### Override Engine Constants

Engine constants are stored in a frozen `EngineConfig` dataclass. Overrides are applied internally via `dataclasses.replace()` with field-name validation — unknown fields are logged and ignored.

```python
from synthed.analysis._sim_runner import run_simulation_with_overrides
from synthed.agents.persona import PersonaConfig

metrics = run_simulation_with_overrides(
    overrides={
        "config.employment_rate": 0.90,
        "engine._TINTO_DECAY_BASE": 0.08,
        "bean._FINANCIAL_PENALTY": 0.025,
    },
    n_students=200, seed=42,
    default_config=PersonaConfig(),
)
```

You can also pass `EngineConfig` directly to the pipeline:

```python
from synthed.pipeline import SynthEdPipeline
from synthed.simulation.engine_config import EngineConfig
from dataclasses import replace

custom_cfg = replace(EngineConfig(), _TINTO_DECAY_BASE=0.08, _DECAY_DAMPING_FACTOR=0.7)
pipeline = SynthEdPipeline(engine_config=custom_cfg, output_dir="./output", seed=42)
```

### Parameter Naming Convention

| Prefix | Target | Example |
|--------|--------|---------|
| `config.*` | PersonaConfig | `config.employment_rate` |
| `engine.*` | EngineConfig | `engine._TINTO_DECAY_BASE` |
| `tinto.*` | TintoIntegration | `tinto._ACADEMIC_EROSION` |
| `bean.*` | BeanMetznerPressure | `bean._OVERWORK_PENALTY` |
| `baulke.*` | BaulkeDropoutPhase | `baulke._DECISION_RISK_MULTIPLIER` |
| `sdt.*` | SDTMotivationDynamics | `sdt._INTRINSIC_THRESHOLD` |
| `rovai.*` | RovaiPersistence | `rovai._FLOOR_SCALE` |
| `garrison.*` | GarrisonCoI | `garrison._SOCIAL_DECAY` |
| `gonzalez.*` | GonzalezExhaustion | `gonzalez._ENGAGEMENT_IMPACT` |
| `moore.*` | MooreTransactionalDistance | `moore._STRUCTURE_WEIGHT` |
| `inst.*` | InstitutionalConfig | `inst.technology_quality` |

---

## 🔍 Troubleshooting

> Find your error in the Quick Reference table, then jump to the detailed entry. Each entry follows the **Error-Context-Action** pattern.

### Quick Reference

| Error / Symptom | Jump to |
|---|---|
| `{name} must be between {lo} and {hi}` | [Range violation](#personaconfig-range-violation) |
| `{name} must sum to 1.0` | [Distribution sum](#distribution-does-not-sum-to-1) |
| `ModuleNotFoundError: No module named 'synthed'` | [Missing package](#missing-package) |
| `SyntaxError` on `X \| None` | [Python version](#python-version-mismatch) |
| Validation grade D or F | [Low validation grade](#low-validation-grade) |
| Dropout rate too low/high | [Dropout mismatch](#dropout-rate-outside-expectations) |
| `Unknown PersonaConfig field` | [Sobol typo](#unknown-parameter-in-sobol) |
| GPA gap (~15%) | [GPA convergence](#gpa-gap-in-calibration) |
| `auto_bounds()` returns empty | [Auto bounds edge case](#auto_bounds-returns-empty) |
| `openai.AuthenticationError` | [API key missing](#openai-api-key-missing) |
| `LLM enrichment blocked: cost exceeds threshold` | [Cost threshold](#llm-cost-threshold) |
| `base_url must use http or https scheme` | [Ollama URL](#ollama-base_url-validation) |
| `studentInfo.csv missing columns` | [OULAD columns](#oulad-csv-missing-columns) |
| Windows CRLF warnings | [CRLF warnings](#windows-crlf-warnings) |
| `ConstantInputWarning` from scipy | [Constant input](#constantinputwarning) |

### Prerequisites Checklist

- [ ] Python 3.10+: `python --version`
- [ ] Package installed: `pip install -e ".[dev]"`
- [ ] Dependencies OK: `python -c "import numpy, scipy, SALib, optuna; print('OK')"`
- [ ] (LLM only) `OPENAI_API_KEY` set
- [ ] (OULAD calibration only) OULAD CSV files present

---

### Installation

#### Missing package

**Error:**
```
ModuleNotFoundError: No module named 'synthed'
```

**Context:** Package not installed.

**Action:**
1. `cd SynthEd`
2. `pip install -e ".[dev]"`
3. Verify: `python -c "import synthed; print('OK')"`

#### Python version mismatch

**Error:**
```
SyntaxError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

**Context:** SynthEd requires Python 3.10+ for `X | None` union syntax.

**Action:**
1. `python --version` -- must be 3.10+
2. Upgrade Python if needed

---

### Configuration Errors

#### PersonaConfig range violation

**Error:**
```
ValueError: employment_rate must be between 0.0 and 1.0, got 1.5
```

**Context:** Any numeric PersonaConfig field outside its valid range.

**Action:** Check valid ranges:

| Field | Min | Max |
|---|---|---|
| `employment_rate` | 0.0 | 1.0 |
| `has_family_rate` | 0.0 | 1.0 |
| `financial_stress_mean` | 0.0 | 1.0 |
| `prior_gpa_mean` | 0.0 | 4.0 |
| `digital_literacy_mean` | 0.0 | 1.0 |
| `self_regulation_mean` | 0.0 | 1.0 |
| `dropout_base_rate` | 0.01 | 1.0 |
| `unavoidable_withdrawal_rate` | 0.0 | 0.05 |
| `disability_rate` | 0.0 | 1.0 |

#### Distribution does not sum to 1

**Error:**
```
ValueError: gender_distribution must sum to 1.0, got 0.9000
```

**Context:** Any categorical distribution (gender, motivation, socioeconomic, education, device, goal, learning style) must sum to 1.0 (tolerance: 0.01).

**Action:**
```python
config = PersonaConfig(
    gender_distribution={"male": 0.48, "female": 0.52},  # sums to 1.0
)
```

---

### Simulation Issues

#### Low validation grade

**Symptom:** `Quality: D (12/21 tests passed)`

**Context:** Population too small for reliable statistics, or PersonaConfig far from reference defaults.

**Action:**
1. Use N >= 200 (N=500 recommended)
2. If using custom config, provide matching `ReferenceStatistics`
3. Check `pipeline_report.json` for per-test details

> **Why:** With N < 100, stochastic variance dominates. The validator uses scale-adjusted alpha for N > 500 to prevent overpowered tests.

#### Dropout rate outside expectations

**Symptom:** Dropout rate diverges from target.

**Action:**
1. Use `target_dropout_range`: `python run_pipeline.py --target-dropout 0.40 0.60`
2. Too low? Increase `dropout_base_rate`
3. Too high? Decrease `dropout_base_rate` or increase `self_regulation_mean`
4. N < 100 → high variance between runs

> **Why:** `dropout_base_rate` is a scaling factor, not the literal rate. The `CalibrationMap` maps target rates to base rates via interpolation. Calibrated range: ~0.21 to ~0.46 for 1 semester.

---

### Calibration Issues

#### Unknown parameter in Sobol

**Error:**
```
ValueError: Unknown PersonaConfig field: 'emplyment_rate' in config.emplyment_rate
```

**Context:** Typo in custom `SobolParameter` name. Caught at setup time before simulations run.

**Action:**
1. Fix the spelling, or
2. Use `auto_bounds()` for auto-generated valid parameters

#### GPA gap in calibration

**Symptom:** `target_gpa=3.03, achieved_gpa=2.77` (~8.6% gap)

**Context:** Assignment/exam quality formula interacts with Optuna's composite loss. Too many trials causes over-optimization of dropout at GPA's expense.

**Action:**
1. Use 60-80 Optuna trials (sweet spot). More trials (120+) can degrade GPA.
2. Increase `gpa_weight` relative to `dropout_weight` if GPA is priority.
3. Best observed: 80 trials → GPA 2.77 (8.6% error), Score 70.1 (8.6%), Loss 0.0036.

| Trials | Loss | GPA | GPA Error | Grade |
|--------|------|-----|-----------|-------|
| 30 | 0.0319 | 2.19 | 27% | — |
| 60 | 0.0084 | 2.56 | 15% | B |
| **80** | **0.0036** | **2.77** | **8.6%** | **B** |
| 120 | 0.0168 | 2.32 | 23% | D |

#### auto_bounds returns empty

**Symptom:** `len(auto_bounds(margin=0.01))` returns 0.

**Context:** Very small margin collapses bounds to `lower >= upper` after clipping.

**Action:** Use larger margin: `auto_bounds(margin=0.5)` (default)

---

### LLM Issues

#### OpenAI API key missing

**Error:**
```
openai.AuthenticationError: No API key provided.
```

**Action:**
```bash
export OPENAI_API_KEY="sk-..."
# For Ollama (any non-empty string works):
export OPENAI_API_KEY="not-needed"
python run_pipeline.py --llm --base-url http://localhost:11434/v1
```

#### LLM cost threshold

**Error:**
```
LLM enrichment blocked: cost $1.25 exceeds threshold $1.00
```

**Action:**
1. CLI: `--cost-threshold 5.0`
2. Python: `SynthEdPipeline(cost_threshold=5.0, confirm_callback=lambda _: True)`
3. Use cheaper model: `--model gpt-4o-mini`

#### Ollama base_url validation

**Error:**
```
ValueError: base_url must use http or https scheme
```

**Action:** Use correct format: `--base-url http://localhost:11434/v1`

---

### Export Issues

#### OULAD CSV missing columns

**Error:**
```
ValueError: studentInfo.csv missing columns: {'final_result', 'disability'}
```

**Context:** OULAD CSV files must contain specific columns for calibration target extraction.

**Action:**
1. Download official OULAD dataset: [Kuzilek et al. (2017)](https://doi.org/10.1038/sdata.2017.171)
2. Required columns in `studentInfo.csv`: `final_result`, `code_module`, `gender`, `disability`
3. Required columns in `studentAssessment.csv`: `score`

---

### Runtime Warnings

#### Windows CRLF warnings

```
warning: LF will be replaced by CRLF
```

Harmless. Suppress with: `git config core.autocrlf true`

#### ConstantInputWarning

```
ConstantInputWarning: An input array is constant
```

Appears with small populations where all students share a trait value. Use N >= 200 for sufficient variance.

#### Student IDs differ between runs

UUIDv7 embeds wall-clock time. Same seed at different times produces different IDs. Use `display_id` (S-0001) for stable identifiers. Simulation state is deterministic.

#### Calibration data staleness

`CALIBRATION_DATA` in `calibration.py` was measured 2026-03-31. Re-measure if you modify theory modules or engine weights (N=500, 5 seeds per point).

---

## ⚖️ Legal Disclaimer

> **SynthEd is under active development and is for research and simulation purposes only.**

SynthEd generates **entirely fictional synthetic data**. No real individuals are represented, modeled, or identifiable in any output. The generated personas, interaction logs, and behavioral trajectories are computational artifacts produced by agent-based simulation grounded in published educational theories.

**By using SynthEd, you acknowledge that:**

- You are **fully responsible** for any use you make of the generated outputs.
- Synthetic data should **not** be presented as real student data without clear disclosure.
- The simulation reflects theoretical models, not empirical observations of specific institutions or populations.
- Outputs are intended for **research, development, and educational purposes** -- not for making decisions about real individuals.
- SynthEd is **under active development** (pre-release). APIs, default parameters, and output formats may change between versions without prior notice.
- As with any actively developed software, **bugs, inaccuracies, or incomplete features may exist**. Generated data should be independently validated before use in publications or critical research decisions.
- If using the optional LLM enrichment feature, you are responsible for compliance with the LLM provider's terms of service and content policies.

## 🤝 Responsible Use

SynthEd is designed to **address** ethical challenges in educational data mining, not create them:

- **Privacy by design**: Synthetic agents have no mapping to real individuals, eliminating re-identification risk.
- **Bias awareness**: The simulation parameters (demographics, employment rates, dropout thresholds) reflect configurable assumptions. Users should critically evaluate whether default parameters are appropriate for their research context.
- **Transparency**: All theoretical frameworks, formulas, and calibration decisions are documented in the source code and this documentation. The simulation is fully auditable.
- **No surveillance**: SynthEd is not designed for, and should not be used for, monitoring or evaluating real students.

## 🙏 Acknowledgments

This project is conceptually inspired by:
- [TinyTroupe](https://github.com/microsoft/tinytroupe) (Microsoft) -- Persona-based multi-agent simulation
- [MiroFish](https://github.com/666ghj/MiroFish) -- Scalable agent-based prediction engine with GraphRAG
- [Agent Lightning](https://github.com/microsoft/agent-lightning) -- RL-based agent optimization framework

OULAD reference data: [Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). Open University Learning Analytics Dataset. *Scientific Data*, 4, 170171.](https://doi.org/10.1038/sdata.2017.171)
