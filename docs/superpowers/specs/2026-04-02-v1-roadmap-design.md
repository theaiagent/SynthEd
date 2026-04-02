# SynthEd v1.0.0 Roadmap: GPA-Dropout Decoupling & Calibration

**Date:** 2026-04-02
**Status:** Draft
**Approach:** Bottom-Up (fix engine first, then calibrate)

---

## Problem Statement

After adding `_GRADE_FLOOR=0.45` (v0.6.4, PR #14), SynthEd's GPA accuracy improved to 3.3% error vs OULAD, but dropout rates compressed below literature values. The grade floor inflates GPA, which feeds into cost-benefit, competence beliefs, and Baulke phase thresholds -- suppressing dropout through 8 identified coupling pathways.

### Evidence

| Source | Dropout Rate |
|--------|-------------|
| OULAD Withdrawn (Kuzilek et al., 2017) | 31.2% |
| Developing country ODL literature | 50-70% |
| Western ODL literature | 20-45% |
| Corporate structured training | 5-25% |
| Mega university literature | 40-60%+ |
| SynthEd moderate_dropout_western | 31.4% (matches OULAD) |
| SynthEd high_dropout_developing | 58.2% (matches literature) |

Current profiles are literature-aligned after hybrid recalibration, but the engine structurally couples GPA and dropout, limiting the achievable parameter space.

---

## Design: 4-Phase Bottom-Up Approach

### Phase 1: Dual-Track GPA (v0.8.0)

**What:** Separate "transcript GPA" (grade floor applied, for export) from "perceived mastery" (raw quality, for internal dropout signals).

**Why:** The grade floor models institutional grading practices (templates, partial credit). But students know whether they actually understand the material. Bandura (1997) distinguishes objective performance from perceived competence. Rojstaczer & Healy (2012) document grade inflation diverging from actual learning.

**Zachman Analysis:**

| Dimension | Answer |
|-----------|--------|
| **What** (data) | New `perceived_mastery_sum`, `perceived_mastery_count` fields in SimulationState |
| **How** (process) | `_record_graded_item` stores both grade-floor GPA and raw quality separately |
| **Where** (location) | engine.py (state), kember.py, sdt_motivation.py, baulke.py (consumers) |
| **Who** (actors) | Theory modules that model student self-perception |
| **When** (timing) | Calculated at each graded item, consumed weekly in theory updates |
| **Why** (motivation) | Decouple institutional grading from student self-assessment to allow high GPA + high dropout |

**Changes:**

| File | Change |
|------|--------|
| `engine.py` | Add `perceived_mastery_sum`, `perceived_mastery_count` to SimulationState. In `_record_graded_item`, track raw quality alongside grade-floor GPA. |
| `kember.py` | GPA-based cost-benefit adjustment (line ~67) uses `perceived_mastery` instead of `cumulative_gpa`. |
| `sdt_motivation.py` | Competence GPA anchor (line ~112) uses `perceived_mastery`. |
| `baulke.py` | Non-fit GPA check (line ~100) and phase 4-5 trigger (line ~169) use `perceived_mastery`. |

**Expected outcome:** Transcript GPA stays realistic (~2.9). Perceived mastery centers at ~0.50 (pre-grade-floor behavior). Dropout signals recover their original sensitivity.

**Test impact:** Moderate. Tests checking GPA influence on dropout need updates. Transcript GPA tests unchanged.

---

### Phase 2: Opportunity Cost (v0.9.0)

**What:** Add GPA-independent opportunity cost term to Kember cost-benefit recalculation.

**Why:** Kember (1989) models cost-benefit as dynamic: perceived costs (time, money, family sacrifice, career opportunity loss) compete with benefits (credential, growth). Current implementation only models the benefit side through GPA. The cost side is static.

**Zachman Analysis:**

| Dimension | Answer |
|-----------|--------|
| **What** (data) | `_OPPORTUNITY_COST_FACTOR`, `_OPPORTUNITY_COST_THRESHOLD`, time-discount factor |
| **How** (process) | Weekly negative pressure when work_hours > threshold AND financial_stress > 0.5 |
| **Where** (location) | kember.py only |
| **Who** (actors) | Students with high employment + financial stress |
| **When** (timing) | Each weekly Kember recalculation; intensifies as semester progresses |
| **Why** (motivation) | GPA-independent path to low cost-benefit and dropout (Bean & Metzner theory support) |

**Changes:**

| File | Change |
|------|--------|
| `kember.py` | Add `_OPPORTUNITY_COST_FACTOR`, `_OPPORTUNITY_COST_THRESHOLD`. When `is_employed AND financial_stress > 0.5`, apply weekly negative cost-benefit pressure proportional to financial_stress. Add time-discount: `remaining_weeks / total_weeks` factor that erodes cost-benefit for fence-sitters as semester progresses. |

**Expected outcome:** Students with good grades but high life pressures can still drop out. Profile differentiation increases naturally (developing/mega profiles have higher employment + financial stress).

**Test impact:** Low. Additive mechanism; existing behavior preserved when conditions not met.

---

### Phase 3: Environmental Shocks (v0.10.0)

**What:** Time-varying stochastic life events (job loss, family crisis, financial emergency) that trigger dropout independent of academic performance.

**Why:** Bean & Metzner (1985) is the foundational theory for ODL dropout precisely because it argues external pressures dominate over academic factors for non-traditional students. OULAD data shows assignment non-submission -> 90% dropout (Hlosta et al., 2017), suggesting acute events cause sudden disengagement. Giordano et al. (2025) found 86.4% of dropout from non-academic mechanisms.

**Zachman Analysis:**

| Dimension | Answer |
|-----------|--------|
| **What** (data) | `environmental_shock_remaining: int`, `environmental_shock_magnitude: float` in SimulationState |
| **How** (process) | Each week: probability of shock scales with employment + family + financial_stress. Shock persists 1-3 weeks, adds engagement penalty. Severe shocks can advance Baulke phases directly. |
| **Where** (location) | bean_metzner.py (shock generation), engine.py (state + integration), baulke.py (phase jump trigger) |
| **Who** (actors) | Students with high external risk factors |
| **When** (timing) | Stochastic per-week events, more likely mid-semester (real-world pattern) |
| **Why** (motivation) | Model acute life events that cause dropout in students who are academically performing well |

**Changes:**

| File | Change |
|------|--------|
| `bean_metzner.py` | Add `stochastic_pressure_event()` method. Shock types: job_schedule_change, family_crisis, financial_emergency, health_issue. Probability per week: `base_prob * (employment * 0.3 + family * 0.3 + financial_stress * 0.4)`. |
| `engine.py` | Add shock fields to SimulationState. Call `stochastic_pressure_event` in `_update_engagement`. Apply shock magnitude as engagement penalty. |
| `baulke.py` | Severe shocks (magnitude > 0.7) can advance dropout phase by 1-2 steps regardless of engagement/GPA. |

**Expected outcome:** Dropout rates increase for high-risk profiles without affecting GPA. Module-level variance emerges naturally (shocks hit randomly, creating CCC-like vs GGG-like outcomes within the same profile).

**Test impact:** Low-moderate. New additive mechanism. May need seeded shock sequences for deterministic tests.

---

### Phase 4: NSGA-II Re-calibration (v0.11.0 -> v1.0.0)

**What:** Replace single-objective Optuna with multi-objective NSGA-II. Re-calibrate all profiles. Generate literature validation report.

**Why:** After Phases 1-3, the engine's parameter space has expanded. Single-objective weighted loss can't explore the full Pareto front of GPA-dropout trade-offs. NSGA-II (already available in Optuna as `NSGAIISampler`) finds all non-dominated solutions.

**Zachman Analysis:**

| Dimension | Answer |
|-----------|--------|
| **What** (data) | Pareto front: set of (GPA_error, dropout_error, engagement_error) non-dominated solutions |
| **How** (process) | `optuna.create_study(directions=["minimize", "minimize", "minimize"])` with NSGAIISampler |
| **Where** (location) | trait_calibrator.py, calibration.py, profiles.py |
| **Who** (actors) | Researcher running calibration pipeline |
| **When** (timing) | After all engine changes are complete and stable |
| **Why** (motivation) | Find optimal parameter configurations for each profile; prove GPA+dropout can be simultaneously achieved |

**Changes:**

| File | Change |
|------|--------|
| `trait_calibrator.py` | Replace `_combined_loss` with multi-objective study. Return Pareto front instead of single best. Add `select_balanced_solution()` to pick from front. |
| `calibration.py` | Re-measure CALIBRATION_DATA with updated engine (N=500, 5 seeds). |
| `profiles.py` | Update all profile parameters from NSGA-II optimal solutions. |
| `benchmarks/generator.py` | Generate final literature validation report comparing SynthEd vs published rates. |

**Expected outcome:** Each profile achieves both GPA accuracy (<5% error) and dropout accuracy (within literature range). Pareto front visualization shows trade-off landscape.

---

## Validation Strategy

Each phase includes:

1. **Unit tests** for new/modified theory modules
2. **Benchmark run** (4 profiles) to measure dropout + GPA shift
3. **Literature comparison** against the reference table above
4. **Regression check** — 477+ tests must pass, no existing behavior broken unintentionally

### Success Criteria for v1.0.0

| Metric | Target |
|--------|--------|
| GPA error vs OULAD | < 5% |
| All 4 profiles in expected dropout range | 4/4 |
| Validation suite quality | A or B for all profiles |
| Test count | 500+ |
| Pareto front demonstrates simultaneous GPA+dropout achievability | Yes |

---

## Dependencies & Risks

| Risk | Mitigation |
|------|-----------|
| Dual-Track GPA breaks many tests | Incremental: change one consumer at a time, test after each |
| Environmental shocks add non-determinism | Seed shock RNG from main simulation seed |
| NSGA-II finds GPA+dropout still conflicting | Pareto front will show exactly where the conflict is; environmental shocks should resolve it |
| Scope creep (course_difficulty, new profiles) | Deferred post-v1.0.0. Roadmap is strictly 4 phases. |

---

## Out of Scope (post v1.0.0)

- Course difficulty parameter in ODLEnvironment
- Turkey-specific open education profile
- GP Emulator / surrogate-accelerated calibration
- ABC (Approximate Bayesian Computation)
- Spectrum refactoring (binary -> continuous)
- PyPI publication

---

## References

- Bean & Metzner (1985) — Environmental factors in non-traditional student attrition
- Kember (1989) — Cost-benefit model of ODL persistence
- Bandura (1997) — Self-efficacy: perceived competence vs objective performance
- Rojstaczer & Healy (2012) — Grade inflation in higher education
- Giordano et al. (2025) — 86.4% of dropout from non-academic mechanisms (arXiv:2511.16243)
- Hlosta, Zdrahal & Zendulka (2017) — Assignment non-submission -> 90% dropout
- Read et al. (2016) — NSGA-II for ABM calibration (J. Royal Society Interface)
- Kuzilek et al. (2017) — OULAD dataset
- Al-Yahyai et al. (2025) — GPA < 2.0 -> 62% dropout (UAE STEM)
- Simpson (2023) — Online education deficit (IRRODL)
