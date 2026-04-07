"""Tests for benchmark profiles and generator."""

from __future__ import annotations

import json

import pytest

from synthed.benchmarks.profiles import PROFILES, BenchmarkProfile
from synthed.benchmarks.generator import BenchmarkGenerator


class TestBenchmarkProfiles:
    """Tests for the pre-defined benchmark profile registry."""

    def test_profiles_exist(self):
        """PROFILES dict should have 1 entry."""
        assert len(PROFILES) == 1

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
        expected = {"default"}
        assert set(PROFILES.keys()) == expected



class TestBenchmarkGenerator:
    """Tests for the BenchmarkGenerator class."""

    def test_generator_runs(self, tmp_path):
        """generate() with overridden small n_students should return valid report."""
        profile = PROFILES["default"]

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
        assert len(profiles) == 1
        for name, desc in profiles.items():
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_unknown_profile_raises(self):
        """generate() with unknown profile name should raise ValueError."""
        gen = BenchmarkGenerator()
        with pytest.raises(ValueError, match="Unknown profile"):
            gen.generate("nonexistent_profile", output_dir="/tmp/test")

    def test_generate_valid_profile_in_range(self, tmp_path):
        """generate() with a valid profile returns report with benchmark_validation."""
        from unittest.mock import patch

        mock_report = {
            "simulation_summary": {"dropout_rate": 0.45},
        }
        with patch(
            "synthed.benchmarks.generator.SynthEdPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = mock_report
            gen = BenchmarkGenerator()
            report = gen.generate(
                "default",
                output_dir=str(tmp_path / "benchmark"),
            )

        assert "benchmark_validation" in report
        bv = report["benchmark_validation"]
        assert bv["profile"] == "default"
        assert bv["actual_dropout_rate"] == 0.45
        # 0.45 is within (0.35, 0.60)
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
                "default",
                output_dir=str(tmp_path / "benchmark"),
            )

        bv = report["benchmark_validation"]
        # 0.95 is outside (0.35, 0.60)
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
            report = gen.generate("default")

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


class TestBenchmarkReport:
    """Tests for benchmark report generation."""

    def _make_mock_report(self, profile_name, dropout=0.45, gpa=2.85, engagement=0.62):
        """Build a realistic mock report for testing."""
        return {
            "simulation_summary": {
                "total_students": 100,
                "dropout_rate": dropout,
                "dropout_count": int(100 * dropout),
                "retained_students": 100 - int(100 * dropout),
                "mean_final_gpa": gpa,
                "mean_final_engagement": engagement,
                "mean_dropout_week": 8.5,
            },
            "benchmark_validation": {
                "profile": profile_name,
                "expected_dropout_range": PROFILES[profile_name].expected_dropout_range,
                "actual_dropout_rate": dropout,
                "in_expected_range": (
                    PROFILES[profile_name].expected_dropout_range[0]
                    <= dropout
                    <= PROFILES[profile_name].expected_dropout_range[1]
                ),
            },
            "validation": {"summary": {"overall_quality": "GOOD", "passed": 18, "total_tests": 21}},
            "timing": {"generation_sec": 0.5, "simulation_sec": 1.2, "export_sec": 0.1, "validation_sec": 0.3},
        }

    def test_format_report_contains_all_profiles(self):
        """_format_report should mention the default profile name."""
        results = [
            self._make_mock_report("default", dropout=0.45),
        ]
        md = BenchmarkGenerator._format_report(results, elapsed=5.0)

        for name in PROFILES:
            assert name in md

    def test_format_report_markdown_structure(self):
        """Report should have expected headers and table."""
        results = [self._make_mock_report("default")]
        md = BenchmarkGenerator._format_report(results, elapsed=1.0)

        assert "# SynthEd Benchmark Report" in md
        assert "## Profile Comparison" in md
        assert "## Profile Details" in md
        assert "| Profile |" in md
        assert "Generated in" in md

    def test_format_report_in_range_flag(self):
        """YES/NO flags should match expected range."""
        results = [
            self._make_mock_report("default", dropout=0.45),
            self._make_mock_report("default", dropout=0.95),
        ]
        # Override the second to be out of range
        results[1]["benchmark_validation"]["in_expected_range"] = False

        md = BenchmarkGenerator._format_report(results, elapsed=1.0)
        assert "YES" in md
        assert "NO" in md

    def test_format_report_handles_none_gpa(self):
        """Report should not crash when GPA or engagement is None."""
        report = self._make_mock_report("default")
        report["simulation_summary"]["mean_final_gpa"] = None
        report["simulation_summary"]["mean_final_engagement"] = None
        report["simulation_summary"]["mean_dropout_week"] = None

        md = BenchmarkGenerator._format_report([report], elapsed=1.0)
        assert "N/A" in md
        assert "-" in md

    def test_generate_report_writes_files(self, tmp_path):
        """generate_report should write .md and .json files."""
        from unittest.mock import patch

        mock_report = self._make_mock_report("default")
        with patch(
            "synthed.benchmarks.generator.SynthEdPipeline"
        ) as MockPipeline:
            MockPipeline.return_value.run.return_value = {
                "simulation_summary": mock_report["simulation_summary"],
            }
            gen = BenchmarkGenerator()
            md = gen.generate_report(output_dir=str(tmp_path))

        assert (tmp_path / "benchmark_report.md").exists()
        assert (tmp_path / "benchmark_results.json").exists()

        # Verify JSON is valid
        data = json.loads((tmp_path / "benchmark_results.json").read_text())
        assert isinstance(data, list)
        assert len(data) == 1

        # Verify markdown returned
        assert "# SynthEd Benchmark Report" in md

