"""
LLM utility wrapper for OpenAI API calls with caching, retry, and cost tracking.
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Iterator

from openai import OpenAI


logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMRateLimitError(LLMError):
    """Raised when the API returns a rate-limit response."""


class LLMTimeoutError(LLMError):
    """Raised when the API request times out."""


class LLMResponseError(LLMError):
    """Raised when the API response is malformed or empty."""


# Approximate pricing per 1M tokens (USD)
# Last verified: 2025-06-01 — https://openai.com/api/pricing/
_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

_DEFAULT_CACHE_TTL_SECONDS: int = 7 * 24 * 3600    # 7 days
_DEFAULT_CACHE_MAX_ENTRIES: int = 10_000

_DEFAULT_AVG_INPUT_TOKENS: int = 350
_DEFAULT_AVG_OUTPUT_TOKENS: int = 200

_CHARS_PER_TOKEN_ESTIMATE: int = 4


class LLMClient:
    """Thin wrapper around OpenAI API with caching, retry, and cost tracking."""

    # Kept for backward compatibility; prefer _DEFAULT_PRICING / self.pricing
    PRICING = _DEFAULT_PRICING

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        cache_dir: str | None = None,
        temperature: float = 0.8,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        pricing: dict | None = None,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
        cache_max_entries: int = _DEFAULT_CACHE_MAX_ENTRIES,
    ):
        self.model = model
        self.temperature = temperature
        self.base_url = base_url

        if base_url is not None:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f"base_url must use http or https scheme, got: {parsed.scheme!r}"
                )
            if not parsed.netloc:
                raise ValueError(f"base_url must include a host: {base_url!r}")
            if parsed.scheme == "http" and (api_key or os.getenv("OPENAI_API_KEY")):
                logger.warning("base_url uses plain HTTP — API key will be transmitted unencrypted")

        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
        )
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.pricing = pricing or dict(_DEFAULT_PRICING)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_max_entries = cache_max_entries

        if base_url and model not in self.pricing:
            logger.info(
                "Custom base_url with unknown model '%s' — cost tracking may be inaccurate",
                model,
            )

        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        self.total_retries = 0
        self.total_failures = 0

    def estimate_cost(
        self,
        n_calls: int,
        avg_input_tokens: int = _DEFAULT_AVG_INPUT_TOKENS,
        avg_output_tokens: int = _DEFAULT_AVG_OUTPUT_TOKENS,
    ) -> float:
        """Estimate cost in USD for n_calls at current model pricing."""
        pricing = self.pricing.get(self.model, {"input": 2.50, "output": 10.00})
        input_cost = (n_calls * avg_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (n_calls * avg_output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _cache_key(self, messages: list[dict], **kwargs) -> str:
        content = json.dumps({"messages": messages, **kwargs}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached(self, key: str) -> str | None:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text())
            content = data["content"]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt cache entry %s, ignoring", key)
            return None

        # TTL check — old-format entries (no created_at) treated as stale
        created_at = data.get("created_at")
        if created_at is None:
            logger.debug("Cache entry %s has no timestamp, treating as stale", key[:12])
            cache_file.unlink(missing_ok=True)
            return None
        if (time.time() - created_at) > self.cache_ttl_seconds:
            logger.debug("Cache entry %s expired", key[:12])
            cache_file.unlink(missing_ok=True)
            return None

        # Touch mtime for LRU tracking
        cache_file.touch()
        return content

    def _set_cached(self, key: str, content: str) -> None:
        if not self.cache_dir:
            return
        self._evict_if_needed()
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps({
            "content": content,
            "created_at": time.time(),
        }))

    def _evict_if_needed(self) -> None:
        """LRU eviction when cache exceeds max_entries. Lazy -- runs on write only."""
        if not self.cache_dir:
            return
        entries = list(self.cache_dir.glob("*.json"))
        if len(entries) < self.cache_max_entries:
            return
        # Sort only when eviction is actually needed
        entries.sort(key=lambda p: p.stat().st_mtime)
        evict_count = len(entries) - self.cache_max_entries + 1
        for path in entries[:evict_count]:
            path.unlink(missing_ok=True)
            logger.debug("Evicted cache entry: %s", path.name[:12])

    def _call_api_with_retry(self, messages: list[dict], **kwargs) -> object:
        """Call the OpenAI API with exponential backoff retry on transient errors."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return self.client.chat.completions.create(
                    messages=messages,
                    **kwargs,
                )
            except Exception as exc:
                last_error = exc
                exc_name = type(exc).__name__

                # Detect rate-limit errors (HTTP 429)
                is_rate_limit = "rate" in str(exc).lower() or "429" in str(exc)
                # Detect timeout errors
                is_timeout = "timeout" in exc_name.lower() or "timeout" in str(exc).lower()
                # Detect network/connection errors
                is_network = any(
                    kw in exc_name.lower()
                    for kw in ("connection", "network", "socket")
                )
                is_retryable = is_rate_limit or is_timeout or is_network

                if not is_retryable:
                    # Non-retryable error (auth, bad request, etc.) — raise immediately
                    logger.error("Non-retryable LLM error: %s", exc)
                    self.total_failures += 1
                    raise LLMError(f"API call failed: {exc}") from exc

                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning(
                        "LLM API attempt %d/%d failed (%s), retrying in %.1fs",
                        attempt + 1, self.max_retries, exc_name, delay,
                    )
                    self.total_retries += 1
                    time.sleep(delay)

        # All retries exhausted
        self.total_failures += 1
        if last_error and ("rate" in str(last_error).lower() or "429" in str(last_error)):
            raise LLMRateLimitError(
                f"Rate limit exceeded after {self.max_retries} retries"
            ) from last_error
        if last_error and "timeout" in str(last_error).lower():
            raise LLMTimeoutError(
                f"Request timed out after {self.max_retries} retries"
            ) from last_error
        raise LLMError(
            f"API call failed after {self.max_retries} retries: {last_error}"
        ) from last_error

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat completion request with optional caching and retry."""
        kwargs = {
            "model": self.model,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        cache_key = self._cache_key(messages, **kwargs)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        response = self._call_api_with_retry(messages, **kwargs)

        if not response.choices:
            self.total_failures += 1
            raise LLMResponseError("API returned empty choices list")

        content = response.choices[0].message.content
        if content is None:
            self.total_failures += 1
            raise LLMResponseError("API returned None content")

        # Track costs
        usage = response.usage
        if usage:
            self.total_input_tokens += usage.prompt_tokens
            self.total_output_tokens += usage.completion_tokens
        self.total_calls += 1

        self._set_cached(cache_key, content)
        return content

    def chat_json(self, messages: list[dict], temperature: float | None = None) -> dict:
        """Send a chat request expecting JSON output.

        Raises:
            LLMResponseError: If the response is not valid JSON.
        """
        content = self.chat(
            messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            self.total_failures += 1
            raise LLMResponseError(
                f"API returned invalid JSON: {content[:200]}"
            ) from exc

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream a chat completion, yielding content chunks.

        Does NOT use cache (streaming is for interactive use).
        Token tracking is approximate (character-count heuristic).
        """
        kwargs = {
            "model": self.model,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": True,
        }

        # Approximate input token tracking (no usage object in streaming)
        input_chars = sum(len(m.get("content", "")) for m in messages)
        self.total_input_tokens += input_chars // _CHARS_PER_TOKEN_ESTIMATE

        response = self._call_api_with_retry(messages, **kwargs)

        collected_content: list[str] = []
        try:
            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    collected_content.append(delta.content)
                    yield delta.content
        except Exception as exc:
            self.total_failures += 1
            raise LLMError(f"Stream interrupted: {exc}") from exc
        finally:
            self.total_calls += 1
            # Approximate output token tracking
            full_content = "".join(collected_content)
            self.total_output_tokens += len(full_content) // _CHARS_PER_TOKEN_ESTIMATE

    @property
    def estimated_cost_usd(self) -> float:
        pricing = self.pricing.get(self.model, {"input": 2.50, "output": 10.00})
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def cost_report(self) -> dict:
        return {
            "model": self.model,
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "total_retries": self.total_retries,
            "total_failures": self.total_failures,
        }
