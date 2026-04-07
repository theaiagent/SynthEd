from __future__ import annotations

import pytest
from dataclasses import replace, fields

from synthed.simulation.institutional import InstitutionalConfig, scale_by


class TestInstitutionalConfig:
    def test_default_values_are_neutral(self):
        ic = InstitutionalConfig()
        for f in fields(ic):
            assert getattr(ic, f.name) == 0.5, f"{f.name} default should be 0.5"

    def test_has_exactly_five_fields(self):
        ic = InstitutionalConfig()
        assert len(fields(ic)) == 5

    def test_frozen_raises_on_assignment(self):
        ic = InstitutionalConfig()
        with pytest.raises(AttributeError):
            ic.technology_quality = 0.9

    def test_replace_works_on_frozen(self):
        ic = InstitutionalConfig()
        ic2 = replace(ic, technology_quality=0.9)
        assert ic2.technology_quality == 0.9
        assert ic.technology_quality == 0.5

    def test_validation_rejects_below_zero(self):
        with pytest.raises(ValueError, match="outside"):
            InstitutionalConfig(support_services_quality=-0.1)

    def test_validation_rejects_above_one(self):
        with pytest.raises(ValueError, match="outside"):
            InstitutionalConfig(instructional_design_quality=1.1)

    def test_validation_accepts_boundaries(self):
        ic = InstitutionalConfig(
            instructional_design_quality=0.0,
            teaching_presence_baseline=1.0,
            support_services_quality=0.0,
            technology_quality=1.0,
            curriculum_flexibility=0.5,
        )
        assert ic.instructional_design_quality == 0.0
        assert ic.teaching_presence_baseline == 1.0


class TestScaleBy:
    def test_identity_at_default(self):
        assert scale_by(0.04, 0.5) == pytest.approx(0.04)

    def test_identity_at_default_large_constant(self):
        assert scale_by(0.50, 0.5) == pytest.approx(0.50)

    def test_low_end(self):
        assert scale_by(0.04, 0.0) == pytest.approx(0.04 * 0.7)

    def test_high_end(self):
        assert scale_by(0.04, 1.0) == pytest.approx(0.04 * 1.3)

    def test_custom_range(self):
        assert scale_by(1.0, 0.0, low=0.5, high=1.5) == pytest.approx(0.5)
        assert scale_by(1.0, 1.0, low=0.5, high=1.5) == pytest.approx(1.5)

    def test_inverted_param(self):
        result = scale_by(0.025, 1.0 - 0.8)
        assert result < 0.025

    def test_zero_constant_returns_zero(self):
        assert scale_by(0.0, 0.8) == 0.0

    def test_preserves_sign(self):
        assert scale_by(0.01, 0.0) > 0
        assert scale_by(0.01, 1.0) > 0

