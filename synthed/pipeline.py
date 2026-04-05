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

from . import __version__
from .agents.persona import PersonaConfig
from .agents.factory import StudentFactory
from .calibration import CalibrationMap
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
        persona_config: PersonaConfig | None = None,
        environment: ODLEnvironment | None = None,
        institutional_config: InstitutionalConfig | None = None,
        reference_stats: ReferenceStatistics | None = None,
        output_dir: str | None = "./output",
        llm_model: str = "gpt-4o-mini",
        llm_base_url: str | None = None,
        use_llm: bool = False,
        seed: int = 42,
        n_semesters: int = 1,
        carry_over_config: Any | None = None,
        target_dropout_range: tuple[float, float] | None = None,
        cost_threshold: float = _DEFAULT_COST_THRESHOLD_USD,
        confirm_callback: Callable[[str], bool] | None = None,
        grading_config: GradingConfig | None = None,
        engine_config: EngineConfig | None = None,
        export_oulad: bool = False,
        _calibration_mode: bool = False,
    ):
        self.persona_config = persona_config or PersonaConfig()
        self.environment = environment or ODLEnvironment()
        self.institutional_config = institutional_config or InstitutionalConfig()
        self.grading_config = grading_config or GradingConfig()
        self.reference = reference_stats or ReferenceStatistics()
        self.output_dir = Path(output_dir) if output_dir is not None else None
        self.use_llm = use_llm
        self.seed = seed
        self.n_semesters = n_semesters
        self.carry_over_config = carry_over_config
        self.target_dropout_range = target_dropout_range
        self.cost_threshold = cost_threshold
        self.confirm_callback = confirm_callback
        self.export_oulad = export_oulad
        self._calibration_mode = _calibration_mode
        self._calibration_estimate = None

        # Apply calibration when a target dropout range is provided
        if target_dropout_range is not None:
            self._apply_calibration(target_dropout_range, n_semesters)

        # Initialize components
        self.llm = LLMClient(model=llm_model, base_url=llm_base_url) if use_llm else None
        self.factory = StudentFactory(config=self.persona_config, llm_client=self.llm, seed=seed)
        self.engine = SimulationEngine(
            environment=self.environment,
            llm_client=self.llm,
            seed=seed,
            unavoidable_withdrawal_rate=self.persona_config.unavoidable_withdrawal_rate,
            institutional_config=self.institutional_config,
            grading_config=self.grading_config,
            engine_config=engine_config,
        )
        self.exporter = DataExporter(
            output_dir=str(self.output_dir) if self.output_dir is not None else None
        )
        self.validator = SyntheticDataValidator(reference=self.reference)

    def _apply_calibration(
        self,
        target_range: tuple[float, float],
        n_semesters: int,
    ) -> None:
        """Use CalibrationMap to set dropout_base_rate from target dropout range."""
        calibration_map = CalibrationMap()
        estimate = calibration_map.estimate_from_range(target_range, n_semesters)
        self._calibration_estimate = estimate

        # Update PersonaConfig with calibrated dropout_base_rate
        self.persona_config = replace(
            self.persona_config,
            dropout_base_rate=estimate.estimated_dropout_base_rate,
        )

        # Update ReferenceStatistics with target range for validation
        midpoint = (target_range[0] + target_range[1]) / 2
        self.reference = replace(
            self.reference,
            dropout_rate=midpoint,
            dropout_range=target_range,
        )

        logger.info(
            "Calibration: targeting %s dropout, estimated base_rate=%.2f (confidence: %s)",
            target_range,
            estimate.estimated_dropout_base_rate,
            estimate.confidence,
        )

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
        return cls(
            persona_config=profile.persona_config,
            environment=profile.environment,
            institutional_config=profile.institutional_config,
            grading_config=profile.grading_config,
            engine_config=engine_config,
            reference_stats=profile.reference_stats,
            output_dir=output_dir,
            use_llm=use_llm,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            seed=profile.seed,
            target_dropout_range=profile.expected_dropout_range,
            cost_threshold=cost_threshold,
            confirm_callback=confirm_callback,
        )

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
            report["dropout_targeting"] = {
                "target_range": self.target_dropout_range,
                "estimated_base_rate": est.estimated_dropout_base_rate,
                "confidence": est.confidence,
                "n_semesters": est.n_semesters,
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
            records, states, network = (
                result.all_records, result.final_states, result.final_network,
            )
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

        # Prepare validation data (all four factor clusters)
        students_data = []
        for s in students:
            d = {
                "student_id": s.id,
                "display_id": s.display_id,
                "age": s.age,
                "gender": s.gender,
                "is_employed": s.is_employed,
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
                coi = state.coi_state
                coi_composite = (coi.social_presence + coi.cognitive_presence + coi.teaching_presence) / 3
                outcomes_data.append({
                    "student_id": s.id,
                    "display_id": s.display_id,
                    "has_dropped_out": state.has_dropped_out,
                    "dropout_week": state.dropout_week,
                    "withdrawal_reason": state.withdrawal_reason or "",
                    "final_dropout_phase": state.dropout_phase,
                    "final_engagement": state.weekly_engagement_history[-1] if state.weekly_engagement_history else None,
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

        weekly_eng = {
            sid: st.weekly_engagement_history
            for sid, st in states.items()
        }

        validation_report = self.validator.validate_all(
            students_data, outcomes_data, weekly_eng
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
