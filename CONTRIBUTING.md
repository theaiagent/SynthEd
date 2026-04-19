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

The `core.hooksPath` step activates `.githooks/pre-commit`, which runs
`python -m synthed.doc_facts --fix` before every commit and restages
`docs/THEORY.md` if the test-count metrics drifted. Without it, the
`doc-health` CI job will fail on any change that adds or removes tests.

### Project Structure

See [docs/THEORY.md](docs/THEORY.md#-project-structure) for the full file layout.

Key directories:
- `synthed/simulation/theories/` -- one module per theoretical framework
- `synthed/analysis/` -- Sobol, Optuna, validation tools
- `synthed/validation/` -- statistical validation suite
- `tests/` -- pytest test files (one per source module)

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
3. Wire it into `SimulationEngine.__init__()` and the weekly loop
4. Add tests in `tests/test_theories.py`
5. Document in `docs/THEORY.md`

### Adding Benchmark Profiles

1. Define a new profile in `synthed/benchmarks/profiles.py`
2. Include `PersonaConfig`, `ODLEnvironment`, `ReferenceStatistics`, and expected dropout range
3. Add a test in `tests/test_benchmarks.py`

## Code Standards

- **Immutability**: Never mutate `StudentPersona`. Use `dataclasses.replace()`.
- **Named constants**: Use `_UPPERCASE` for all magic numbers.
- **Logging**: `logging.getLogger(__name__)`, never `print()`.
- **File size**: Max 800 lines per file.
- **Type hints**: Use `from __future__ import annotations` for modern syntax.
- **Lint**: `ruff check` with `--select E,F,W --ignore E501` must pass.
- **Tests**: Every new feature needs tests. Follow existing patterns.

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
3. All CI checks must pass (tests, lint, CodeQL, pipeline-smoke)
4. At least one maintainer review required
5. No merge conflicts with `main`

## Questions?

- Open an [Issue](https://github.com/theaiagent/SynthEd/issues)
- Check the [User Guide](docs/GUIDE.md) and [Troubleshooting](docs/GUIDE.md#-troubleshooting)
