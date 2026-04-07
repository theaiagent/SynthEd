"""Tests for ConversationMemory and LLM streaming."""

from __future__ import annotations

import pytest

from synthed.utils.llm_memory import (
    Message,
    ConversationMemory,
    _DEFAULT_MAX_TURNS,
)


class TestMessage:
    def test_frozen_message(self):
        """Message is immutable (frozen dataclass)."""
        msg = Message(role="user", content="hello")
        with pytest.raises(AttributeError):
            msg.role = "assistant"
        with pytest.raises(AttributeError):
            msg.content = "changed"


class TestConversationMemory:
    def test_empty_memory(self):
        """New memory has 0 messages and 0 turns."""
        mem = ConversationMemory()
        assert mem.message_count == 0
        assert mem.turn_count == 0

    def test_add_message_returns_new_instance(self):
        """Original unchanged, new has the message."""
        original = ConversationMemory()
        updated = original.add_message("user", "hello")
        assert original.message_count == 0
        assert updated.message_count == 1

    def test_add_message_immutability(self):
        """Original._messages unchanged after add."""
        original = ConversationMemory()
        original.add_message("user", "hello")
        assert original._messages == ()

    def test_get_history_format(self):
        """Returns list of {'role': ..., 'content': ...} dicts."""
        mem = ConversationMemory().add_message("user", "hi")
        history = mem.get_history()
        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "hi"}

    def test_get_history_preserves_order(self):
        """Messages come back in insertion order."""
        mem = (
            ConversationMemory()
            .add_message("system", "You are helpful.")
            .add_message("user", "Hello")
            .add_message("assistant", "Hi there!")
        )
        history = mem.get_history()
        assert [m["role"] for m in history] == ["system", "user", "assistant"]
        assert history[0]["content"] == "You are helpful."
        assert history[1]["content"] == "Hello"
        assert history[2]["content"] == "Hi there!"

    def test_max_turns_enforced(self):
        """Beyond max_turns, oldest non-system messages dropped."""
        mem = ConversationMemory(max_turns=2)
        # Add 3 full turns (user + assistant each)
        mem = mem.add_message("user", "turn1")
        mem = mem.add_message("assistant", "resp1")
        mem = mem.add_message("user", "turn2")
        mem = mem.add_message("assistant", "resp2")
        mem = mem.add_message("user", "turn3")
        mem = mem.add_message("assistant", "resp3")
        # max_turns=2 means max 4 non-system messages
        history = mem.get_history()
        non_system = [m for m in history if m["role"] != "system"]
        assert len(non_system) <= 4
        # Oldest turn should be evicted
        contents = [m["content"] for m in non_system]
        assert "turn1" not in contents
        assert "resp1" not in contents
        assert "turn3" in contents
        assert "resp3" in contents

    def test_system_messages_preserved_on_eviction(self):
        """System messages survive turn eviction."""
        mem = ConversationMemory(max_turns=1)
        mem = mem.add_message("system", "You are a tutor.")
        mem = mem.add_message("user", "turn1")
        mem = mem.add_message("assistant", "resp1")
        mem = mem.add_message("user", "turn2")
        mem = mem.add_message("assistant", "resp2")
        history = mem.get_history()
        roles = [m["role"] for m in history]
        assert "system" in roles
        system_msgs = [m for m in history if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "You are a tutor."

    def test_clear_returns_empty(self):
        """Cleared memory has same max_turns, zero messages."""
        mem = ConversationMemory(max_turns=10)
        mem = mem.add_message("user", "hello")
        cleared = mem.clear()
        assert cleared.message_count == 0
        assert cleared.turn_count == 0
        assert cleared.max_turns == 10

    def test_turn_count_accuracy(self):
        """Counts only user messages."""
        mem = (
            ConversationMemory()
            .add_message("system", "sys")
            .add_message("user", "q1")
            .add_message("assistant", "a1")
            .add_message("user", "q2")
            .add_message("assistant", "a2")
        )
        assert mem.turn_count == 2

    def test_message_count_includes_all(self):
        """Counts system + user + assistant."""
        mem = (
            ConversationMemory()
            .add_message("system", "sys")
            .add_message("user", "q1")
            .add_message("assistant", "a1")
        )
        assert mem.message_count == 3

    def test_default_max_turns(self):
        """Verify _DEFAULT_MAX_TURNS == 20."""
        assert _DEFAULT_MAX_TURNS == 20
        mem = ConversationMemory()
        assert mem.max_turns == 20

    def test_invalid_role_raises(self):
        """Invalid role string raises ValueError."""
        mem = ConversationMemory()
        with pytest.raises(ValueError, match="Invalid role"):
            mem.add_message("assistent", "typo")
        with pytest.raises(ValueError, match="Invalid role"):
            mem.add_message("admin", "nope")

    def test_frozen_memory(self):
        """ConversationMemory is immutable."""
        mem = ConversationMemory()
        with pytest.raises(AttributeError):
            mem.max_turns = 10
        with pytest.raises(AttributeError):
            mem._messages = ()

