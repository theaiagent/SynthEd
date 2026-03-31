"""Tests for LLM enrichment feature: backstory generation, export, and error handling."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock


from synthed.agents.factory import StudentFactory
from synthed.data_output.exporter import DataExporter
from synthed.utils.llm import LLMClient, LLMError

if TYPE_CHECKING:
    pass


class TestLLMEnrichment:
    """Tests for LLM-based persona enrichment in the StudentFactory pipeline."""

    def test_enrich_with_llm_disabled(self):
        """Factory with no LLM client produces empty backstories."""
        factory = StudentFactory(seed=42, llm_client=None)
        population = factory.generate_population(n=5, enrich_with_llm=True)
        for persona in population:
            assert persona.backstory == ""

    def test_enrich_with_llm_mock(self):
        """Mock LLM client provides backstory that is set on the persona."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {
            "backstory": "Sarah works full-time as a nurse and enrolled in distance learning "
                         "to advance her career while caring for two children.",
            "primary_challenge": "time_management",
        }

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=3, enrich_with_llm=True)

        assert mock_llm.chat_json.call_count == 3
        for persona in population:
            assert "nurse" in persona.backstory or "Sarah" in persona.backstory
            assert len(persona.backstory) > 20

    def test_backstory_in_csv_export(self, tmp_path: Path):
        """Backstory column exists in exported students CSV."""
        from dataclasses import replace as _replace
        factory = StudentFactory(seed=42)
        population = factory.generate_population(n=3)
        population[0] = _replace(population[0], backstory="A working parent juggling career and studies.")

        exporter = DataExporter(output_dir=str(tmp_path))
        csv_path = exporter.export_students(population)

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "backstory" in rows[0]
        assert rows[0]["backstory"] == "A working parent juggling career and studies."
        assert rows[1]["backstory"] == ""

    def test_llm_client_error_handling(self):
        """Factory continues without crash when LLM raises an exception."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.side_effect = LLMError("API connection refused")

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=5, enrich_with_llm=True)

        # All 5 personas should be created despite LLM failures
        assert len(population) == 5
        for persona in population:
            assert persona.backstory == ""

    def test_llm_returns_invalid_json_structure(self):
        """Factory handles LLM returning a dict without the 'backstory' key."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {"story": "Some text without the right key."}

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=2, enrich_with_llm=True)

        for persona in population:
            assert persona.backstory == ""

    def test_llm_returns_empty_backstory(self):
        """Factory rejects empty or whitespace-only backstories from LLM."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {"backstory": "   ", "primary_challenge": "none"}

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=2, enrich_with_llm=True)

        for persona in population:
            assert persona.backstory == ""

    def test_llm_unexpected_exception(self):
        """Factory handles unexpected (non-LLMError) exceptions gracefully (lines 335-337)."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.side_effect = RuntimeError("unexpected crash")

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=2, enrich_with_llm=True)

        assert len(population) == 2
        for persona in population:
            assert persona.backstory == ""

    def test_llm_returns_non_dict(self):
        """Factory handles LLM returning a non-dict value (lines 341-344)."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = "just a string"

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=2, enrich_with_llm=True)

        for persona in population:
            assert persona.backstory == ""

    def test_llm_returns_too_short_backstory(self):
        """Factory rejects backstories shorter than MIN_BACKSTORY_LENGTH (lines 357-361)."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {
            "backstory": "Too short.",  # less than 20 chars
            "primary_challenge": "test",
        }

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        population = factory.generate_population(n=2, enrich_with_llm=True)

        for persona in population:
            assert persona.backstory == ""

    def test_llm_client_cost_report(self):
        """LLMClient.cost_report() returns expected structure with zero usage."""
        mock_openai = MagicMock()
        client = LLMClient.__new__(LLMClient)
        client.model = "gpt-4o-mini"
        client.client = mock_openai
        client.cache_dir = None
        client.temperature = 0.8
        client.max_retries = 3
        client.retry_base_delay = 1.0
        client.pricing = {"gpt-4o-mini": {"input": 0.15, "output": 0.60}}
        client.total_input_tokens = 0
        client.total_output_tokens = 0
        client.total_calls = 0
        client.total_retries = 0
        client.total_failures = 0

        report = client.cost_report()
        assert report["model"] == "gpt-4o-mini"
        assert report["total_calls"] == 0
        assert report["total_input_tokens"] == 0
        assert report["total_output_tokens"] == 0
        assert report["estimated_cost_usd"] == 0.0
        assert report["total_retries"] == 0
        assert report["total_failures"] == 0

    def test_llm_client_custom_pricing(self):
        """LLMClient with custom pricing uses those rates in cost_report."""
        mock_openai = MagicMock()
        client = LLMClient.__new__(LLMClient)
        client.model = "custom-model"
        client.client = mock_openai
        client.cache_dir = None
        client.temperature = 0.8
        client.max_retries = 3
        client.retry_base_delay = 1.0
        client.pricing = {"custom-model": {"input": 1.0, "output": 2.0}}
        client.total_input_tokens = 1_000_000
        client.total_output_tokens = 500_000
        client.total_calls = 10
        client.total_retries = 0
        client.total_failures = 0

        report = client.cost_report()
        assert report["model"] == "custom-model"
        # 1M input tokens * $1.0/1M = $1.0
        # 500K output tokens * $2.0/1M = $1.0
        assert report["estimated_cost_usd"] == 2.0

    def test_factory_uses_varied_prompts(self):
        """Mock LLM receives different system prompts for 7+ students (template rotation)."""
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.chat_json.return_value = {
            "backstory": "A diverse backstory generated by the LLM for this synthetic student.",
            "primary_challenge": "time_management",
        }

        factory = StudentFactory(seed=42, llm_client=mock_llm)
        factory.generate_population(n=10, enrich_with_llm=True)

        assert mock_llm.chat_json.call_count == 10

        # Collect unique system prompts across all calls
        system_prompts = set()
        for call in mock_llm.chat_json.call_args_list:
            messages = call[0][0]  # First positional arg is messages list
            system_prompt = messages[0]["content"]
            system_prompts.add(system_prompt)

        # With 10 students and 7 templates, we expect at least 3 different prompts
        assert len(system_prompts) >= 3, (
            f"Expected varied system prompts, got only {len(system_prompts)} unique"
        )
