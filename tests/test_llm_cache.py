"""Tests for LLM cache TTL expiry and LRU eviction."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from synthed.utils.llm import (
    LLMClient,
    _DEFAULT_CACHE_MAX_ENTRIES,
    _DEFAULT_CACHE_TTL_SECONDS,
)


@pytest.fixture
def mock_openai():
    """Mock OpenAI client with a successful response."""
    with patch("synthed.utils.llm.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

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


class TestCacheDefaults:
    def test_default_constants(self):
        """Verify default constant values match 7 days and 10000 entries."""
        assert _DEFAULT_CACHE_TTL_SECONDS == 604800  # 7 * 24 * 3600
        assert _DEFAULT_CACHE_MAX_ENTRIES == 10_000


class TestCacheTTL:
    def test_new_entry_has_timestamp(self, mock_openai, tmp_path):
        """Write a cache entry, verify created_at exists and is close to now."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(api_key="test-key", cache_dir=str(cache_dir))
        before = time.time()
        client._set_cached("test_key", "test_content")
        after = time.time()

        cache_file = cache_dir / "test_key.json"
        data = json.loads(cache_file.read_text())
        assert "created_at" in data
        assert isinstance(data["created_at"], float)
        assert before <= data["created_at"] <= after

    def test_old_format_treated_as_stale(self, mock_openai, tmp_path):
        """Old-format entries (no created_at) return None and get deleted."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(api_key="test-key", cache_dir=str(cache_dir))

        cache_file = cache_dir / "old_key.json"
        cache_file.write_text(json.dumps({"content": "old"}))

        result = client._get_cached("old_key")
        assert result is None
        assert not cache_file.exists()

    def test_entry_within_ttl_returned(self, mock_openai, tmp_path):
        """Entry with current timestamp is returned from cache."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(api_key="test-key", cache_dir=str(cache_dir))

        cache_file = cache_dir / "fresh_key.json"
        cache_file.write_text(json.dumps({
            "content": "fresh_content",
            "created_at": time.time(),
        }))

        result = client._get_cached("fresh_key")
        assert result == "fresh_content"

    def test_entry_beyond_ttl_evicted(self, mock_openai, tmp_path):
        """Entry with old timestamp returns None and file is deleted."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(api_key="test-key", cache_dir=str(cache_dir))

        cache_file = cache_dir / "stale_key.json"
        cache_file.write_text(json.dumps({
            "content": "stale_content",
            "created_at": time.time() - 999_999,
        }))

        result = client._get_cached("stale_key")
        assert result is None
        assert not cache_file.exists()

    def test_corrupt_entry_handled(self, mock_openai, tmp_path):
        """Invalid JSON in cache file returns None."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(api_key="test-key", cache_dir=str(cache_dir))

        cache_file = cache_dir / "corrupt_key.json"
        cache_file.write_text("{{not valid json")

        result = client._get_cached("corrupt_key")
        assert result is None


class TestCacheLRUEviction:
    def test_lru_eviction_on_write(self, mock_openai, tmp_path):
        """With max_entries=3, a 4th write evicts the oldest entry."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(
            api_key="test-key",
            cache_dir=str(cache_dir),
            cache_max_entries=3,
        )

        # Write 3 entries with distinct mtimes
        for i in range(3):
            client._set_cached(f"key_{i}", f"content_{i}")
            time.sleep(0.02)

        # Write a 4th — should evict the oldest (key_0)
        client._set_cached("key_3", "content_3")

        remaining = list(cache_dir.glob("*.json"))
        remaining_names = {p.stem for p in remaining}
        assert len(remaining) == 3
        assert "key_0" not in remaining_names
        assert "key_3" in remaining_names

    def test_lru_preserves_recently_accessed(self, mock_openai, tmp_path):
        """Touching the oldest entry protects it from eviction."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(
            api_key="test-key",
            cache_dir=str(cache_dir),
            cache_max_entries=3,
        )

        # Write 3 entries with distinct mtimes
        for i in range(3):
            client._set_cached(f"key_{i}", f"content_{i}")
            time.sleep(0.02)

        # Access key_0 (touch it so it's no longer the oldest by mtime)
        client._get_cached("key_0")
        time.sleep(0.02)

        # Write a 4th — key_1 should be evicted (oldest mtime), not key_0
        client._set_cached("key_3", "content_3")

        remaining = list(cache_dir.glob("*.json"))
        remaining_names = {p.stem for p in remaining}
        assert len(remaining) == 3
        assert "key_1" not in remaining_names
        assert "key_0" in remaining_names
        assert "key_3" in remaining_names

    def test_eviction_count_correct(self, mock_openai, tmp_path):
        """With max_entries=2, after 5 writes exactly 2 files remain."""
        cache_dir = tmp_path / "cache"
        client = LLMClient(
            api_key="test-key",
            cache_dir=str(cache_dir),
            cache_max_entries=2,
        )

        for i in range(5):
            client._set_cached(f"key_{i}", f"content_{i}")
            time.sleep(0.02)

        remaining = list(cache_dir.glob("*.json"))
        assert len(remaining) == 2
