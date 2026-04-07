"""
Conversation memory for LLM interactions.

Manages per-student message history with turn limits for future
LLM-augmented simulation mode. Follows project immutability convention:
add_message() and clear() return new instances.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TURNS: int = 20
_VALID_ROLES: frozenset[str] = frozenset({"system", "user", "assistant"})


@dataclass(frozen=True)
class Message:
    """A single message in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class ConversationMemory:
    """Immutable conversation history with turn-based eviction.

    System messages are always retained. When turn limit is exceeded,
    oldest non-system messages are evicted first.
    """

    max_turns: int = _DEFAULT_MAX_TURNS
    _messages: tuple[Message, ...] = ()  # Use tuple for true immutability

    def add_message(self, role: str, content: str) -> ConversationMemory:
        """Return a NEW ConversationMemory with the message appended."""
        if role not in _VALID_ROLES:
            raise ValueError(
                f"Invalid role {role!r}. Must be one of {sorted(_VALID_ROLES)}"
            )
        new_msg = Message(role=role, content=content)
        new_messages = (*self._messages, new_msg)

        # Enforce turn limit: count user+assistant pairs
        system = tuple(m for m in new_messages if m.role == "system")
        non_system = tuple(m for m in new_messages if m.role != "system")
        max_non_system = self.max_turns * 2  # each turn = user + assistant
        if len(non_system) > max_non_system:
            non_system = non_system[-max_non_system:]

        return ConversationMemory(
            max_turns=self.max_turns,
            _messages=(*system, *non_system),
        )

    def get_history(self) -> list[dict[str, str]]:
        """Return messages in OpenAI API format."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def clear(self) -> ConversationMemory:
        """Return a new empty ConversationMemory with same settings."""
        return ConversationMemory(max_turns=self.max_turns)

    @property
    def turn_count(self) -> int:
        """Number of user messages (each representing one turn)."""
        return sum(1 for m in self._messages if m.role == "user")

    @property
    def message_count(self) -> int:
        """Total number of messages including system."""
        return len(self._messages)

