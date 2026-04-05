# SynthEd Developer Wiki

SynthEd is a Python agent-based simulation for generating synthetic Open & Distance Learning (ODL) data, grounded in 11 educational and sociological theories.

This wiki documents the **internals** — what happens under the hood when you run the simulation, which theory modules affect which state variables, and what non-obvious behaviors to watch out for.

- **User-facing configuration** (CLI flags, JSON config, troubleshooting): see [GUIDE.md](../GUIDE.md)
- **Academic foundations** (theory citations, factor clusters, validation suite inventory): see [THEORY.md](../THEORY.md)
- **Quick start and project overview**: see [README.md](../../README.md)

---

## Reading Order

If you are new to the codebase, read these pages in order:

1. [Pipeline Walkthrough](pipeline-walkthrough.md) — what happens when you run `python run_pipeline.py`
2. [The Weekly Simulation Loop](simulation-loop.md) — Phase 1 (individual) and Phase 2 (social) mechanics
3. [Engagement Update Formula](engagement-formula.md) — the multi-theory engagement composer, term by term
4. [Theory Module Reference](theory-modules.md) — all 11 modules: what they read, write, and when they fire
5. [Dropout Mechanics](dropout-mechanics.md) — Baulke 6-phase model, unavoidable withdrawal, contagion
6. [Grading & GPA System](grading-and-gpa.md) — dual-track GPA, outcome classification, relative grading
7. [Calibration & Sensitivity Analysis](calibration-and-analysis.md) — Sobol, NSGA-II, CalibrationMap
8. [Data Export & OULAD](data-export.md) — 4-table standard export, 7-table OULAD export

---

## "I Want to Understand..."

| Question | Page |
|----------|------|
| What happens when I run `python run_pipeline.py --n 500`? | [Pipeline Walkthrough](pipeline-walkthrough.md) |
| How does the simulation decide what a student does each week? | [Simulation Loop](simulation-loop.md) |
| Why did this student's engagement drop at week 7? | [Engagement Formula](engagement-formula.md) |
| Which theory module writes `social_integration`? | [Theory Module Reference](theory-modules.md) |
| How does a student go from "enrolled" to "dropped out"? | [Dropout Mechanics](dropout-mechanics.md) |
| Why does `cumulative_gpa` differ from `perceived_mastery`? | [Grading & GPA](grading-and-gpa.md) |
| What is `CalibrationMap` and when do I re-measure it? | [Calibration & Analysis](calibration-and-analysis.md) |
| How does `--target-dropout 0.40 0.60` work? | [Pipeline Walkthrough](pipeline-walkthrough.md) + [Calibration & Analysis](calibration-and-analysis.md) |
| What columns are in the exported CSV files? | [Data Export & OULAD](data-export.md) |
| How does the OULAD 7-table format differ from standard export? | [Data Export & OULAD](data-export.md) |
| What is `scale_by()` and how does `InstitutionalConfig` work? | [Theory Module Reference](theory-modules.md) + [Engagement Formula](engagement-formula.md) |
| How do multi-semester simulations carry over state? | [Simulation Loop](simulation-loop.md) |

---

## Glossary

| Term | Definition |
|------|------------|
| `StudentPersona` | Immutable frozen dataclass representing a student's traits, demographics, and personality. Never mutated during simulation. Located in `synthed/agents/persona.py`. |
| `SimulationState` | Mutable dataclass tracking a student's evolving state (engagement, GPA, dropout phase, etc.) during simulation. Located in `synthed/simulation/engine.py`. |
| `EngineConfig` | Frozen dataclass holding all 70+ simulation engine constants (weights, thresholds, clip bounds). Override via `dataclasses.replace()`. Located in `synthed/simulation/engine_config.py`. |
| `ODLEnvironment` | Dataclass representing the semester structure: courses, weeks, scheduled events, positive events. Located in `synthed/simulation/environment.py`. |
| `Course` | Dataclass for a single course, including Moore transactional distance fields (`structure_level`, `dialogue_frequency`, `instructor_responsiveness`). Located in `synthed/simulation/environment.py`. |
| `PersonaConfig` | Frozen dataclass controlling population generation distributions (age ranges, employment rates, trait means). Located in `synthed/agents/persona.py`. |
| `InstitutionalConfig` | Frozen dataclass with 5 float parameters [0,1] representing institution-level quality. `scale_by()` modulates engine constants. Located in `synthed/simulation/institutional.py`. |
| `GradingConfig` | Frozen dataclass controlling assessment modes, component weights, pass/distinction thresholds, and grade floor. Located in `synthed/simulation/grading.py`. |
| `SynthEdPipeline` | End-to-end orchestrator: configure, generate, simulate, export, validate, report. Located in `synthed/pipeline.py`. |
| `SimulationEngine` | The core simulation engine running the two-phase weekly loop across all students. Located in `synthed/simulation/engine.py`. |
| `CalibrationMap` | Piecewise linear interpolation mapping target dropout rates to `dropout_base_rate` values. Located in `synthed/calibration.py`. |
| `InteractionRecord` | Dataclass for a single student interaction event (login, forum post, assignment, exam). Located in `synthed/simulation/engine.py`. |
| `CommunityOfInquiryState` | Per-student CoI state tracking social, cognitive, and teaching presence (Garrison et al., 2000). Located in `synthed/simulation/engine.py`. |
| `SDTNeedSatisfaction` | Per-student Self-Determination Theory needs: autonomy, competence, relatedness (Deci & Ryan, 1985). Located in `synthed/simulation/theories/sdt_motivation.py`. |
| `ExhaustionState` | Per-student exhaustion tracking (Gonzalez et al., 2025): `exhaustion_level` and `recovery_capacity`. Located in `synthed/simulation/theories/academic_exhaustion.py`. |
| `SocialNetwork` | Peer network with link formation, decay, and degree tracking (Epstein & Axtell, 1996). Located in `synthed/simulation/social_network.py`. |
| `MultiSemesterRunner` | Orchestrates sequential semester simulations with inter-semester carry-over. Only used when `n_semesters >= 2`. Located in `synthed/simulation/semester.py`. |
| `scale_by()` | Modulation function: `constant * (0.7 + 0.6 * inst_param)`. At `inst_param=0.5`, returns `constant` exactly. Located in `synthed/simulation/institutional.py`. |
| Dual-track GPA | `cumulative_gpa` (transcript, grade floor applied) vs. `perceived_mastery` (raw quality, no floor). Theory modules use `perceived_mastery` for dropout signals. |
| Baulke phases | 6-phase dropout progression: 0 (Baseline) through 5 (Final Decision = dropout). See [Dropout Mechanics](dropout-mechanics.md). |

---

## Gotchas

- **Do not mutate `StudentPersona`** — it is a frozen dataclass. Use `dataclasses.replace()` for any modifications (e.g., multi-semester carry-over).
- **`SimulationState.semester_grade` is raw [0,1]**, NOT floor-adjusted. The floor is applied during outcome classification in `_assign_outcomes`.
- **RNG determinism depends on interaction order** — the 5 interaction generators fire in a fixed order (logins, forum, assignment, live, exam) per course. Changing this order changes all downstream random draws.
- **`CALIBRATION_DATA` was measured with DEFAULT persona traits** — if you change `PersonaConfig` defaults or engine weights, the calibration data may be stale. Re-measure with `run_calibration.py`.
- **Student IDs are non-deterministic** — UUIDv7 embeds wall-clock time, so IDs change across runs even with the same seed.
- **File size rule** — all files (code and docs) should stay under 800 lines. Split if approaching.
