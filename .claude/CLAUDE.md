# SynthEd — Project Instructions

> For project history, decisions, and context see [MEMORY.md](MEMORY.md)

## Quick Start

```bash
pip install -e ".[dev]"              # Dev install
python run_pipeline.py               # Default: 200 students, 14 weeks
python run_pipeline.py --n 500       # Custom population
python run_pipeline.py --llm         # LLM backstory enrichment (needs OPENAI_API_KEY)
```

```python
from synthed.pipeline import SynthEdPipeline
pipeline = SynthEdPipeline(output_dir="./output", seed=42)
report = pipeline.run(n_students=200)

# Multi-semester
pipeline = SynthEdPipeline(output_dir="./output", seed=42, n_semesters=4)
report = pipeline.run(n_students=200)
```

## Before Every Commit

```bash
ruff check synthed/ tests/ --select E,F,W --ignore E501
python -m pytest tests/ -q --tb=short
```

Both must pass before committing. No exceptions.

## Key Rules

- **Immutability**: Never mutate `StudentPersona`. Use `dataclasses.replace()`. SimulationState mutation is OK.
- **Theory modules**: Stateless classes, `_UPPERCASE` named constants. Follow `academic_exhaustion.py` pattern.
- **Imports**: Use `TYPE_CHECKING` to avoid circular imports in theory modules.
- **Version**: Auto-derived from git tags via `setuptools-scm`. Never hardcode.
- **Logging**: `logging.getLogger(__name__)`, never `print()`.
- **File size**: Max 800 lines. Extract if approaching.
- **Commits**: No severity labels (HIGH/MEDIUM/LOW) in commit messages or release notes.
- **Co-Authored-By**: All commits include `Co-Authored-By: Claude <81847+claude@users.noreply.github.com>`
- **Zenodo metadata**: `.zenodo.json` and `CITATION.cff` must exist in repo root with correct ORCID IDs and affiliations. Update if authors or affiliations change. After each release, manually set Programming Language=Python and Development Status=Active on Zenodo (these fields are not supported by `.zenodo.json`).
- **Release notes format**: Every GitHub release must start with the standard SynthEd description paragraph, then Authors with ORCID links, then What's New / What's Changed / Quality sections. Update `.zenodo.json` description with "Latest Release" changelog BEFORE creating git tag.
- **Branch workflow**: All changes via feature branches + PRs. No direct main commits. CI must pass before merge.

## Architecture

```
synthed/
├── agents/           # Persona + factory (population generation)
├── simulation/
│   ├── engine.py     # Orchestrator (delegates to theories/)
│   ├── theories/     # 11 modules, one per theoretical framework
│   ├── semester.py   # Multi-semester with carry-over
│   └── social_network.py  # Peer network (degree cap, link decay)
├── validation/       # 21 statistical tests (5 levels)
├── analysis/         # Sobol (SALib), Optuna calibrator, OULAD validator, auto_bounds, OAT
├── benchmarks/       # 4 institutional profiles
├── data_output/      # CSV export + OULAD 7-table export
├── utils/            # LLM wrapper, logging, validation helpers
└── pipeline.py       # End-to-end orchestrator
```

## Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Only with `--llm` | LLM backstory enrichment |

## Gotchas

- **Windows CRLF**: Git warnings normal, harmless
- **PersonaConfig validation**: Distributions must sum to 1.0
- **Rate limits**: LLM enrichment degrades gracefully (empty backstory)
- **Multi-semester RNG**: 4-semester ≠ 4× single-semester (RNG carries forward)
- **students.csv = initial values**: Final values in outcomes.csv
- **Engagement history**: Recorded AFTER peer influence (Phase 2)
- **Student IDs non-deterministic**: UUIDv7 embeds wall-clock time. Same seed at different times → different IDs. Simulation state is deterministic, IDs are not.
- **Calibration data staleness**: `CALIBRATION_DATA` in calibration.py was re-measured 2026-04-01 post grade-floor addition (N=500, 5 seeds). Re-measure if theory modules, engine weights, or RNG-consuming code paths change.
- **Grade floor**: `engine._GRADE_FLOOR=0.45` models baseline marks from templates, partial credit, and easy portions. Adjusting this shifts the entire GPA distribution — re-calibrate after changes.
