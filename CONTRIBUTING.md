# Contributing to SynthEd

Thank you for your interest in contributing to SynthEd! Whether you are a researcher, developer, or educator, your contributions are welcome.

## Getting Started

### Development Setup

```bash
git clone https://github.com/theaiagent/SynthEd.git
cd SynthEd
pip install -e ".[dev]"
git config core.hooksPath .githooks      # enable repo pre-commit hooks
python -m pytest tests/ -q --tb=short   # all tests must pass
```

CI installs `.[dev,llm,dashboard]` to exercise those optional integrations. The
HTML/PDF report tests additionally need `jinja2`, `plotly`, `playwright` and a
Playwright Chromium installation for full coverage; see the
[report setup](docs/GUIDE.md#optional-htmlpdf-reports). Missing optional packages
or browsers can skip tests, so report the passed and skipped counts separately.

The `core.hooksPath` step activates `.githooks/pre-commit`, which runs
`python -m synthed.doc_facts --fix` before every commit and restages the
doc_facts-managed files (`docs/THEORY.md`, `synthed/analysis/sobol_sensitivity.py`,
`.zenodo.json`) when they drift. Without it, the `doc-health` CI job will fail
on any change that adds or removes tests, or alters the Sobol parameter space.

The hook invokes `python -m synthed.doc_facts`, so the `synthed` package must
be importable — keep your dev venv activated (or re-run `pip install -e ".[dev]"`)
before committing, otherwise the hook errors with `ModuleNotFoundError`. If
python/python3 is missing from PATH entirely, the hook exits cleanly and leaves
sync to CI.

### Project Structure

See [docs/THEORY.md](docs/THEORY.md#-project-structure) for the project layout.

Key directories:
- `synthed/simulation/theories/` -- one module per theoretical framework
- `synthed/analysis/` -- Sobol, Optuna, validation tools
- `synthed/validation/` -- statistical validation suite
- `tests/` -- unit, integration and regression tests

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/theaiagent/SynthEd/issues) first
2. Use the **Bug Report** template
3. Include: Python version, OS, steps to reproduce, expected vs actual behavior
4. If possible, include the relevant section of `pipeline_report.json`

### Suggesting Features

1. Open an issue using the **Feature Request** template
2. Explain the use case and why it would benefit ODL research
3. Reference relevant theoretical frameworks if applicable

### Submitting Code

1. **Fork** the repository
2. Create a **feature branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
3. Make your changes following the [Code Standards](#code-standards)
4. Write tests (aim for 80%+ coverage on new code)
5. Ensure all checks pass:
   ```bash
   ruff check synthed/ tests/ --select E,F,W --ignore E501
   python -m pytest tests/ -q --tb=short
   python -m synthed.doc_facts
   ```
6. Commit with a descriptive message:
   ```bash
   git commit -m "feat: add your feature description"
   ```
7. Push and open a **Pull Request** against `main`

### Adding Theory Modules

SynthEd's simulation is built on pluggable theory modules. To add a new one:

1. Create `synthed/simulation/theories/your_theory.py`
2. Follow the existing pattern (see `academic_exhaustion.py` as a template):
   - Stateless class with `_UPPERCASE` named constants
   - Clear docstring citing the theoretical source
3. Implement the relevant protocol methods from `theories/protocol.py`. Phase-method classes with no-argument constructors are auto-discovered; `_PHASE_ORDER` controls their order. Engagement-only classes must be instantiated and included in the engagement dispatch list in `SimulationEngine.__init__()`, with `_ENGAGEMENT_ORDER`. See the [protocol guide](docs/GUIDE.md#theory-protocol-developer).
4. Add focused tests, including phase dispatch or engagement composition as applicable
5. Document in `docs/THEORY.md`

### Adding Benchmark Profiles

1. Define a new profile in `synthed/benchmarks/profiles.py`
2. Include `PersonaConfig`, `ODLEnvironment`, `ReferenceStatistics`, and expected dropout range
3. Add a test in `tests/test_benchmarks.py`

## Code Standards

- **Immutability**: Never mutate `StudentPersona`. Use `dataclasses.replace()`.
- **Named constants**: Use `_UPPERCASE` for all magic numbers.
- **Logging**: `logging.getLogger(__name__)`, never `print()`.
- **File size**: Soft limit around 1000 lines. Split when responsibilities diverge, rather than by line count alone.
- **Type hints**: Use `from __future__ import annotations` for modern syntax.
- **Lint**: `ruff check` with `--select E,F,W --ignore E501` must pass.
- **Tests**: Cover behavior changes with regression tests. Use multiple seeds for stochastic integration comparisons and report the aggregation used.
- **Versions**: Package versions are derived from Git tags with `setuptools-scm`; do not hardcode runtime versions.

## Commit Message Convention

```
<type>: <description>

Types: feat, fix, refactor, docs, test, chore, perf, ci
```

Examples:
- `feat: add parquet export support`
- `fix: correct GPA calculation for zero-credit students`
- `docs: update calibration guide with new trial analysis`

## Pull Request Process

1. PR title follows commit convention (`feat:`, `fix:`, etc.)
2. Description explains **what** and **why**
3. Update `CHANGELOG.md` under `[Unreleased]` and keep documentation consistent with the change
4. All CI checks must pass (tests, lint, doc-health, CodeQL, pipeline-smoke)
5. Complete independent Python and security reviews; changes to calibration or validation parameters also require statistical consistency review
6. Wait for CodeRabbit feedback and explicit maintainer approval before merging. A skipped bot review is not a completed review
7. Resolve merge conflicts with `main` and verify the resulting changes

Before creating a release tag, update the `.zenodo.json` description from the changelog and align `CITATION.cff` with the actual release version/date. Keep release history distinct from unreleased changes.

## Questions?

- Open an [Issue](https://github.com/theaiagent/SynthEd/issues)
- Check the [User Guide](docs/GUIDE.md) and [Troubleshooting](docs/GUIDE.md#-troubleshooting)
