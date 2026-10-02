"""
SynthEd Pipeline: End-to-end orchestrator for synthetic educational data generation.

Usage:
    from synthed.pipeline import SynthEdPipeline
    pipeline = SynthEdPipeline()
    report = pipeline.run(n_students=200)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import warnings

from . import __version__
from .agents.persona import PersonaConfig
from .agents.factory import StudentFactory
from .calibration import CalibrationMap
from .pipeline_config import PipelineConfig
from .simulation.environment import ODLEnvironment
from .simulation.engine import SimulationEngine
from .simulation.engine_config import EngineConfig
from .simulation.grading import GradingConfig
from .simulation.institutional import InstitutionalConfig
from .data_output.exporter import DataExporter
from .data_output.oulad_exporter import OuladExporter
from .validation import SyntheticDataValidator, ReferenceStatistics
from .utils.llm import LLMClient

logger = logging.getLogger(__name__)

_DEFAULT_COST_THRESHOLD_USD: float = 1.0

# Allowlist of legacy kwargs accepted by the deprecation bridge.
_LEGACY_PARAMS: frozenset[str] = frozenset({
    "persona_config", "environment", "institutional_config", "grading_config",
    "engine_config", "reference_stats", "seed", "n_semesters",
    "carry_over_config", "target_dropout_range", "output_dir", "export_oulad",
    "llm_model", "llm_base_url", "use_llm", "cost_threshold",
})


class SynthEdPipeline:
    """
    End-to-end pipeline for generating and validating synthetic ODL data.

    Pipeline stages:
    1. Configure → Set persona distributions, environment, and validation targets
    2. Generate  → Create student population using StudentFactory
    3. Simulate  → Run week-by-week behavioral simulation
    4. Export    → Write CSV datasets
    5. Validate  → Statistical comparison against reference data
    6. Report    → Produce quality assessment report
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        confirm_callback: Callable[[str], bool] | None = None,
        _calibration_mode: bool = False,
        **kwargs: Any,
    ):
        # ── Deprecation bridge ──────────────────────────────────────────
        if config is not None and kwargs:
            raise TypeError(
                "Cannot pass both 'config' and legacy keyword arguments. "
                "Use PipelineConfig for all configuration."
            )
        if kwargs:
            unknown = set(kwargs) - _LEGACY_PARAMS
            if unknown:
                raise TypeError(
                    f"Unknown keyword arguments: {unknown}. "
                    f"Valid legacy params: {sorted(_LEGACY_PARAMS)}"
                )
            warnings.warn(
                "Passing individual keyword arguments to SynthEdPipeline is "
                "deprecated. Use config=PipelineConfig(...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            config = PipelineConfig(
                persona_config=kwargs.get("persona_config") or PersonaConfig(),
                environment=kwargs.get("environment") or ODLEnvironment(),
                institutional_config=kwargs.get("institutional_config") or InstitutionalConfig(),
                grading_config=kwargs.get("grading_config") or GradingConfig(),
                engine_config=kwargs.get("engine_config") or EngineConfig(),
                reference_stats=kwargs.get("reference_stats") or ReferenceStatistics(),
                seed=kwargs.get("seed", 42),
                n_semesters=kwargs.get("n_semesters", 1),
                carry_over_config=kwargs.get("carry_over_config"),
                target_dropout_range=kwargs.get("target_dropout_range"),
                output_dir=kwargs.get("output_dir", "./output"),
                export_oulad=kwargs.get("export_oulad", False),
                llm_model=kwargs.get("llm_model", "gpt-4o-mini"),
                llm_base_url=kwargs.get("llm_base_url"),
                use_llm=kwargs.get("use_llm", False),
                cost_threshold=kwargs.get("cost_threshold", _DEFAULT_COST_THRESHOLD_USD),
            )
        elif config is None:
            config = PipelineConfig()

        # ── Non-serializable / internal args ────────────────────────────
        self.confirm_callback = confirm_callback
        self._calibration_mode = _calibration_mode
        self._calibration_estimate = None

        # ── Apply calibration (produces new config via replace) ─────────
        if config.target_dropout_range is not None:
            config = self._apply_calibration(config)

        # ── Store frozen config (single source of truth) ────────────────
        self.config = config

        # ── Initialize components from self.config ──────────────────────
        self.llm = (
            LLMClient(model=self.llm_model, base_url=self.llm_base_url)
            if self.use_llm else None
        )
        self.factory = StudentFactory(
            config=self.persona_config, llm_client=self.llm, seed=self.seed,
        )
        self.engine = SimulationEngine(
            environment=self.environment,
            llm_client=self.llm,
            seed=self.seed,
            unavoidable_withdrawal_rate=self.persona_config.unavoidable_withdrawal_rate,
            institutional_config=self.institutional_config,
            grading_config=self.grading_config,
            engine_config=self.engine_config,
        )
        self.exporter = DataExporter(
            output_dir=str(self.output_dir) if self.output_dir is not None else None,
        )
        self.validator = SyntheticDataValidator(reference=self.reference)

    # ── @property delegates to self.config ──────────────────────────────

    @property
    def persona_config(self) -> PersonaConfig:
        return self.config.persona_config

    @property
    def environment(self) -> ODLEnvironment:
        return self.config.environment

    @property
    def institutional_config(self) -> InstitutionalConfig:
        return self.config.institutional_config

    @property
    def grading_config(self) -> GradingConfig:
        return self.config.grading_config

    @property
    def engine_config(self) -> EngineConfig:
        return self.config.engine_config

    @property
    def reference(self) -> ReferenceStatistics:
        return self.config.reference_stats

    @property
    def seed(self) -> int:
        return self.config.seed

    @property
    def n_semesters(self) -> int:
        return self.config.n_semesters

    @property
    def carry_over_config(self) -> Any | None:
        return self.config.carry_over_config

    @property
    def target_dropout_range(self) -> tuple[float, float] | None:
        return self.config.target_dropout_range

    @property
    def output_dir(self) -> Path | None:
        od = self.config.output_dir
        return Path(od) if od is not None else None

    @property
    def export_oulad(self) -> bool:
        return self.config.export_oulad

    @property
    def use_llm(self) -> bool:
        return self.config.use_llm

    @property
    def llm_model(self) -> str:
        return self.config.llm_model

    @property
    def llm_base_url(self) -> str | None:
        return self.config.llm_base_url

    @property
    def cost_threshold(self) -> float:
        return self.config.cost_threshold

    def _apply_calibration(self, config: PipelineConfig) -> PipelineConfig:
        """Return a new PipelineConfig with calibrated dropout params."""
        calibration_map = CalibrationMap()
        estimate = calibration_map.estimate_from_range(
            config.target_dropout_range, config.n_semesters,
        )
        from .simulation.semester import SemesterCarryOverConfig

        defaults = PipelineConfig()
        self._calibration_reference_matches = (
            replace(config.persona_config, dropout_base_rate=defaults.persona_config.dropout_base_rate)
            == defaults.persona_config
            and all(getattr(config, name) == getattr(defaults, name) for name in (
                "environment", "institutional_config", "grading_config", "engine_config",
            ))
            and (config.n_semesters == 1 or
                 (config.carry_over_config or SemesterCarryOverConfig()) == SemesterCarryOverConfig())
        )
        if not self._calibration_reference_matches:
            estimate = replace(estimate, confidence="low")
            logger.warning(
                "Dropout targeting uses a default-model calibration curve, but "
                "the simulation configuration differs. Validate the transfer estimate "
                "across seeds or measure a curve for this configuration."
            )
        self._calibration_estimate = estimate

        midpoint = (config.target_dropout_range[0] + config.target_dropout_range[1]) / 2
        new_config = replace(
            config,
            persona_config=replace(
                config.persona_config,
                dropout_base_rate=estimate.estimated_dropout_base_rate,
            ),
            reference_stats=replace(
                config.reference_stats,
                dropout_rate=midpoint,
                dropout_range=config.target_dropout_range,
            ),
        )

        logger.info(
            "Calibration: targeting %s dropout, estimated base_rate=%.2f (confidence: %s)",
            config.target_dropout_range,
            estimate.estimated_dropout_base_rate,
            estimate.confidence,
        )
        return new_config

    def _check_cost_before_enrichment(self, n_students: int) -> bool:
        """Estimate LLM cost and warn/prompt if above threshold.

        Returns True if enrichment should proceed, False to skip.
        """
        if not self.llm:
            return True

        estimated = self.llm.estimate_cost(n_calls=n_students)
        if estimated <= self.cost_threshold:
            logger.info(
                "Estimated LLM cost: $%.4f (within threshold $%.2f)",
                estimated, self.cost_threshold,
            )
            return True

        warning = (
            f"Estimated LLM cost: ${estimated:.4f} exceeds threshold "
            f"${self.cost_threshold:.2f} ({n_students} students x {self.llm.model})"
        )
        logger.warning(warning)

        if self.confirm_callback is not None:
            return self.confirm_callback(warning)

        # Library mode: no interactive prompt — block by default
        logger.error(
            "LLM enrichment blocked: cost $%.4f exceeds threshold $%.2f. "
            "Pass confirm_callback=lambda _: True to override.",
            estimated, self.cost_threshold,
        )
        return False

    @classmethod
    def from_profile(
        cls,
        profile_name: str,
        output_dir: str = "./output",
        use_llm: bool = False,
        llm_model: str = "gpt-4o-mini",
        llm_base_url: str | None = None,
        cost_threshold: float = _DEFAULT_COST_THRESHOLD_USD,
        confirm_callback: Callable[[str], bool] | None = None,
        engine_config: EngineConfig | None = None,
    ) -> SynthEdPipeline:
        """Create a pipeline from a named benchmark profile.

        The profile's ``expected_dropout_range`` is used as the
        ``target_dropout_range`` for calibration.
        """
        from .benchmarks.profiles import PROFILES

        if profile_name not in PROFILES:
            available = ", ".join(PROFILES.keys())
            raise ValueError(
                f"Unknown profile '{profile_name}'. Available: {available}"
            )

        profile = PROFILES[profile_name]
        config = PipelineConfig(
            persona_config=profile.persona_config,
            environment=profile.environment,
            institutional_config=profile.institutional_config,
            grading_config=profile.grading_config,
            engine_config=engine_config or EngineConfig(),
            reference_stats=profile.reference_stats,
            output_dir=output_dir,
            use_llm=use_llm,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            seed=profile.seed,
            target_dropout_range=profile.expected_dropout_range,
            cost_threshold=cost_threshold,
        )
        return cls(config=config, confirm_callback=confirm_callback)

    def run(
        self,
        n_students: int = 200,
        enrich_personas: bool = False,
    ) -> dict[str, Any]:
        """
        Execute the full pipeline.

        Args:
            n_students: Number of synthetic students to generate.
            enrich_personas: Whether to use LLM for persona backstories.

        Returns:
            Comprehensive pipeline report including file paths and validation.
        """
        if not isinstance(n_students, int) or n_students <= 0:
            raise ValueError(f"n_students must be a positive integer, got {n_students}")

        if n_students < 100:
            logger.warning(
                "n_students=%d is small — stochastic variance may make "
                "calibration and validation results unreliable. "
                "Consider n_students >= 100 for stable results.",
                n_students,
            )

        report: dict[str, Any] = {
            "pipeline": f"SynthEd v{__version__}",
            "config": {
                "n_students": n_students,
                "seed": self.seed,
                "llm_enabled": self.use_llm,
                "semester_weeks": self.environment.total_weeks,
                "courses": len(self.environment.courses),
            },
            "timing": {},
        }

        # Include calibration info when dropout targeting is active
        if self._calibration_estimate is not None:
            est = self._calibration_estimate
            population_match = n_students == est.reference_population_size
            if not population_match:
                logger.warning(
                    "Dropout targeting was measured with %s students; this run uses %d. "
                    "Peer-network behavior may also vary with population size.",
                    est.reference_population_size, n_students,
                )
            report["dropout_targeting"] = {
                "target_range": self.target_dropout_range,
                "estimated_base_rate": est.estimated_dropout_base_rate,
                "confidence": est.confidence if population_match else "low",
                "n_semesters": est.n_semesters,
                "source_data_points": est.source_data_points,
                "observed_dropout_range": est.observed_dropout_range,
                "clamped": est.clamped,
                "mapping_status": est.mapping_status,
                "candidate_base_rates": est.candidate_base_rates,
                "reference_configuration_match": self._calibration_reference_matches,
                "reference_population_size": est.reference_population_size,
                "population_size_match": population_match,
            }

        # Pre-enrichment cost check
        enrich = enrich_personas and self.use_llm
        if enrich:
            if not self._check_cost_before_enrichment(n_students):
                logger.info("LLM enrichment skipped by user")
                enrich = False

        # Stage 1: Generate Population
        logger.info("[1/4] Generating %d student personas...", n_students)
        t0 = time.time()
        students = self.factory.generate_population(
            n=n_students, enrich_with_llm=enrich
        )
        report["timing"]["generation_sec"] = round(time.time() - t0, 2)
        report["population_summary"] = self.factory.population_summary(students)
        logger.info("      Done. Mean age: %.1f, Dropout risk: %.2f%%",
                    report['population_summary']['age_mean'],
                    report['population_summary']['base_dropout_risk_mean'] * 100)

        # Stage 2: Run Simulation
        total_weeks = self.environment.total_weeks * self.n_semesters
        logger.info("[2/4] Simulating %d weeks of ODL interactions (%d semester(s))...",
                     total_weeks, self.n_semesters)
        t0 = time.time()
        engagement_histories = None
        if self.n_semesters <= 1:
            records, states, network = self.engine.run(students)
        else:
            from .simulation.semester import MultiSemesterRunner
            runner = MultiSemesterRunner(
                self.engine, self.n_semesters,
                carry_over=self.carry_over_config,
                target_dropout_range=self.target_dropout_range,
            )
            result = runner.run(students)
            engagement_histories = result.engagement_histories
            records, states, network = (
                result.all_records, result.final_states, result.final_network,
            )
            cumulative_dropouts = 0
            report["semester_summary"] = []
            for semester in result.semester_results:
                entrants = len(semester.states)
                dropouts = sum(s.has_dropped_out for s in semester.states.values())
                cumulative_dropouts += dropouts
                report["semester_summary"].append({
                    "semester": semester.semester_index + 1,
                    "students_at_start": entrants,
                    "dropouts": dropouts,
                    "conditional_dropout_rate": dropouts / entrants if entrants else None,
                    "cumulative_dropout_rate": cumulative_dropouts / n_students,
                })
            if result.interim_reports:
                report["interim_reports"] = [
                    {
                        "semester": ir.semester,
                        "cumulative_dropout_rate": ir.cumulative_dropout_rate,
                        "target_range": ir.target_range,
                        "status": ir.status,
                    }
                    for ir in result.interim_reports
                ]
        report["timing"]["simulation_sec"] = round(time.time() - t0, 2)
        report["simulation_summary"] = self.engine.summary_statistics(states)
        if self.target_dropout_range is not None:
            actual = report["simulation_summary"]["dropout_rate"]
            lower, upper = self.target_dropout_range
            achieved = lower <= actual <= upper
            report["dropout_targeting"].update(
                actual_dropout_rate=actual, target_achieved=achieved,
            )
            if not achieved:
                logger.warning(
                    "Observed dropout %.3f is outside target range %s after %d "
                    "semester(s); calibration is an estimate, not a guarantee.",
                    actual, self.target_dropout_range, self.n_semesters,
                )
        report["network_summary"] = network.network_statistics(states)
        logger.info("      Done. %d interaction records generated. Dropout rate: %.2f%%",
                    len(records), report['simulation_summary']['dropout_rate'] * 100)

        # Stage 3: Export Data
        if not self._calibration_mode:
            logger.info("[3/4] Exporting datasets to %s/...", self.output_dir)
            t0 = time.time()
            file_paths = self.exporter.export_all(students, records, states, network)
            report["timing"]["export_sec"] = round(time.time() - t0, 2)
            report["exported_files"] = file_paths
            logger.info("      Done. Files: %s", ', '.join(Path(p).name for p in file_paths.values()))

            # Stage 4: OULAD export (optional)
            if self.export_oulad:
                oulad_exporter = OuladExporter(str(self.output_dir), seed=self.seed)
                oulad_paths = oulad_exporter.export_all(
                    students, records, states, self.environment,
                )
                report["exported_files"]["oulad"] = oulad_paths
                logger.info("OULAD-compatible export completed: 7 tables")
        else:
            report["exported_files"] = {}

        # Stage 5: Validate
        logger.info("[4/4] Running validation suite...")
        t0 = time.time()

        students_data, outcomes_data, weekly_eng = self._prepare_validation_data(
            students, states, network, engagement_histories=engagement_histories,
        )

        validation_report = self.validator.validate_all(
            students_data, outcomes_data, weekly_eng, total_weeks=total_weeks,
        )
        report["timing"]["validation_sec"] = round(time.time() - t0, 2)
        report["validation"] = validation_report
        logger.info("      Done. Quality: %s (%d/%d tests passed)",
                    validation_report['summary']['overall_quality'],
                    validation_report['summary']['passed'],
                    validation_report['summary']['total_tests'])

        # Save full report (skipped in calibration mode when no output dir)
        if self.output_dir is not None:
            report_path = self.output_dir / "pipeline_report.json"
            report_path.write_text(json.dumps(report, indent=2, default=str))
            report["report_path"] = str(report_path)
            logger.info("Pipeline complete. Report saved to %s", report_path)
        else:
            logger.info("Pipeline complete (calibration mode — no report written to disk)")

        # LLM cost report
        if self.llm:
            report["llm_costs"] = self.llm.cost_report()

        return report

    @staticmethod
    def _prepare_validation_data(
        students: list,
        states: dict,
        network: Any,
        *,
        engagement_histories: dict[str, list[float]] | None = None,
    ) -> tuple[list, list, dict]:
        """Build students_data, outcomes_data, and weekly_eng dicts for validation.

        Prepares all four factor clusters (student characteristics, skills,
        external factors, internal factors) plus Garrison CoI and Epstein-Axtell
        network degree fields required by SyntheticDataValidator. Multi-semester
        callers supply full histories separately from semester-local theory state.
        """
        students_data = []
        for s in students:
            d = {
                "student_id": s.id,
                "display_id": s.display_id,
                "age": s.age,
                "gender": s.gender,
                "employment_intensity": s.employment_intensity,
                "family_responsibility_level": s.family_responsibility_level,
                "internet_reliability": s.internet_reliability,
                "prior_gpa": s.prior_gpa,
                "socioeconomic_level": s.socioeconomic_level,
                # Cluster 1: Student Characteristics
                "conscientiousness": s.personality.conscientiousness,
                "goal_commitment": s.goal_commitment,
                # Cluster 2: Student Skills (Rovai, Moore)
                "self_regulation": s.self_regulation,
                "digital_literacy": s.digital_literacy,
                "learner_autonomy": s.learner_autonomy,
                # Cluster 3: External Factors (Bean & Metzner)
                "financial_stress": s.financial_stress,
                # Cluster 3 extra
                "perceived_cost_benefit": s.perceived_cost_benefit,
                # Cluster 4: Internal Factors (Tinto)
                "self_efficacy": s.self_efficacy,
                "motivation_type": s.motivation_type,
                # Garrison et al. (2000) — CoI composite for correlation validation
                "coi_composite": round((states[s.id].coi_state.social_presence + states[s.id].coi_state.cognitive_presence + states[s.id].coi_state.teaching_presence) / 3, 3) if s.id in states else None,
                # Epstein & Axtell (1996) — Network degree for correlation validation
                "network_degree": network.get_degree(s.id) if network else 0,
            }
            students_data.append(d)

        outcomes_data = []
        for s in students:
            state = states.get(s.id)
            if state:
                history = (engagement_histories.get(s.id, []) if engagement_histories is not None
                           else state.weekly_engagement_history)
                coi = state.coi_state
                coi_composite = (coi.social_presence + coi.cognitive_presence + coi.teaching_presence) / 3
                outcomes_data.append({
                    "student_id": s.id,
                    "display_id": s.display_id,
                    "has_dropped_out": state.has_dropped_out,
                    "dropout_week": state.dropout_week,
                    "withdrawal_reason": state.withdrawal_reason or "",
                    "final_dropout_phase": state.dropout_phase,
                    "final_engagement": history[-1] if history else None,
                    # Mean over observed weeks; no zero padding after dropout.
                    "mean_engagement": sum(history) / len(history) if history else None,
                    "final_gpa": round(state.cumulative_gpa, 2) if state.gpa_count > 0 else None,
                    # Garrison et al. (2000)
                    "coi_composite": round(coi_composite, 3),
                    # Deci & Ryan (1985)
                    "final_motivation_type": state.current_motivation_type,
                    "final_autonomy_need": round(state.sdt_needs.autonomy, 3),
                    "final_competence_need": round(state.sdt_needs.competence, 3),
                    "final_relatedness_need": round(state.sdt_needs.relatedness, 3),
                    # Gonzalez et al. (2025)
                    "final_exhaustion_level": round(state.exhaustion.exhaustion_level, 3),
                    # Epstein & Axtell (1996)
                    "network_degree": network.get_degree(s.id),
                })

        weekly_eng = engagement_histories if engagement_histories is not None else {
            sid: st.weekly_engagement_history
            for sid, st in states.items()
        }

        return students_data, outcomes_data, weekly_eng
