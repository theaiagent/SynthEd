"""Tests for benchmark profiles and generator."""

from __future__ import annotations

from synthed.benchmarks.profiles import PROFILES, BenchmarkProfile
from synthed.benchmarks.generator import BenchmarkGenerator


class TestBenchmarkProfiles:
    """Tests for the pre-defined benchmark profile registry."""

    def test_profiles_exist(self):
        """PROFILES dict should have 4 entries."""
        assert len(PROFILES) == 4

    def test_profile_structure(self):
        """Each profile should have required attributes."""
        for name, profile in PROFILES.items():
            assert isinstance(profile, BenchmarkProfile)
            assert profile.name == name
            assert len(profile.description) > 0
            assert isinstance(profile.expected_dropout_range, tuple)
            assert len(profile.expected_dropout_range) == 2
            lo, hi = profile.expected_dropout_range
            assert 0.0 <= lo < hi <= 1.0
            assert profile.n_students > 0
            assert profile.seed > 0

    def test_profile_names(self):
        """Expected profile names should be present."""
        expected = {
            "high_dropout_developing",
            "moderate_dropout_western",
            "low_dropout_corporate",
            "mega_university",
        }
        assert set(PROFILES.keys()) == expected


class TestBenchmarkGenerator:
    """Tests for the BenchmarkGenerator class."""

    def test_generator_runs(self, tmp_path):
        """generate() with overridden small n_students should return valid report."""
        profile = PROFILES["moderate_dropout_western"]

        # Use the pipeline directly with small n_students
        from synthed.pipeline import SynthEdPipeline
        pipeline = SynthEdPipeline(
            persona_config=profile.persona_config,
            environment=profile.environment,
            reference_stats=profile.reference_stats,
            output_dir=str(tmp_path),
            seed=profile.seed,
        )
        report = pipeline.run(n_students=20)

        assert "simulation_summary" in report
        assert "dropout_rate" in report["simulation_summary"]
        assert 0.0 <= report["simulation_summary"]["dropout_rate"] <= 1.0

    def test_list_profiles(self):
        """list_profiles returns dict mapping names to descriptions."""
        gen = BenchmarkGenerator()
        profiles = gen.list_profiles()

        assert isinstance(profiles, dict)
        assert len(profiles) == 4
        for name, desc in profiles.items():
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_unknown_profile_raises(self):
        """generate() with unknown profile name should raise ValueError."""
        import pytest
        gen = BenchmarkGenerator()
        with pytest.raises(ValueError, match="Unknown profile"):
            gen.generate("nonexistent_profile", output_dir="/tmp/test")

    def test_generate_valid_profile_in_range(self, tmp_path):
        """generate() with a valid profile returns report with benchmark_validation."""
        from unittest.mock import patch

        mock_report = {
            "simulation_summary": {"dropout_rate": 0.15},
        }
        with patch(
            "synthed.benchmarks.generator.SynthEdPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = mock_report
            gen = BenchmarkGenerator()
            report = gen.generate(
                "low_dropout_corporate",
                output_dir=str(tmp_path / "benchmark"),
            )

        assert "benchmark_validation" in report
        bv = report["benchmark_validation"]
        assert bv["profile"] == "low_dropout_corporate"
        assert bv["actual_dropout_rate"] == 0.15
        # 0.15 is within (0.05, 0.30)
        assert bv["in_expected_range"] is True

    def test_generate_valid_profile_out_of_range(self, tmp_path):
        """generate() logs warning when dropout is outside expected range."""
        from unittest.mock import patch

        mock_report = {
            "simulation_summary": {"dropout_rate": 0.95},
        }
        with patch(
            "synthed.benchmarks.generator.SynthEdPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = mock_report
            gen = BenchmarkGenerator()
            report = gen.generate(
                "low_dropout_corporate",
                output_dir=str(tmp_path / "benchmark"),
            )

        bv = report["benchmark_validation"]
        # 0.95 is outside (0.05, 0.30)
        assert bv["in_expected_range"] is False

    def test_generate_default_output_dir(self):
        """generate() with no output_dir uses default benchmarks/<name>."""
        from unittest.mock import patch

        mock_report = {
            "simulation_summary": {"dropout_rate": 0.45},
        }
        with patch(
            "synthed.benchmarks.generator.SynthEdPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = mock_report
            gen = BenchmarkGenerator()
            report = gen.generate("moderate_dropout_western")

        assert "benchmark_validation" in report

    def test_generate_all(self, tmp_path):
        """generate_all() runs all profiles and returns a list of reports."""
        from unittest.mock import patch

        mock_report = {
            "simulation_summary": {"dropout_rate": 0.50},
        }
        with patch(
            "synthed.benchmarks.generator.SynthEdPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = mock_report
            gen = BenchmarkGenerator()
            results = gen.generate_all(output_dir=str(tmp_path / "all"))

        assert isinstance(results, list)
        assert len(results) == len(PROFILES)
        for report in results:
            assert "benchmark_validation" in report
            assert "simulation_summary" in report
