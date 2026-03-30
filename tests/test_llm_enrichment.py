"""Tests for LLM enrichment feature: backstory generation, export, and error handling."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from synthed.agents.factory import StudentFactory
from synthed.agents.persona import StudentPersona
from synthed.data_output.exporter import DataExporter
from synthed.utils.llm import LLMClient, LLMError, LLMResponseError

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
        factory = StudentFactory(seed=42)
        population = factory.generate_population(n=3)
        population[0].backstory = "A working parent juggling career and studies."

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
