# SynthEd

[![CI](https://github.com/theaiagent/SynthEd/actions/workflows/ci.yml/badge.svg)](https://github.com/theaiagent/SynthEd/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests: 52 passed](https://img.shields.io/badge/tests-52%20passed-brightgreen.svg)](#test-suite)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Status: Active Development](https://img.shields.io/badge/status-active%20development-orange.svg)](https://github.com/theaiagent/SynthEd/releases)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19334118.svg)](https://doi.org/10.5281/zenodo.19334118)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Agent-Based Synthetic Educational Data Generation for Open & Distance Learning Research**

SynthEd generates behaviorally coherent synthetic student data by combining **persona-driven agent modeling** (inspired by [TinyTroupe](https://github.com/microsoft/tinytroupe)) with **scalable multi-agent simulation** (inspired by [MiroFish](https://github.com/666ghj/MiroFish)). Unlike traditional synthetic data methods (GANs, VAEs), SynthEd produces temporally consistent interaction traces where each data point is grounded in a simulated student's personality, motivation, and life context.

## Why SynthEd?

Educational data mining research faces three persistent challenges:

| Challenge | Traditional Approach | SynthEd Approach |
|-----------|---------------------|-----------------|
| **Privacy regulations** (GDPR/KVKK) restrict access to real student data | Anonymization (risk of re-identification) | Agents are fictional — no real individuals involved |
| **Class imbalance** — real dropout data is sensitive and often skewed | Oversampling (SMOTE) — loses behavioral context | Parameter-level control of dropout rates and population characteristics |
| **Temporal incoherence** — GAN/VAE outputs lack behavioral consistency | Post-hoc smoothing | Persona + memory system produces coherent trajectories |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       SynthEd Pipeline                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌───────────────────────┐   ┌───────────┐ │
│  │  Student      │───▶│   Simulation Engine   │──▶│   Data    │ │
│  │  Factory      │    │                       │   │   Export  │ │
│  │               │    │  Phase 1: Individual   │   │          │ │
│  │ 4 clusters    │    │  ├ LMS logins (Rovai) │   │ students │ │
│  │ (Rovai 2003)  │    │  ├ Forum posts (Tinto)│   │ .csv     │ │
│  │ Big Five      │    │  ├ Assignments        │   │ interact.│ │
│  │ SDT motivation│    │  ├ Live sessions      │   │ .csv     │ │
│  │ Bean & Metzner│    │  ├ CoI presences      │   │ outcomes │ │
│  │ Moore autonomy│    │  └ Engagement update  │   │ .csv     │ │
│  │ ...           │    │                       │   │ weekly   │ │
│  └──────────────┘    │  Phase 2: Social       │   │ .csv     │ │
│                       │  ├ Network formation  │   └───────────┘ │
│                       │  ├ Peer influence     │        │        │
│                       │  ├ Dropout contagion  │        │        │
│                       │  └ Bäulke 6-phase     │        │        │
│                       │    dropout decision   │        │        │
│                       └───────────────────────┘        │        │
│                                │                       │        │
│                       ┌────────┴───────┐               │        │
│                       │  Social Network│               │        │
│                       │  (Epstein &    │               │        │
│                       │   Axtell)      │               │        │
│                       └────────────────┘               │        │
│                                                        │        │
│              ┌──────────────────┐                       │        │
│              │  Validation Suite│◀──────────────────────┘        │
│              │  17+ validation  │                                │
│              │  tests           │                                │
│              │  ├ Distributions │                                │
│              │  ├ Correlations  │                                │
│              │  ├ Temporal      │                                │
│              │  └ Privacy       │                                │
│              └──────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

- **Persona-Driven Agents**: Each student has Big Five personality traits, motivation type (SDT), self-efficacy, employment status, family responsibilities, and digital literacy — all influencing simulated behavior.
- **Simulation Memory**: Each student's simulation state accumulates events across weeks (assignments, exams, phase transitions), creating realistic engagement trajectories (e.g., a failed midterm reduces subsequent engagement).
- **Configurable Populations**: Calibrate to your institution's demographics using aggregate statistics only (no individual data needed).
- **Multi-Level Validation**: Automatic statistical comparison against reference data using KS-tests, chi-squared tests, correlation checks, and temporal coherence analysis.
- **Optional LLM Enrichment**: Use GPT-4o-mini to generate narrative backstories with automatic retry, validation, and persona-attribute consistency checks (off by default — zero API cost in rule-based mode).
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

# Single semester (default)
pipeline = SynthEdPipeline(output_dir="./my_output", seed=42)
report = pipeline.run(n_students=300)

print(f"Dropout rate: {report['simulation_summary']['dropout_rate']:.1%}")
print(f"Validation: {report['validation']['summary']['overall_quality']}")
```

### Multi-Semester Simulation

```python
from synthed.pipeline import SynthEdPipeline

# 4 semesters with inter-semester carry-over
pipeline = SynthEdPipeline(output_dir="./multi_sem", seed=42, n_semesters=4)
report = pipeline.run(n_students=300)

# Carry-over between semesters: engagement recovery, social decay,
# dropout phase regression, exhaustion relief, network reset
```

## Output Datasets

| File | Description | Rows | Use Case |
|------|-------------|------|----------|
| `students.csv` | Initial/baseline persona attributes (Big Five, motivation, self-efficacy, etc.) | 1 per student | Feature engineering, clustering |
| `interactions.csv` | Timestamped LMS events (logins, posts, submissions) | ~50-100 per student/week | Sequence modeling, engagement analysis |
| `outcomes.csv` | Dropout status, final engagement, trend, CoI presences, network degree | 1 per student | Classification, survival analysis |
| `weekly_engagement.csv` | Week-by-week engagement scores | 1 per student | Time series, early warning systems |
| `pipeline_report.json` | Full validation report and pipeline metadata | 1 | Quality assurance |

## Validation Suite

SynthEd validates generated data across five levels:

1. **Marginal Distributions** — KS-test for continuous variables, chi-squared for categorical
2. **Correlation Structure** — Verifies expected relationships (e.g., conscientiousness ↔ dropout)
3. **Temporal Coherence** — Dropout students should show declining engagement trajectories
4. **Privacy Assessment** — k-anonymity check on quasi-identifiers
5. **Backstory Consistency** (optional) — LLM-generated backstories checked for non-empty rate and persona-attribute relevance

Example validation output (17 tests across 9 theoretical anchors):
```
Quality: A (Excellent) — 17/17 tests passed
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
| **Bäulke et al. Phase-Oriented Dropout Model** (2022) | Psychology | Dropout modeled as a **phased process**: non-fit perception → thoughts of quitting → deliberation → information search → final decision. Tracked via `dropout_phase`. (Originally developed for general HE; adapted to ODE context in SynthEd.) |
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
│   │   ├── persona.py          # StudentPersona, PersonaConfig, BigFiveTraits
│   │   └── factory.py          # Calibrated population generation
│   ├── simulation/
│   │   ├── engine.py            # Simulation orchestrator (delegates to theories/)
│   │   ├── environment.py       # ODL course structure + positive events
│   │   ├── social_network.py    # Peer network with link decay (Epstein & Axtell)
│   │   ├── semester.py          # Multi-semester runner with carry-over mechanics
│   │   └── theories/            # One module per theoretical framework
│   │       ├── tinto.py         # Academic/social integration (Tinto, 1975)
│   │       ├── bean_metzner.py  # Environmental pressure (Bean & Metzner, 1985)
│   │       ├── kember.py        # Cost-benefit + CoI link (Kember, 1989)
│   │       ├── moore_td.py      # Transactional distance (Moore, 1993)
│   │       ├── sdt_motivation.py # Dynamic motivation (Deci & Ryan, 1985)
│   │       ├── garrison_coi.py  # Community of Inquiry (Garrison et al., 2000)
│   │       ├── rovai.py         # Self-regulation + engagement floor (Rovai, 2003)
│   │       ├── baulke.py        # 6-phase dropout model (Bäulke et al., 2022)
│   │       ├── epstein_axtell.py # Peer influence + contagion
│   │       ├── positive_events.py # Positive environmental events
│   │       └── gonzalez_exhaustion.py # Academic exhaustion mediator
│   ├── data_output/
│   │   └── exporter.py          # CSV dataset generation
│   ├── validation/
│   │   └── validator.py         # 17+ statistical validation tests
│   ├── analysis/
│   │   └── sensitivity.py       # OAT parameter sensitivity analysis
│   ├── benchmarks/
│   │   ├── profiles.py          # Pre-defined ODL institutional profiles
│   │   └── generator.py         # Benchmark dataset generator
│   ├── utils/
│   │   ├── llm.py               # OpenAI wrapper with caching, retries & cost tracking
│   │   ├── log_config.py        # Logging configuration
│   │   └── validation.py        # Input validation utilities
│   └── pipeline.py              # End-to-end orchestrator
├── tests/                        # 52 pytest tests across 10 files
├── configs/
│   └── default.json
├── run_pipeline.py               # CLI entry point
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
    "dropout_base_rate": 0.75
  },
  "reference_statistics": {
    "age_mean": 32.0,
    "dropout_rate": 0.50
  }
}
```

### Adding New Interaction Types

Extend `SimulationEngine._simulate_student_week()` to add new behavioral channels (e.g., mobile app usage, tutoring sessions).

## Roadmap

- [x] **Multi-Semester Simulation** — Carry-over mechanics between semesters (engagement recovery, social decay, fresh start effect)
- [x] **Sensitivity Analysis** — OAT parameter sweeps to identify most impactful dropout predictors
- [x] **Benchmark Datasets** — Pre-generated profiles for different ODL contexts (developing, western, corporate, mega university)
- [x] **Academic Exhaustion** — Gonzalez et al. (2025) exhaustion mediator between stressors and dropout
- [ ] **OULAD-Compatible Export** — Generate data in Open University Learning Analytics Dataset format (7 tables) for drop-in compatibility with existing EDM research
- [ ] **GraphRAG Integration** — Knowledge graph-based curriculum modeling (MiroFish-inspired)
- [ ] **LLM-Augmented Mode** — Generate realistic forum posts, assignment text
- [ ] **RL Calibration** — Use [Agent Lightning](https://github.com/microsoft/agent-lightning) to optimize agent parameters against real data
- [ ] **Interactive Dashboard** — Vue.js frontend for scenario exploration
- [ ] **Parquet/Arrow Export** — For large-scale data processing

## Test Suite

SynthEd includes 52 pytest tests across 10 test files, covering all theory modules, simulation mechanics, LLM enrichment, and the full pipeline.

```bash
python -m pytest tests/ -v --tb=short
```

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_persona.py` | 7 | BigFive validation, engagement/dropout bounds, motivation comparison, dict roundtrip |
| `test_factory.py` | 4 | Population count, seed determinism, attribute ranges, summary keys |
| `test_engine.py` | 8 | Return types, state completeness, engagement bounds, dropout phases, risk cohort differentiation |
| `test_social_network.py` | 6 | Link creation/strengthening, degree counting, peer influence, link decay, statistics |
| `test_environment.py` | 4 | Default courses, exam week detection, positive events, course lookup |
| `test_validator.py` | 3 | Report structure, z-test symmetry, quality grade thresholds |
| `test_pipeline_integration.py` | 4 | Full pipeline run, output file creation, validation results, input rejection |
| `test_theories.py` | 9 | One test per theory module (Tinto, Bean-Metzner, Moore, Rovai, Garrison, Bäulke, Kember, SDT, Gonzalez) |
| `test_llm_enrichment.py` | 6 | Mock LLM enrichment, backstory export, error handling, invalid JSON, empty backstory rejection |

CI runs tests across **Python 3.10, 3.11, and 3.12** on every push and pull request via [GitHub Actions](https://github.com/theaiagent/SynthEd/actions/workflows/ci.yml).

## Legal Disclaimer

> **SynthEd is under active development and is for research and simulation purposes only.**

SynthEd generates **entirely fictional synthetic data**. No real individuals are represented, modeled, or identifiable in any output. The generated personas, interaction logs, and behavioral trajectories are computational artifacts produced by agent-based simulation grounded in published educational theories.

**By using SynthEd, you acknowledge that:**

- You are **fully responsible** for any use you make of the generated outputs.
- Synthetic data should **not** be presented as real student data without clear disclosure.
- The simulation reflects theoretical models, not empirical observations of specific institutions or populations.
- Outputs are intended for **research, development, and educational purposes** — not for making decisions about real individuals.
- SynthEd is **under active development** (pre-release). APIs, default parameters, and output formats may change between versions without prior notice.
- As with any actively developed software, **bugs, inaccuracies, or incomplete features may exist**. Generated data should be independently validated before use in publications or critical research decisions.
- If using the optional LLM enrichment feature, you are responsible for compliance with the LLM provider's terms of service and content policies.

## Responsible Use

SynthEd is designed to **address** ethical challenges in educational data mining, not create them:

- **Privacy by design**: Synthetic agents have no mapping to real individuals, eliminating re-identification risk.
- **Bias awareness**: The simulation parameters (demographics, employment rates, dropout thresholds) reflect configurable assumptions. Users should critically evaluate whether default parameters are appropriate for their research context.
- **Transparency**: All theoretical frameworks, formulas, and calibration decisions are documented in the source code and this README. The simulation is fully auditable.
- **No surveillance**: SynthEd is not designed for, and should not be used for, monitoring or evaluating real students.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributors

| Contributor | Role |
|-------------|------|
| [Halis Aykut Cosgun](https://github.com/theaiagent) | Project lead, system architecture, development, simulation design |
| [Evrim Genc Kumtepe](https://avesis.anadolu.edu.tr/egkumtepe) | Research advisor, theoretical framework design |
| [Claude](https://claude.ai) (Anthropic) | AI pair programmer — architecture, implementation, testing, code review |

## Citation

If you use SynthEd in your research, please cite:

```bibtex
@software{synthed2026,
  author = {Cosgun, Halis Aykut and Kumtepe Genc, Evrim},
  title = {SynthEd: Agent-Based Synthetic Educational Data Generation for ODL Research},
  year = {2026},
  url = {https://github.com/theaiagent/SynthEd},
  doi = {10.5281/zenodo.19334118}
}
```

## Acknowledgments

This project is conceptually inspired by:
- [TinyTroupe](https://github.com/microsoft/tinytroupe) (Microsoft) — Persona-based multi-agent simulation
- [MiroFish](https://github.com/666ghj/MiroFish) — Scalable agent-based prediction engine with GraphRAG
- [Agent Lightning](https://github.com/microsoft/agent-lightning) — RL-based agent optimization framework
