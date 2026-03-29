# SynthEd

**Agent-Based Synthetic Educational Data Generation for Open & Distance Learning Research**

SynthEd generates behaviorally coherent synthetic student data by combining **persona-driven agent modeling** (inspired by [TinyTroupe](https://github.com/microsoft/tinytroupe)) with **scalable multi-agent simulation** (inspired by [MiroFish](https://github.com/666ghj/MiroFish)). Unlike traditional synthetic data methods (GANs, VAEs), SynthEd produces temporally consistent interaction traces where each data point is grounded in a simulated student's personality, motivation, and life context.

## Why SynthEd?

Educational data mining research faces three persistent challenges:

| Challenge | Traditional Approach | SynthEd Approach |
|-----------|---------------------|-----------------|
| **Privacy regulations** (GDPR/KVKK) restrict access to real student data | Anonymization (risk of re-identification) | Agents are fictional — no real individuals involved |
| **Class imbalance** — dropout events are rare | Oversampling (SMOTE) — loses behavioral context | Parameter-level control of dropout rates |
| **Temporal incoherence** — GAN/VAE outputs lack behavioral consistency | Post-hoc smoothing | Persona + memory system produces coherent trajectories |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    SynthEd Pipeline                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  Student     │───▶│  Simulation  │───▶│   Data     │  │
│  │  Factory     │    │  Engine      │    │   Export   │  │
│  │              │    │              │    │            │  │
│  │ Big Five     │    │ Week-by-week │    │ students   │  │
│  │ Demographics │    │ LMS logins   │    │ .csv       │  │
│  │ Motivation   │    │ Forum posts  │    │ interact.  │  │
│  │ Self-efficacy│    │ Assignments  │    │ .csv       │  │
│  │ Employment   │    │ Exams        │    │ outcomes   │  │
│  │ ...          │    │ Dropout      │    │ .csv       │  │
│  └─────────────┘    └──────────────┘    └────────────┘  │
│         │                                     │          │
│         │          ┌──────────────┐            │          │
│         └─────────▶│  Validation  │◀───────────┘          │
│                    │  Suite       │                       │
│                    │              │                       │
│                    │ KS-test      │                       │
│                    │ Chi-squared  │                       │
│                    │ Correlations │                       │
│                    │ Temporal     │                       │
│                    │ k-Anonymity  │                       │
│                    └──────────────┘                       │
└──────────────────────────────────────────────────────────┘
```

## Key Features

- **Persona-Driven Agents**: Each student has Big Five personality traits, motivation type (SDT), self-efficacy, employment status, family responsibilities, and digital literacy — all influencing simulated behavior.
- **Temporal Memory**: Agents accumulate experiences across weeks, creating realistic engagement trajectories (e.g., a failed midterm reduces subsequent engagement).
- **Configurable Populations**: Calibrate to your institution's demographics using aggregate statistics only (no individual data needed).
- **Multi-Level Validation**: Automatic statistical comparison against reference data using KS-tests, chi-squared tests, correlation checks, and temporal coherence analysis.
- **Optional LLM Enrichment**: Use GPT-4o-mini to generate narrative backstories and richer behavioral nuance (off by default — zero API cost in rule-based mode).
- **Privacy by Design**: Synthetic agents are fictional constructs with no mapping to real individuals.

## Quick Start

### Installation

```bash
git clone https://github.com/theaiagent/SynthEd.git
cd SynthEd
pip install -r requirements.txt
```

### Generate Data (No API Key Needed)

```bash
# Default: 200 students, 14-week semester, rule-based simulation
python run_pipeline.py

# Custom population size
python run_pipeline.py --n 500

# With config file
python run_pipeline.py --config configs/default.json
```

### With LLM Enrichment (Optional)

```bash
export OPENAI_API_KEY="your-key-here"
python run_pipeline.py --n 100 --llm --model gpt-4o-mini
```

### Python API

```python
from synthed.pipeline import SynthEdPipeline

pipeline = SynthEdPipeline(output_dir="./my_output", seed=42)
report = pipeline.run(n_students=300)

print(f"Dropout rate: {report['simulation_summary']['dropout_rate']:.1%}")
print(f"Validation: {report['validation']['summary']['overall_quality']}")
```

## Output Datasets

| File | Description | Rows | Use Case |
|------|-------------|------|----------|
| `students.csv` | Demographics, Big Five, motivation, self-efficacy | 1 per student | Feature engineering, clustering |
| `interactions.csv` | Timestamped LMS events (logins, posts, submissions) | ~50-100 per student/week | Sequence modeling, engagement analysis |
| `outcomes.csv` | Dropout status, final engagement, trend | 1 per student | Classification, survival analysis |
| `weekly_engagement.csv` | Week-by-week engagement scores | 1 per student | Time series, early warning systems |
| `pipeline_report.json` | Full validation report and pipeline metadata | 1 | Quality assurance |

## Validation Suite

SynthEd validates generated data across four levels:

1. **Marginal Distributions** — KS-test for continuous variables, chi-squared for categorical
2. **Correlation Structure** — Verifies expected relationships (e.g., conscientiousness ↔ dropout)
3. **Temporal Coherence** — Dropout students should show declining engagement trajectories
4. **Privacy Assessment** — k-anonymity check on quasi-identifiers

Example validation output:
```
Quality: B (Good) — 7/9 tests passed
  ✓ age_distribution (KS-test, p=0.342)
  ✓ gender_distribution (Chi-squared, p=0.891)
  ✓ dropout_rate (Z-test, p=0.156)
  ✓ conscientiousness_dropout_correlation (r=-0.31)
  ✓ engagement_trajectory_divergence (retained > dropout)
  ✓ dropout_negative_trend_rate (78% show decline)
  ✓ k_anonymity (min k=3)
```

## Theoretical Foundations

SynthEd draws on established frameworks from educational psychology and distance learning research:

- **Self-Determination Theory** (Deci & Ryan, 2000) — Intrinsic/extrinsic motivation and amotivation as predictors of persistence
- **Big Five Personality Model** (Costa & McCrae, 1992) — Conscientiousness as the strongest personality predictor of academic outcomes
- **Transactional Distance Theory** (Moore, 1993) — Structure, dialogue, and learner autonomy in distance education
- **Community of Inquiry** (Garrison et al., 2000) — Social, cognitive, and teaching presence in online learning
- **Agent-Based Social Simulation** (Epstein & Axtell, 1996) — Bottom-up emergence of collective patterns from individual agent behaviors

## Project Structure

```
SynthEd/
├── synthed/
│   ├── agents/
│   │   ├── persona.py      # StudentPersona with Big Five traits
│   │   └── factory.py      # Calibrated population generation
│   ├── simulation/
│   │   ├── environment.py   # ODL course structure & events
│   │   └── engine.py        # Week-by-week behavioral simulation
│   ├── data_output/
│   │   └── exporter.py      # CSV dataset generation
│   ├── validation/
│   │   └── validator.py     # Multi-level statistical validation
│   ├── utils/
│   │   └── llm.py           # OpenAI wrapper with caching & cost tracking
│   └── pipeline.py          # End-to-end orchestrator
├── configs/
│   └── default.json         # Default configuration
├── run_pipeline.py           # CLI entry point
├── requirements.txt
└── README.md
```

## Customization

### Custom Institution Profile

Create a JSON config matching your institution's demographics:

```json
{
  "persona_config": {
    "age_range": [22, 60],
    "employment_rate": 0.80,
    "dropout_base_rate": 0.45
  },
  "reference_statistics": {
    "age_mean": 32.0,
    "dropout_rate": 0.45
  }
}
```

### Adding New Interaction Types

Extend `SimulationEngine._simulate_student_week()` to add new behavioral channels (e.g., mobile app usage, tutoring sessions).

## Roadmap

- [ ] **GraphRAG Integration** — Knowledge graph-based curriculum modeling (MiroFish-inspired)
- [ ] **LLM-Augmented Mode** — Generate realistic forum posts, assignment text
- [ ] **RL Calibration** — Use [Agent Lightning](https://github.com/microsoft/agent-lightning) to optimize agent parameters against real data
- [ ] **Interactive Dashboard** — Vue.js frontend for scenario exploration
- [ ] **Parquet/Arrow Export** — For large-scale data processing
- [ ] **Benchmark Datasets** — Pre-generated datasets for research community

## Citation

If you use SynthEd in your research, please cite:

```bibtex
@software{synthed2026,
  author = {Gençkaptan, Aykut},
  title = {SynthEd: Agent-Based Synthetic Educational Data Generation for ODL Research},
  year = {2026},
  url = {https://github.com/theaiagent/SynthEd}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

This project is conceptually inspired by:
- [TinyTroupe](https://github.com/microsoft/tinytroupe) (Microsoft) — Persona-based multi-agent simulation
- [MiroFish](https://github.com/666ghj/MiroFish) — Scalable agent-based prediction engine with GraphRAG
- [Agent Lightning](https://github.com/microsoft/agent-lightning) — RL-based agent optimization framework
