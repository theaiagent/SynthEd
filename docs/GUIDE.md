# SynthEd User Guide

Practical guide for generating synthetic ODL data, calibrating against institutional data, and validating output quality.

## Table of Contents

- [Installation](#-installation)
- [CLI Usage](#-cli-usage)
- [Python API](#-python-api)
- [Population Configuration](#-population-configuration)
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

## 🎯 Dropout Targeting

Instead of manually tuning `dropout_base_rate`, specify the desired range:

```python
pipeline = SynthEdPipeline(
    target_dropout_range=(0.30, 0.45),  # auto-calibrates
    seed=42,
)
report = pipeline.run(n_students=300)
```

| Semesters | Default Dropout Rate | Quality |
|-----------|---------------------|---------|
| 1 (14 weeks) | ~46% | A (Excellent) |
| 2 (28 weeks) | ~76% | B (Good) |
| 4 (56 weeks) | ~96% | B (Good) |

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

Pre-defined institutional contexts:

```python
pipeline = SynthEdPipeline.from_profile("high_dropout_developing")
report = pipeline.run(n_students=500)
```

| Profile | Scenario | Expected Dropout |
|---------|----------|-----------------|
| `high_dropout_developing` | Developing country ODL | 60-90% |
| `moderate_dropout_western` | Western university | 30-60% |
| `low_dropout_corporate` | Corporate training | 5-30% |
| `mega_university` | Mega university | 55-85% |

---

## 🔬 Calibration Pipeline

Three-phase pipeline for tuning SynthEd parameters against real data (e.g., OULAD).

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

Adds narrative backstories explaining *why* each student behaves the way they do:

```bash
export OPENAI_API_KEY="your-key"
python run_pipeline.py --n 100 --llm
```

- **Providers:** OpenAI, Ollama (`--base-url`), any OpenAI-compatible API
- **Cost control:** `--cost-threshold 2.0` prompts for confirmation
- **Cache:** 7-day TTL, 10K-entry LRU eviction
- **No simulation effect:** Backstories are for interpretation only

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

### Parameter Naming Convention

| Prefix | Target | Example |
|--------|--------|---------|
| `config.*` | PersonaConfig | `config.employment_rate` |
| `engine.*` | SimulationEngine | `engine._TINTO_DECAY_BASE` |
| `tinto.*` | TintoIntegration | `tinto._ACADEMIC_EROSION` |
| `bean.*` | BeanMetznerPressure | `bean._OVERWORK_PENALTY` |
| `baulke.*` | BaulkeDropoutPhase | `baulke._DECISION_RISK_MULTIPLIER` |
| `sdt.*` | SDTMotivationDynamics | `sdt._INTRINSIC_THRESHOLD` |
| `rovai.*` | RovaiPersistence | `rovai._FLOOR_SCALE` |
| `garrison.*` | GarrisonCoI | `garrison._SOCIAL_DECAY` |
| `gonzalez.*` | GonzalezExhaustion | `gonzalez._ENGAGEMENT_IMPACT` |
| `moore.*` | MooreTransactionalDistance | `moore._STRUCTURE_WEIGHT` |

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| `validate_range: employment_rate must be between 0.0 and 1.0` | Check PersonaConfig values |
| `Unknown PersonaConfig field` during Sobol | Check spelling or use `auto_bounds()` |
| Validation grade D | Use N=200+ for reliable results |
| LLM 429 rate limit | Automatic retry with backoff; use `--cost-threshold` |
| Windows CRLF warnings | Normal, harmless |
| GPA gap (~15%) | Assignment quality formula ceiling; use 100+ Optuna trials |
