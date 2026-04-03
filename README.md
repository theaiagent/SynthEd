# SynthEd: From synthetic data to simulated learners

[![Status: v1.0.0](https://img.shields.io/badge/status-v1.0.0-brightgreen.svg)](https://github.com/theaiagent/SynthEd/releases/tag/v1.0.0)
[![CI](https://github.com/theaiagent/SynthEd/actions/workflows/ci.yml/badge.svg)](https://github.com/theaiagent/SynthEd/actions/workflows/ci.yml)
[![pytest](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/theaiagent/cbf1abd6cdc2134e7e26374de286f2c9/raw/synthed-test-badge.json)](#test-suite)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/theaiagent/SynthEd/graph/badge.svg)](https://codecov.io/gh/theaiagent/SynthEd)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19334118.svg)](https://doi.org/10.5281/zenodo.19334118)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Agent-based simulation environment for Open & Distance Learning (ODL) research.** SynthEd generates behaviorally grounded and temporally coherent learning trajectories by combining persona-driven agent modeling with 11 established theoretical frameworks. Built for researchers in learning analytics, educational data mining, and dropout prediction.

```bash
pip install -e ".[dev]"
python run_pipeline.py --n 200
```

> **From statistical similarity to behavioral fidelity.** Traditional synthetic data methods optimize for distributional match. SynthEd optimizes for *behavioral coherence* -- each data point emerges from a simulated student's evolving motivations, decisions, and life context.

---

## Why SynthEd?

| Challenge | Traditional Approach | SynthEd Approach |
|-----------|---------------------|-----------------|
| **Privacy regulations** (GDPR/KVKK) | Anonymization (re-identification risk) | Agents are fictional -- no real individuals |
| **Class imbalance** in dropout data | Oversampling (SMOTE) -- loses context | Parameter-level control of dropout rates |
| **Temporal incoherence** | GAN/VAE post-hoc smoothing | Persona + memory produces coherent trajectories |

---

## Key Features

- **11 Theory Modules** -- Tinto, Bean & Metzner, Kember, SDT, Garrison CoI, Moore, Rovai, Baulke, Epstein & Axtell, Gonzalez, Unavoidable Withdrawal
- **Trait-Based Calibration** -- Sobol sensitivity (66 params) + Optuna Bayesian optimization against real OULAD data, validated Grade B on held-out modules
- **Multi-Semester Simulation** -- Carry-over mechanics for engagement, GPA, coping, dropout phases
- **GPA Feedback Loop** -- Cumulative GPA anchors cost-benefit, non-fit perception, and competence beliefs
- **OULAD-Compatible Export** -- 7-table CSV matching the Open University Learning Analytics Dataset schema
- **Adaptive Parameter Bounds** -- `auto_bounds()` adjusts calibration space when demographics change
- **5-Level Validation Suite** -- 21 statistical tests (distributions, correlations, temporal coherence, privacy, backstory)
- **Optional LLM Enrichment** -- Persona-grounded narrative backstories via OpenAI, Ollama, or any compatible provider
- **4 Benchmark Profiles** -- Developing, Western, Corporate, Mega University with CLI report generation
- **InstitutionalConfig** -- 5 institution-level quality parameters that modulate theory constants
- **GradingConfig** -- Configurable grading policy: Beta/Normal/Uniform grade distributions, weighted semester grades (midterm/final), dual-hurdle pass requirements, exam-only and continuous assessment modes, floor-adjusted transcript scale for outcome classification (Distinction/Pass/Fail)
- **NSGA-II Calibration** -- Multi-objective optimization with Pareto front exploration
- **565 Tests** -- 98% coverage, CI across Python 3.10/3.11/3.12

---

## Quick Start

```bash
git clone https://github.com/theaiagent/SynthEd.git
cd SynthEd
pip install -e ".[dev]"
python run_pipeline.py              # 200 students, 14 weeks
python run_pipeline.py --n 500      # Custom population
python run_pipeline.py --oulad      # OULAD-compatible export
python run_pipeline.py --benchmark  # Run all 4 benchmark profiles
```

```python
from synthed.pipeline import SynthEdPipeline

pipeline = SynthEdPipeline(output_dir="./output", seed=42)
report = pipeline.run(n_students=300)
print(f"Dropout: {report['simulation_summary']['dropout_rate']:.1%}")
```

---

## Use Cases

1. **Dropout Prediction** -- Generate labeled training data with known ground-truth trajectories
2. **Intervention Simulation** -- Model "what-if" scenarios by adjusting population parameters
3. **Privacy-Safe Benchmarking** -- Share synthetic datasets publicly for reproducible research

---

## Documentation

| Document | Content |
|----------|---------|
| **[User Guide](docs/GUIDE.md)** | Installation, configuration, calibration pipeline, OULAD export, LLM enrichment, troubleshooting |
| **[Theory & Architecture](docs/THEORY.md)** | 11 theoretical anchors, factor clusters, architecture diagram, project structure, validation suite, test inventory |

---

## Roadmap

- [x] Multi-semester simulation with carry-over
- [x] 11 theory modules (Tinto, Bean & Metzner, Kember, SDT, Garrison, Moore, Rovai, Baulke, Epstein & Axtell, Gonzalez, Unavoidable Withdrawal)
- [x] Trait-based calibration (Sobol + Optuna + OULAD validation)
- [x] Benchmark reports with CLI (`--benchmark`)
- [x] OULAD-compatible 7-table export
- [x] LLM enrichment with cost control and streaming
- [x] Disability severity (Beta distribution)
- [x] InstitutionalConfig (5 quality parameters modulating theory constants)
- [x] NSGA-II multi-objective calibration with Pareto front
- [ ] Spectrum refactoring (binary -> continuous for family/internet)
- [ ] GraphRAG integration (curriculum modeling)
- [ ] LLM-augmented mode (forum posts, assignment text)
- [ ] Parquet/Arrow export
- [ ] PyPI package publication
- [ ] Interactive dashboard

---

## Legal Disclaimer

> **SynthEd generates entirely fictional synthetic data.** No real individuals are represented or identifiable. Outputs are intended for research, development, and educational purposes. SynthEd is under active development -- APIs and output formats may change between versions.

See full [Legal Disclaimer](docs/GUIDE.md#%EF%B8%8F-legal-disclaimer) and [Responsible Use](docs/GUIDE.md#-responsible-use) guidelines.

---

## Contributing

Contributions welcome! See the [User Guide](docs/GUIDE.md) for development setup.

```bash
ruff check synthed/ tests/ --select E,F,W --ignore E501
python -m pytest tests/ -v --tb=short
```

---

## License

MIT License. See [LICENSE](LICENSE).

## Citation

If you use SynthEd in your research, please cite using the [CITATION.cff](CITATION.cff) file or the Zenodo DOI above.

## Contributors

| Contributor | Role |
|-------------|------|
| [Halis Aykut Cosgun](https://orcid.org/0000-0003-0166-6237) | Lead Developer, Data Scientist & AI Engineer, Researcher -- Yozgat Bozok University |
| [Evrim Genc Kumtepe](https://orcid.org/0000-0002-2568-8054) | Research Advisor -- Anadolu University |
| [Claude](https://claude.ai) (Anthropic) | AI pair programmer -- implementation, testing, code review |

## Acknowledgments

Conceptually inspired by [TinyTroupe](https://github.com/microsoft/tinytroupe) (Microsoft), [MiroFish](https://github.com/666ghj/MiroFish), and [Agent Lightning](https://github.com/microsoft/agent-lightning). OULAD reference data: [Kuzilek et al. (2017)](https://doi.org/10.1038/sdata.2017.171).
