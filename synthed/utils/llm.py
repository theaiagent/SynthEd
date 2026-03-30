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
from typing import TYPE_CHECKING

from openai import OpenAI

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMRateLimitError(LLMError):
    """Raised when the API returns a rate-limit response."""


class LLMTimeoutError(LLMError):
    """Raised when the API request times out."""


class LLMResponseError(LLMError):
    """Raised when the API response is malformed or empty."""


class LLMClient:
    """Thin wrapper around OpenAI API with caching, retry, and cost tracking."""

    # Approximate pricing per 1M tokens (USD) - GPT-4o-mini
    PRICING = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
    }

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        cache_dir: str | None = None,
        temperature: float = 0.8,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    ):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        self.total_retries = 0
        self.total_failures = 0

    def _cache_key(self, messages: list[dict], **kwargs) -> str:
        content = json.dumps({"messages": messages, **kwargs}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached(self, key: str) -> str | None:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())["content"]
            except (json.JSONDecodeError, KeyError):
                logger.warning("Corrupt cache entry %s, ignoring", key)
                return None
        return None

    def _set_cached(self, key: str, content: str) -> None:
        if not self.cache_dir:
            return
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps({"content": content}))

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
            "temperature": temperature or self.temperature,
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

    @property
    def estimated_cost_usd(self) -> float:
        pricing = self.PRICING.get(self.model, {"input": 2.50, "output": 10.00})
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
