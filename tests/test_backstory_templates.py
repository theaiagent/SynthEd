"""Tests for backstory template selection and prompt building."""

from __future__ import annotations

import numpy as np
import pytest

from synthed.agents.backstory_templates import (
    BackstoryTemplate,
    LifeEvent,
    RegionalContext,
    _LIFE_EVENT_INJECTION_PROBABILITY,
    _LIFE_EVENTS,
    _REGIONAL_CONTEXTS,
    _TEMPLATES,
    build_enrichment_prompt,
    select_life_event,
    select_regional_context,
    select_template,
)
from synthed.agents.factory import StudentFactory


@pytest.fixture()
def persona():
    """Create a single persona for testing."""
    factory = StudentFactory(seed=42)
    personas = factory.generate_population(n=1)
    return personas[0]


class TestSelectTemplate:
    """Tests for select_template()."""

    def test_select_template_returns_valid_template(self):
        rng = np.random.default_rng(42)
        result = select_template(rng)
        assert isinstance(result, BackstoryTemplate)

    def test_select_template_deterministic_with_seed(self):
        rng1 = np.random.default_rng(99)
        rng2 = np.random.default_rng(99)
        t1 = select_template(rng1)
        t2 = select_template(rng2)
        assert t1.id == t2.id

    def test_select_template_varies_across_students(self):
        rng = np.random.default_rng(42)
        templates = [select_template(rng) for _ in range(20)]
        unique_ids = {t.id for t in templates}
        assert len(unique_ids) > 1, "Expected variety across 20 selections"

    def test_all_templates_used_in_large_sample(self):
        rng = np.random.default_rng(12345)
        selected_ids = {select_template(rng).id for _ in range(100)}
        expected_ids = {t.id for t in _TEMPLATES}
        assert selected_ids == expected_ids, (
            f"Missing templates: {expected_ids - selected_ids}"
        )


class TestSelectLifeEvent:
    """Tests for select_life_event()."""

    def test_life_event_injection_probability(self):
        rng = np.random.default_rng(42)
        results = [select_life_event(rng) for _ in range(1000)]
        injected = sum(1 for r in results if r is not None)
        rate = injected / 1000
        assert 0.30 <= rate <= 0.50, (
            f"Expected ~40% injection rate, got {rate:.1%}"
        )

    def test_life_event_deterministic(self):
        rng1 = np.random.default_rng(77)
        rng2 = np.random.default_rng(77)
        e1 = select_life_event(rng1)
        e2 = select_life_event(rng2)
        if e1 is None:
            assert e2 is None
        else:
            assert e1.label == e2.label

    def test_life_event_none_when_not_injected(self):
        rng = np.random.default_rng(42)
        results = [select_life_event(rng) for _ in range(100)]
        assert any(r is None for r in results), "Expected some None results"

    def test_life_event_returns_life_event_when_injected(self):
        rng = np.random.default_rng(42)
        results = [select_life_event(rng) for _ in range(100)]
        injected = [r for r in results if r is not None]
        assert len(injected) > 0
        for event in injected:
            assert isinstance(event, LifeEvent)


class TestSelectRegionalContext:
    """Tests for select_regional_context()."""

    def test_regional_context_selection(self):
        rng = np.random.default_rng(42)
        result = select_regional_context(rng)
        assert isinstance(result, RegionalContext)
        assert result.setting in {"rural", "urban", "suburban", "peri-urban"}
        assert result.connectivity in {"reliable", "intermittent", "limited"}


class TestBuildEnrichmentPrompt:
    """Tests for build_enrichment_prompt()."""

    def test_build_enrichment_prompt_structure(self, persona):
        rng = np.random.default_rng(42)
        template = select_template(rng)
        life_event = select_life_event(rng)
        regional_ctx = select_regional_context(rng)
        messages = build_enrichment_prompt(persona, template, life_event, regional_ctx)

        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "content" in messages[0]
        assert "content" in messages[1]

    def test_build_enrichment_prompt_includes_persona_data(self, persona):
        rng = np.random.default_rng(42)
        template = select_template(rng)
        regional_ctx = select_regional_context(rng)
        messages = build_enrichment_prompt(persona, template, None, regional_ctx)

        user_content = messages[1]["content"]
        assert str(persona.age) in user_content
        if persona.is_employed:
            assert "employed" in user_content
        else:
            assert "unemployed" in user_content

    def test_build_enrichment_prompt_with_life_event(self, persona):
        life_event = LifeEvent(
            label="test_event",
            description="a test life event for validation",
        )
        template = _TEMPLATES[0]
        regional_ctx = _REGIONAL_CONTEXTS[0]
        messages = build_enrichment_prompt(persona, template, life_event, regional_ctx)

        user_content = messages[1]["content"]
        assert "a test life event for validation" in user_content

    def test_build_enrichment_prompt_without_life_event(self, persona):
        template = _TEMPLATES[0]
        regional_ctx = _REGIONAL_CONTEXTS[0]
        messages = build_enrichment_prompt(persona, template, None, regional_ctx)

        user_content = messages[1]["content"]
        assert "no significant recent life changes" in user_content


class TestConstants:
    """Tests for module-level constants."""

    def test_template_constants_valid(self):
        assert len(_TEMPLATES) == 7
        for template in _TEMPLATES:
            assert isinstance(template, BackstoryTemplate)
            assert template.id, "Template id must be non-empty"
            assert template.system_prompt, "Template system_prompt must be non-empty"
            assert template.user_prompt_format, "Template user_prompt_format must be non-empty"
            # All system prompts must include content guardrails
            assert "No violence" in template.system_prompt
            assert "sexual content" in template.system_prompt
            assert "discrimination" in template.system_prompt
            # All system prompts must include JSON instruction
            assert "backstory" in template.system_prompt
            assert "primary_challenge" in template.system_prompt

    def test_life_events_weights_positive(self):
        assert len(_LIFE_EVENTS) >= 12
        for event in _LIFE_EVENTS:
            assert isinstance(event, LifeEvent)
            assert event.weight > 0, f"Weight for {event.label} must be positive"
            assert event.label, "Life event label must be non-empty"
            assert event.description, "Life event description must be non-empty"

    def test_regional_contexts_valid(self):
        assert len(_REGIONAL_CONTEXTS) == 8
        for ctx in _REGIONAL_CONTEXTS:
            assert isinstance(ctx, RegionalContext)
            assert ctx.setting in {"rural", "urban", "suburban", "peri-urban"}
            assert ctx.connectivity in {"reliable", "intermittent", "limited"}
            assert ctx.country_context, "Country context must be non-empty"

    def test_injection_probability_in_range(self):
        assert 0.0 < _LIFE_EVENT_INJECTION_PROBABILITY < 1.0
        assert _LIFE_EVENT_INJECTION_PROBABILITY == pytest.approx(0.4)
