"""Tests for LLM cost estimation and warning system."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from synthed.utils.llm import (
    LLMClient,
    _DEFAULT_AVG_INPUT_TOKENS,
    _DEFAULT_AVG_OUTPUT_TOKENS,
)
from synthed.pipeline import SynthEdPipeline, _DEFAULT_COST_THRESHOLD_USD


@pytest.fixture
def mock_openai():
    """Mock OpenAI client to avoid real API calls."""
    with patch("synthed.utils.llm.OpenAI") as mock_cls:
        mock_cls.return_value = MagicMock()
        yield mock_cls


class TestEstimateCost:
    def test_estimate_cost_calculation(self, mock_openai):
        """Known model pricing: gpt-4o-mini input=0.15, output=0.60 per 1M tokens."""
        client = LLMClient(api_key="test-key", model="gpt-4o-mini")
        cost = client.estimate_cost(n_calls=1000)
        # (1000 * 350 / 1_000_000) * 0.15 = 0.0525
        # (1000 * 200 / 1_000_000) * 0.60 = 0.12
        expected = 0.0525 + 0.12
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_estimate_cost_unknown_model_fallback(self, mock_openai):
        """Unknown model falls back to expensive pricing (gpt-4o rates)."""
        client = LLMClient(api_key="test-key", model="unknown-model")
        cost = client.estimate_cost(n_calls=1000)
        # Fallback: input=2.50, output=10.00
        # (1000 * 350 / 1_000_000) * 2.50 = 0.875
        # (1000 * 200 / 1_000_000) * 10.00 = 2.0
        expected = 0.875 + 2.0
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_estimate_cost_custom_tokens(self, mock_openai):
        """Custom avg_input_tokens and avg_output_tokens override defaults."""
        client = LLMClient(api_key="test-key", model="gpt-4o-mini")
        cost = client.estimate_cost(
            n_calls=500,
            avg_input_tokens=100,
            avg_output_tokens=50,
        )
        # (500 * 100 / 1_000_000) * 0.15 = 0.0075
        # (500 * 50 / 1_000_000) * 0.60 = 0.015
        expected = 0.0075 + 0.015
        assert cost == pytest.approx(expected, abs=1e-6)


class TestCheckCostBeforeEnrichment:
    @pytest.fixture
    def mock_llm(self, mock_openai):
        """Create a mock LLMClient with estimate_cost controllable."""
        client = LLMClient(api_key="test-key", model="gpt-4o-mini")
        return client

    def _make_pipeline(self, mock_llm, cost_threshold=1.0, confirm_callback=None):
        """Create a pipeline with mocked LLM for cost-check testing."""
        with patch("synthed.pipeline.LLMClient"):
            pipeline = SynthEdPipeline(
                use_llm=False,
                cost_threshold=cost_threshold,
                confirm_callback=confirm_callback,
            )
        # Manually inject mock LLM
        pipeline.llm = mock_llm
        return pipeline

    def test_check_cost_below_threshold(self, mock_llm):
        """Below threshold: returns True, no callback called."""
        callback = MagicMock()
        pipeline = self._make_pipeline(
            mock_llm,
            cost_threshold=1.0,
            confirm_callback=callback,
        )
        # gpt-4o-mini, 100 students: very cheap
        result = pipeline._check_cost_before_enrichment(100)
        assert result is True
        callback.assert_not_called()

    def test_check_cost_above_threshold_no_callback(self, mock_llm, caplog):
        """Above threshold, no callback: block by default and log error."""
        pipeline = self._make_pipeline(
            mock_llm,
            cost_threshold=0.0001,
            confirm_callback=None,
        )
        with caplog.at_level(logging.WARNING, logger="synthed.pipeline"):
            result = pipeline._check_cost_before_enrichment(1000)
        assert result is False
        assert "exceeds threshold" in caplog.text

    def test_check_cost_above_threshold_callback_approves(self, mock_llm):
        """Above threshold, callback returns True: enrichment proceeds."""
        callback = MagicMock(return_value=True)
        pipeline = self._make_pipeline(
            mock_llm,
            cost_threshold=0.0001,
            confirm_callback=callback,
        )
        result = pipeline._check_cost_before_enrichment(1000)
        assert result is True
        callback.assert_called_once()
        # Verify the warning message was passed to callback
        warning_msg = callback.call_args[0][0]
        assert "exceeds threshold" in warning_msg

    def test_check_cost_above_threshold_callback_rejects(self, mock_llm):
        """Above threshold, callback returns False: enrichment skipped."""
        callback = MagicMock(return_value=False)
        pipeline = self._make_pipeline(
            mock_llm,
            cost_threshold=0.0001,
            confirm_callback=callback,
        )
        result = pipeline._check_cost_before_enrichment(1000)
        assert result is False
        callback.assert_called_once()

    def test_no_llm_returns_true(self, mock_openai):
        """No LLM client: always returns True (nothing to check)."""
        pipeline = SynthEdPipeline(use_llm=False)
        result = pipeline._check_cost_before_enrichment(1000)
        assert result is True


class TestDefaultConstants:
    def test_default_threshold_constant(self):
        assert _DEFAULT_COST_THRESHOLD_USD == 1.0

    def test_default_avg_input_tokens(self):
        assert _DEFAULT_AVG_INPUT_TOKENS == 350

    def test_default_avg_output_tokens(self):
        assert _DEFAULT_AVG_OUTPUT_TOKENS == 200
