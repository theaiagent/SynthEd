"""
LLM utility wrapper for OpenAI API calls with caching and cost tracking.
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Any

from openai import OpenAI


class LLMClient:
    """Thin wrapper around OpenAI API with caching and cost tracking."""

    # Approximate pricing per 1M tokens (USD) - GPT-4o-mini
    PRICING = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
    }

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        cache_dir: str | None = None,
        temperature: float = 0.8,
    ):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0

    def _cache_key(self, messages: list[dict], **kwargs) -> str:
        content = json.dumps({"messages": messages, **kwargs}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached(self, key: str) -> str | None:
        if not self.cache_dir:
            return None
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())["content"]
        return None

    def _set_cached(self, key: str, content: str) -> None:
        if not self.cache_dir:
            return
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(json.dumps({"content": content}))

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat completion request with optional caching."""
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

        response = self.client.chat.completions.create(
            messages=messages,
            **kwargs,
        )

        content = response.choices[0].message.content

        # Track costs
        usage = response.usage
        if usage:
            self.total_input_tokens += usage.prompt_tokens
            self.total_output_tokens += usage.completion_tokens
        self.total_calls += 1

        self._set_cached(cache_key, content)
        return content

    def chat_json(self, messages: list[dict], temperature: float | None = None) -> dict:
        """Send a chat request expecting JSON output."""
        content = self.chat(
            messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(content)

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
        }
