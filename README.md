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

Example validation output (17 tests across 9 theories):
```
Quality: B (Good) — 15/17 tests passed
  ✓ age_distribution (KS-test)
  ✓ gender_distribution (Chi-squared)
  ✓ employment_rate (Z-test)
  ✓ dropout_rate (Z-test)
  ✓ tinto_conscientiousness_dropout (expected negative)
  ✓ bandura_self_efficacy_engagement (expected positive)
  ✓ rovai_self_regulation_engagement (expected positive)
  ✓ bean_metzner_financial_stress_dropout (expected positive)
  ✓ tinto_goal_commitment_engagement (expected positive)
  ✓ moore_autonomy_engagement (expected positive)
  ✓ kember_cost_benefit_engagement (expected positive)
  ✓ garrison_coi_engagement (expected positive)
  ✓ epstein_network_degree_engagement (expected positive)
  ✓ sdt_intrinsic_vs_amotivation (intrinsic > amotivation)
  ✓ baulke_phase_distribution (decided phase proportion)
  ✓ engagement_trajectory_divergence (retained > dropout)
  ✓ dropout_negative_trend_rate (decline before dropout)
  ✓ k_anonymity
```

## Theoretical Foundations

SynthEd's persona attributes and simulation mechanics are grounded in nine established theoretical anchors from ODE dropout research, organized into four factor clusters based on Rovai's (2003) composite persistence model:

### Core Theoretical Anchors

| Anchor | Origin | Role in SynthEd |
|--------|--------|-----------------|
| **Tinto's Student Integration Model** (1975) | Sociology (Durkheim) | Academic & social integration drive `institutional_commitment` → `engagement`. Social integration is deliberately weighted lower in ODE context. |
| **Bean & Metzner's Non-Traditional Student Attrition Model** (1985) | Non-traditional students | Environmental factors (`financial_stress`, `weekly_work_hours`, `has_family_responsibilities`) are the **dominant** dropout predictors, outweighing social integration. |
| **Kember's Longitudinal Process Model** (1989) | Distance education | Centers social/academic integration and cost-benefit evaluation for distance learners. SynthEd operationalizes this as a dynamic `perceived_cost_benefit` that updates weekly based on academic outcomes — a simulation design decision extending Kember's conceptual framework. |
| **Transactional Distance Theory** (Moore, 1993) | Distance education | Course-level `structure_level` and `dialogue_frequency` interact with student `learner_autonomy` to produce transactional distance, which modulates engagement and feeds Kember's cost-benefit calculation. |
| **Self-Determination Theory** (Deci & Ryan, 1985) | Psychology | Intrinsic/extrinsic motivation and amotivation (`motivation_type`) as predictors of persistence and goal commitment. |
| **Community of Inquiry** (Garrison et al., 2000) | Online learning | Three presences (`social_presence`, `cognitive_presence`, `teaching_presence`) emerge from weekly interactions and co-evolve with Tinto's integration constructs. |
| **Rovai's Composite Persistence Model** (2003) | Online/distance learning | `digital_literacy`, `self_regulation`, `time_management`, and `institutional_support_access` as persistence factors specific to ODE. |
| **Bäulke et al. Phase-Oriented Dropout Model** | Psychology | Dropout modeled as a **phased process**: non-fit perception → thoughts of quitting → deliberation → information search → final decision. Tracked via `dropout_phase`. (Originally developed for general HE; adapted to ODE context in SynthEd.) |
| **Agent-Based Social Simulation** (Epstein & Axtell, 1996) | Computational social science | Methodological framework for bottom-up emergent social behavior. Students form peer networks through forum co-activity; peer influence creates engagement contagion and dropout cascades as emergent phenomena. |

### Factor Clusters (Rovai, 2003)

| Cluster | Attributes | Theoretical Source |
|---------|------------|-------------------|
| **Student Characteristics** | `personality` (Big Five), `goal_commitment`, `ode_beliefs`, `motivation_type` | Tinto, Kember, Costa & McCrae (1992), Deci & Ryan (1985) |
| **Student Skills / Needs** | `self_regulation`, `digital_literacy`, `time_management`, `learner_autonomy`, `academic_reading_writing`, `institutional_support_access` | Rovai (2003), Moore (1993), Bäulke et al. |
| **External Factors** | `is_employed`, `weekly_work_hours`, `financial_stress`, `has_family_responsibilities` | Bean & Metzner (1985), Economic Rationality |
| **Internal Factors** | `academic_integration`, `social_integration`, `self_efficacy` | Tinto (1975), Bandura (1997) |
| **Emergent Properties** | `social_presence`, `cognitive_presence`, `teaching_presence` | Garrison et al. (2000) |
| **Network Properties** | `network_degree`, peer influence, dropout contagion | Epstein & Axtell (1996) — emergent from agent co-activity |

### Key Design Decision: ODE ≠ Campus

Following Bean & Metzner's central insight, SynthEd explicitly **weights external/environmental factors higher than social integration** in the dropout risk formula. Social integration is capped at 0.80 and contributes only 4% to the engagement composite — reflecting the empirical reality that distance learners rarely build campus-based social bonds.

### Emergent Properties (ABSS)

Unlike the other theories which map to static persona attributes or individual simulation mechanics, Epstein & Axtell's ABSS framework produces **emergent collective phenomena**:

- **Dropout clustering**: Students connected by forum activity influence each other's engagement; when one begins withdrawing, neighbors are more likely to follow.
- **Social stratification**: Employed students with family responsibilities form fewer connections (Bean & Metzner prediction) and thus receive less peer support, creating a reinforcing disadvantage loop.
- **Teaching presence amplification**: In courses with high instructor dialogue, peer networks amplify the effect as students discuss instructor feedback.

## Project Structure

```
SynthEd/
├── synthed/
│   ├── agents/
│   │   ├── persona.py      # StudentPersona (4 factor clusters + Big Five + Moore autonomy)
│   │   └── factory.py      # Calibrated population with inter-attribute correlations
│   ├── simulation/
│   │   ├── environment.py   # ODL course structure with transactional distance params
│   │   ├── engine.py        # Theory-grounded week-by-week simulation (9 theories)
│   │   └── social_network.py # Peer network formation & influence (Epstein & Axtell)
│   ├── data_output/
│   │   └── exporter.py      # CSV dataset generation
│   ├── validation/
│   │   └── validator.py     # Theory-grounded statistical validation
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
