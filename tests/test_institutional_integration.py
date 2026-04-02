"""Integration tests: InstitutionalConfig wired into SimulationEngine."""

from __future__ import annotations

import pytest

from synthed.simulation.engine import SimulationEngine
from synthed.simulation.environment import ODLEnvironment
from synthed.simulation.institutional import InstitutionalConfig
from synthed.agents.persona import PersonaConfig
from synthed.agents.factory import StudentFactory


class TestEngineInstitutionalIntegration:

    def test_engine_accepts_institutional_config(self):
        env = ODLEnvironment()
        ic = InstitutionalConfig(technology_quality=0.9)
        engine = SimulationEngine(environment=env, institutional_config=ic)
        assert engine.inst.technology_quality == 0.9

    def test_engine_defaults_to_neutral_config(self):
        env = ODLEnvironment()
        engine = SimulationEngine(environment=env)
        assert engine.inst.instructional_design_quality == 0.5

    def test_default_config_produces_identical_results(self):
        """Backward compat: default InstitutionalConfig = no behavior change."""
        env = ODLEnvironment()
        factory = StudentFactory(config=PersonaConfig(), seed=42)
        students = factory.generate_population(n=50)

        engine_a = SimulationEngine(environment=env, seed=42)
        _, states_a, _ = engine_a.run(students)

        engine_b = SimulationEngine(
            environment=env, seed=42,
            institutional_config=InstitutionalConfig(),
        )
        _, states_b, _ = engine_b.run(students)

        for sid in states_a:
            assert states_a[sid].cumulative_gpa == pytest.approx(
                states_b[sid].cumulative_gpa, abs=1e-10
            ), f"GPA mismatch for {sid}"
            assert states_a[sid].has_dropped_out == states_b[sid].has_dropped_out

    def test_high_quality_institution_lowers_dropout(self):
        """Directional: better institution -> fewer dropouts."""
        env = ODLEnvironment()
        factory = StudentFactory(config=PersonaConfig(), seed=42)
        students = factory.generate_population(n=200)

        low_ic = InstitutionalConfig(
            instructional_design_quality=0.2,
            teaching_presence_baseline=0.3,
            support_services_quality=0.2,
            technology_quality=0.3,
            curriculum_flexibility=0.2,
        )
        high_ic = InstitutionalConfig(
            instructional_design_quality=0.8,
            teaching_presence_baseline=0.7,
            support_services_quality=0.8,
            technology_quality=0.8,
            curriculum_flexibility=0.8,
        )

        engine_low = SimulationEngine(environment=env, seed=42, institutional_config=low_ic)
        _, states_low, _ = engine_low.run(students)
        dropout_low = sum(1 for s in states_low.values() if s.has_dropped_out) / len(states_low)

        engine_high = SimulationEngine(environment=env, seed=42, institutional_config=high_ic)
        _, states_high, _ = engine_high.run(students)
        dropout_high = sum(1 for s in states_high.values() if s.has_dropped_out) / len(states_high)

        assert dropout_high < dropout_low, (
            f"High quality ({dropout_high:.1%}) should have lower dropout "
            f"than low quality ({dropout_low:.1%})"
        )
