"""Tests for LLMClient with mocked OpenAI API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from synthed.utils.llm import LLMClient, LLMError, LLMResponseError, LLMRateLimitError


@pytest.fixture
def mock_openai():
    """Mock OpenAI client with a successful response."""
    with patch("synthed.utils.llm.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # Build a realistic response
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "test"}'
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 100
        mock_usage.completion_tokens = 50
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_client.chat.completions.create.return_value = mock_response

        yield mock_client


class TestLLMClientInit:
    def test_default_init(self, mock_openai):
        client = LLMClient(api_key="test-key")
        assert client.model == "gpt-4o-mini"
        assert client.total_calls == 0

    def test_custom_pricing(self, mock_openai):
        pricing = {"custom-model": {"input": 1.0, "output": 2.0}}
        client = LLMClient(api_key="test-key", pricing=pricing)
        assert "custom-model" in client.pricing

    def test_cache_dir_created(self, mock_openai, tmp_path):
        cache = tmp_path / "cache"
        LLMClient(api_key="test-key", cache_dir=str(cache))
        assert cache.exists()


class TestLLMClientChat:
    def test_chat_returns_content(self, mock_openai):
        client = LLMClient(api_key="test-key")
        result = client.chat([{"role": "user", "content": "hello"}])
        assert result == '{"result": "test"}'
        assert client.total_calls == 1

    def test_chat_tracks_tokens(self, mock_openai):
        client = LLMClient(api_key="test-key")
        client.chat([{"role": "user", "content": "hello"}])
        assert client.total_input_tokens == 100
        assert client.total_output_tokens == 50

    def test_chat_caches_response(self, mock_openai, tmp_path):
        client = LLMClient(api_key="test-key", cache_dir=str(tmp_path / "cache"))
        msgs = [{"role": "user", "content": "cached test"}]
        result1 = client.chat(msgs)
        result2 = client.chat(msgs)
        assert result1 == result2
        # Second call should use cache, not API
        assert mock_openai.chat.completions.create.call_count == 1

    def test_chat_empty_choices_raises(self, mock_openai):
        mock_openai.chat.completions.create.return_value.choices = []
        client = LLMClient(api_key="test-key")
        with pytest.raises(LLMResponseError, match="empty choices"):
            client.chat([{"role": "user", "content": "hello"}])

    def test_chat_none_content_raises(self, mock_openai):
        mock_openai.chat.completions.create.return_value.choices[0].message.content = None
        client = LLMClient(api_key="test-key")
        with pytest.raises(LLMResponseError, match="None content"):
            client.chat([{"role": "user", "content": "hello"}])


class TestLLMClientChatJson:
    def test_chat_json_parses(self, mock_openai):
        client = LLMClient(api_key="test-key")
        result = client.chat_json([{"role": "user", "content": "json please"}])
        assert result == {"result": "test"}

    def test_chat_json_invalid_raises(self, mock_openai):
        mock_openai.chat.completions.create.return_value.choices[0].message.content = "not json"
        client = LLMClient(api_key="test-key")
        with pytest.raises(LLMResponseError, match="invalid JSON"):
            client.chat_json([{"role": "user", "content": "hello"}])


class TestLLMClientRetry:
    def test_non_retryable_error_raises_immediately(self, mock_openai):
        mock_openai.chat.completions.create.side_effect = Exception("authentication failed")
        client = LLMClient(api_key="test-key", max_retries=3, retry_base_delay=0.01)
        with pytest.raises(LLMError):
            client.chat([{"role": "user", "content": "hello"}])
        assert client.total_failures == 1
        assert mock_openai.chat.completions.create.call_count == 1

    def test_rate_limit_retries_then_raises(self, mock_openai):
        mock_openai.chat.completions.create.side_effect = Exception("rate limit 429")
        client = LLMClient(api_key="test-key", max_retries=2, retry_base_delay=0.01)
        with pytest.raises(LLMRateLimitError):
            client.chat([{"role": "user", "content": "hello"}])
        assert mock_openai.chat.completions.create.call_count == 2

    def test_timeout_retries_then_raises(self, mock_openai):
        mock_openai.chat.completions.create.side_effect = TimeoutError("request timeout")
        client = LLMClient(api_key="test-key", max_retries=2, retry_base_delay=0.01)
        with pytest.raises(LLMError):
            client.chat([{"role": "user", "content": "hello"}])
        assert mock_openai.chat.completions.create.call_count == 2


class TestLLMClientCostReport:
    def test_cost_report_structure(self, mock_openai):
        client = LLMClient(api_key="test-key")
        client.chat([{"role": "user", "content": "hello"}])
        report = client.cost_report()
        assert "total_calls" in report
        assert "estimated_cost_usd" in report
        assert "total_input_tokens" in report
        assert "total_output_tokens" in report
        assert report["total_calls"] == 1

    def test_estimated_cost(self, mock_openai):
        client = LLMClient(api_key="test-key")
        client.chat([{"role": "user", "content": "hello"}])
        assert client.estimated_cost_usd > 0


    def test_connection_error_retries_then_raises_generic(self, mock_openai):
        """Connection error retries then raises generic LLMError (line 153)."""
        class ConnectionError(Exception):
            pass
        mock_openai.chat.completions.create.side_effect = ConnectionError("connection refused")
        client = LLMClient(api_key="test-key", max_retries=2, retry_base_delay=0.01)
        with pytest.raises(LLMError, match="API call failed after"):
            client.chat([{"role": "user", "content": "hello"}])
        assert mock_openai.chat.completions.create.call_count == 2
        assert client.total_failures == 1


class TestLLMClientCache:
    def test_corrupt_cache_handled(self, mock_openai, tmp_path):
        cache_dir = tmp_path / "cache"
        client = LLMClient(api_key="test-key", cache_dir=str(cache_dir))
        # Write corrupt cache
        msgs = [{"role": "user", "content": "corrupt"}]
        key = client._cache_key(msgs, model="gpt-4o-mini", temperature=0.8)
        cache_file = cache_dir / f"{key}.json"
        cache_file.write_text("not valid json")
        # Should fall back to API call
        result = client.chat(msgs)
        assert result == '{"result": "test"}'
