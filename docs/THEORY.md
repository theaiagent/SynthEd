# SynthEd Theoretical Foundations & Architecture

## Table of Contents

- [Architecture](#-architecture)
- [Theoretical Anchors](#-theoretical-anchors)
- [Factor Clusters](#-factor-clusters)
- [Design Decision: ODE is not Campus](#-design-decision-ode-is-not-campus)
- [Emergent Properties](#-emergent-properties)
- [Institutional Quality](#-institutional-quality)
- [Grading and Outcome Classification](#-grading-and-outcome-classification)
- [Project Structure](#-project-structure)
- [Validation Suite](#-validation-suite)
- [Test Suite](#-test-suite)

---

## 🏗️ Architecture

```mermaid
flowchart TD
    CM["CalibrationMap\ntarget dropout range -> params"]
    BP["Benchmark Profiles / JSON Config"]
    IC["InstitutionalConfig\n5 quality parameters"]
    PC["PersonaConfig\nadjusted parameters"]

    CM --> PC
    BP --> PC

    SF["Student Factory\n4 clusters (Rovai 2003)\nBig Five, SDT, Bean & Metzner, Moore"]
    PC --> SF
    IC --> engine

    SF -->|"N students\nwith UUIDv7 id + display_id"| engine

    subgraph engine ["Simulation Engine -- 14 weeks x N semesters"]
        direction TB
        P1["Phase 1: Individual Behavior\nLMS logins (Rovai), Forum posts (Tinto)\nAssignments & exams, Live sessions\nCoI presences (Garrison), Engagement update"]
        UW["Unavoidable Withdrawal\nLife events: illness, relocation, death..."]
        GPA["GPA Computation\nCumulative 4.0-scale from assignments & exams"]
        P2["Phase 2: Social Network\nPeer influence & contagion\nBaulke 6-phase dropout decision"]
        P1 --> UW --> GPA --> P2
    end

    SN["Social Network\nEpstein & Axtell\nLink formation, decay, contagion"]
    P2 <--> SN

    engine --> EX

    subgraph EX ["Data Export"]
        direction LR
        E1["students.csv"]
        E2["interactions.csv"]
        E3["outcomes.csv"]
        E4["weekly_engagement.csv"]
    end

    EX --> VAL

    subgraph VAL ["Validation Suite -- 22-24 statistical tests"]
        direction LR
        V1["L1: Distributions"]
        V2["L2: Correlations"]
        V3["L3: Temporal"]
        V4["L4: Privacy"]
        V5["L5: Backstory"]
    end
```

---

## 📚 Theoretical Anchors

SynthEd's persona attributes and simulation mechanics are grounded in ten established theoretical frameworks from ODE dropout research:

| # | Anchor | Origin | Role in SynthEd |
|---|--------|--------|-----------------|
| 1 | **Tinto's Student Integration Model** (1975) | Sociology (Durkheim) | Academic & social integration drive engagement. Social integration weighted lower in ODE context. |
| 2 | **Bean & Metzner** (1985) | Non-traditional students | Environmental factors (work, family, finances) are the **dominant** dropout predictors in ODE. Includes stochastic unavoidable withdrawal events (illness, death, relocation) via Lazarus & Folkman's (1984) stress-coping framework. |
| 3 | **Kember's Process Model** (1989) | Distance education | Dynamic `perceived_cost_benefit` updated weekly based on academic outcomes. |
| 4 | **Moore's Transactional Distance** (1993) | Distance education | Course structure and dialogue interact with learner autonomy. |
| 5 | **Self-Determination Theory** (Deci & Ryan, 1985) | Psychology | Intrinsic/extrinsic motivation and amotivation predict persistence. |
| 6 | **Community of Inquiry** (Garrison et al., 2000) | Online learning | Three presences (social, cognitive, teaching) co-evolve with Tinto's integration. |
| 7 | **Rovai's Persistence Model** (2003) | Online/distance learning | Digital literacy, self-regulation, time management as ODE-specific factors. |
| 8 | **Baulke et al. Phase Model** (2022) | Psychology | 6-phase dropout process: non-fit perception -> thoughts -> deliberation -> info search -> decision. Phase thresholds modulated by `support_services_quality` via `scale_by()`. |
| 9 | **Epstein & Axtell ABSS** (1996) | Computational social science | Bottom-up emergent behavior: peer networks, engagement contagion, dropout cascades. |
| 10 | **Academic Exhaustion** (Gonzalez et al., 2025) | Psychology | Exhaustion as mediator between stressors and dropout risk. |

---

## 🧩 Factor Clusters

Organized using Rovai's (2003) composite persistence model:

| Cluster | Attributes | Source |
|---------|------------|--------|
| **Student Characteristics** | personality (Big Five), goal_commitment, ode_beliefs, motivation_type | Tinto, Kember, Costa & McCrae, Deci & Ryan |
| **Student Skills** | self_regulation, digital_literacy, time_management, learner_autonomy | Rovai, Moore, Baulke |
| **External Factors** | employment_intensity, family_responsibility_level, financial_stress | Bean & Metzner, Economic Rationality |
| **Internal Factors** | academic_integration, social_integration, self_efficacy | Tinto, Bandura |
| **Emergent Properties** | `social_presence`, `cognitive_presence`, `teaching_presence` (emergent; stored on `SimulationState.coi_state`, not on `StudentPersona`) | Garrison et al. |
| **Network Properties** | network_degree, peer influence, dropout contagion | Epstein & Axtell |

---

## ⚖️ Design Decision: ODE is not Campus

Following Bean & Metzner's central insight, SynthEd **weights external/environmental factors higher than social integration** in the dropout risk formula:

- Social integration is capped at 0.80 and contributes only 4% to engagement
- External factors (work, family, finances) contribute 30% to dropout risk
- This reflects empirical ODL research: distance learners rarely build campus-based social bonds

---

## 🌐 Emergent Properties

Unlike static persona-based theories, Epstein & Axtell's ABSS framework produces **emergent collective phenomena**:

- **Dropout clustering:** Connected students influence each other's engagement; one withdrawing increases neighbors' dropout risk.
- **Social stratification:** Employed students with families form fewer connections (Bean & Metzner prediction), creating a reinforcing disadvantage loop.
- **Teaching presence amplification:** High instructor dialogue courses see peer networks amplify the effect as students discuss feedback.

---

## 🏛️ Institutional Quality

Non-academic institutional factors are a major driver of student outcomes. Gonzalez et al. (2025) found that 86.4% of dropout variance is explained by non-academic mechanisms -- including institutional support, technology infrastructure, and course design quality. SynthEd captures this through five institution-level parameters in `InstitutionalConfig`:

| Parameter | Theoretical Grounding |
|-----------|----------------------|
| `instructional_design_quality` | Garrison CoI teaching presence, Moore structure |
| `teaching_presence_baseline` | Garrison CoI, Rovai persistence |
| `support_services_quality` | Bean & Metzner environmental factors |
| `technology_quality` | Moore transactional distance, Rovai digital access |
| `curriculum_flexibility` | Moore dialogue, Kember cost-benefit |

Each parameter ranges 0-1 with 0.5 as neutral. The `scale_by()` method applies multiplicative modulation to theory constants: values above 0.5 improve the constant (e.g., stronger teaching presence, lower transactional distance), while values below 0.5 degrade it. At 0.5 the modulation is identity -- theory constants remain unchanged, preserving backward compatibility with existing calibrations.

---

## 📊 Grading and Outcome Classification

SynthEd supports two grading methods via `GradingConfig`:

- **Absolute grading** (default): Students are classified against fixed thresholds (`pass_threshold`, `distinction_threshold`).
- **Relative grading** (`grading_method="relative"`): Applies t-score standardization across the cohort. Students are classified by their standing relative to peers rather than fixed thresholds. Automatically falls back to absolute grading for cohorts smaller than 2 or with zero or near-zero variance (std < 1e-9).

---

## 📁 Project Structure

```
SynthEd/
├── synthed/
│   ├── agents/
│   │   ├── persona.py          # StudentPersona, PersonaConfig, BigFiveTraits
│   │   ├── factory.py          # Calibrated population generation
│   │   ├── name_pools.py       # Culturally diverse name generation
│   │   └── backstory_templates.py  # 7 templates, 12 life events, 8 contexts
│   ├── simulation/
│   │   ├── engine.py            # Orchestrator (delegates to theories/)
│   │   ├── engine_config.py     # EngineConfig frozen dataclass (70 constants)
│   │   ├── grading.py           # GradingConfig + outcome classification
│   │   ├── state.py             # SimulationState + state management (extracted from engine)
│   │   ├── statistics.py        # summary_statistics (extracted from engine)
│   │   ├── environment.py       # ODL course structure + positive events
│   │   ├── social_network.py    # Peer network with link decay
│   │   ├── semester.py          # Multi-semester with carry-over
│   │   ├── institutional.py     # InstitutionalConfig (5 quality parameters)
│   │   └── theories/            # 10 theory modules + protocol.py (TheoryModule + auto-discovery)
│   ├── data_output/
│   │   ├── exporter.py          # CSV export (4 standard files)
│   │   ├── oulad_exporter.py    # OULAD-compatible 7-table export
│   │   └── oulad_mappings.py    # OULAD schema mappings
│   ├── validation/
│   │   ├── validator.py         # 22 statistical validation tests (default; up to 24 with backstory validation)
│   │   └── types.py             # ReferenceStatistics, ValidationResult
│   ├── analysis/
│   │   ├── sensitivity.py       # OAT parameter sweeps
│   │   ├── sobol_sensitivity.py # Sobol variance decomposition (68 params)
│   │   ├── trait_calibrator.py  # Optuna Bayesian optimization
│   │   ├── oulad_targets.py     # OULAD reference data extraction
│   │   ├── oulad_validator.py   # Held-out module validation
│   │   ├── auto_bounds.py       # Adaptive parameter bounds
│   │   ├── nsga2_calibrator.py  # NSGA-II multi-objective calibration
│   │   ├── pareto_utils.py      # Pareto front utilities
│   │   └── _sim_runner.py       # Shared simulation runner
│   ├── benchmarks/
│   │   ├── profiles.py          # Default benchmark profile
│   │   └── generator.py         # Benchmark dataset generator + report
│   ├── dashboard/
│   │   ├── __main__.py          # `python -m synthed.dashboard` entry point
│   │   ├── app.py               # Shiny for Python app (reactive UI, simulation runner)
│   │   ├── theme.py             # Dark/light theme color palette (WCAG AA contrast)
│   │   ├── charts.py            # Plotly chart builders (on-screen)
│   │   ├── config_bridge.py     # Frozen config dataclasses <-> reactive UI values
│   │   └── components/          # param_panel, distribution_editor, warnings, results_panel
│   ├── report/
│   │   ├── generator.py         # HTML/PDF report generator (optional deps: jinja2, playwright)
│   │   ├── charts.py            # Print-friendly chart builders (white bg, dark text)
│   │   ├── translations.py      # i18n strings (EN/TR)
│   │   └── templates/report.html
│   ├── utils/
│   │   ├── llm.py               # OpenAI wrapper with cache, cost, streaming
│   │   ├── llm_memory.py        # Immutable ConversationMemory
│   │   ├── log_config.py        # Logging configuration
│   │   └── validation.py        # Input validation utilities
│   ├── calibration.py           # CalibrationMap: target dropout -> params
│   ├── doc_facts.py             # Documentation consistency checker
│   ├── pipeline_config.py       # PipelineConfig frozen dataclass (16 params)
│   └── pipeline.py              # End-to-end orchestrator
├── tests/                       # 890 pytest tests across 49 files
├── docs/
│   ├── GUIDE.md                 # User guide
│   └── THEORY.md                # This file
├── oulad/                       # Real OULAD reference data — Kuzilek et al. (2017) doi:10.1038/sdata.2017.171
├── run_pipeline.py              # CLI entry point
└── README.md
```

---

## ✅ Validation Suite

22 statistical tests (default; up to 24 with backstory validation) across 5 levels:

| Level | Tests | Method |
|-------|-------|--------|
| **L1: Distributions** | age, gender, employment, GPA, dropout | KS-test, chi-squared, z-test, range check |
| **L2: Correlations** | conscientiousness-dropout, self-efficacy-engagement, self-regulation-engagement, financial-stress-dropout, goal-commitment-engagement, autonomy-engagement, CoI-engagement, network-engagement, cost-benefit-engagement, GPA-dropout, engagement-GPA, SDT motivation, Baulke phases | Point-biserial r, Pearson r, t-test |
| **L3: Temporal** | engagement divergence, negative trend, early attrition | Mean difference, proportion, timing |
| **L4: Privacy** | k-anonymity | Quasi-identifier grouping |
| **L5: Backstory** | non-empty rate, attribute relevance | Content checks (when LLM enabled) |

Quality grades: **A** (90%+), **B** (75%+), **C** (60%+), **D** (40%+), **F** (<40%).

---

## 🧪 Test Suite

890 pytest tests across 49 files:

<!-- BEGIN:test_inventory -->
| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_auto_bounds.py` | 20 | auto_bounds parameter generation |
| `test_backstory_templates.py` | 17 | backstory template selection and prompt building |
| `test_baulke_institutional.py` | 11 | Baulke institutional modulation via InstitutionalConfig. |
| `test_benchmarks.py` | 15 | benchmark profiles and generator |
| `test_calibration.py` | 11 | CalibrationMap interpolation and estimation |
| `test_coverage_boost.py` | 37 | boost coverage from 93% to 95%+. |
| `test_coverage_gaps.py` | 8 | close remaining coverage gaps |
| `test_dashboard.py` | 42 | SynthEd Dashboard config bridge, distribution normalization, and charts |
| `test_dashboard_a11y.py` | 5 | dashboard (audit P1-6/P1-7/P1-10/P3-2). |
| `test_dashboard_calibrate.py` | 40 | the Calibrate tab UI components (PR B scorecard) |
| `test_dashboard_nav.py` | 3 | the two-tab mode-split skeleton (PR A). |
| `test_dashboard_theme.py` | 7 | dashboard theme & layout fixes (v1.7.0). |
| `test_dual_track_gpa.py` | 12 | dual-track GPA: transcript GPA vs perceived mastery |
| `test_engine.py` | 12 | the SimulationEngine |
| `test_engine_config.py` | 19 | EngineConfig frozen dataclass |
| `test_engine_grading.py` | 14 | GradingConfig |
| `test_environment.py` | 7 | ODLEnvironment |
| `test_environmental_shocks.py` | 26 | Environmental Shocks (Bean & Metzner Phase 3 — stochastic life events) |
| `test_factory.py` | 26 | StudentFactory population generation |
| `test_gpa.py` | 9 | GPA/academic success computation |
| `test_grading.py` | 49 | GradingConfig and grading utilities |
| `test_institutional_config.py` | 15 | InstitutionalConfig validation, scale_by, defaults |
| `test_institutional_integration.py` | 5 | InstitutionalConfig wired into SimulationEngine |
| `test_llm_cache.py` | 9 | LLM cache TTL expiry and LRU eviction |
| `test_llm_client.py` | 28 | LLMClient with mocked OpenAI API |
| `test_llm_cost_warning.py` | 11 | LLM cost estimation and warning system |
| `test_llm_enrichment.py` | 12 | LLM enrichment feature: backstory generation, export, and error handling |
| `test_llm_memory.py` | 14 | ConversationMemory and LLM streaming |
| `test_name_pools.py` | 11 | name_pools module |
| `test_network_scaling.py` | 4 | network scaling: sampling, degree caps, backward compatibility |
| `test_nsga2_calibrator.py` | 25 | NSGA-II calibration, Pareto front, knee-point, parallel branch, profile-object signatures |
| `test_opportunity_cost.py` | 5 | Kember opportunity cost mechanism |
| `test_oulad_export.py` | 35 | OULAD-compatible export |
| `test_pareto_utils.py` | 19 | Pareto dominance, front extraction, utilities |
| `test_persona.py` | 27 | StudentPersona and BigFiveTraits |
| `test_pipeline_config.py` | 19 | PipelineConfig frozen dataclass |
| `test_pipeline_integration.py` | 28 | SynthEdPipeline |
| `test_report.py` | 11 | SynthEd report generation module |
| `test_semester.py` | 19 | MultiSemesterRunner carry-over and multi-semester logic |
| `test_sensitivity.py` | 2 | sensitivity analysis module |
| `test_sobol.py` | 48 | Sobol sensitivity analysis |
| `test_social_network.py` | 11 | SocialNetwork |
| `test_theories.py` | 29 | individual theory modules |
| `test_theory_protocol.py` | 32 | TheoryModule Protocol, TheoryContext, and auto-discovery |
| `test_trait_calibration.py` | 39 | OULAD target extraction and trait-based calibration |
| `test_unavoidable_withdrawal.py` | 9 | the UnavoidableWithdrawal theory module |
| `test_utils.py` | 14 | shared utility modules: validation and log_config |
| `test_validation_types.py` | 10 | synthed.validation.types dataclasses |
| `test_validator.py` | 9 | SyntheticDataValidator |
<!-- END:test_inventory -->

CI runs tests across **Python 3.10, 3.11, and 3.12** via [GitHub Actions](https://github.com/theaiagent/SynthEd/actions/workflows/ci.yml).
