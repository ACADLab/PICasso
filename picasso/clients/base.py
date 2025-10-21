"""Client interfaces for text-generation backends."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Sequence


Messages = Sequence[Dict[str, str]]  # [{"role": "...", "content": "..."}]


class ChatClient(Protocol):
    """Minimal synchronous chat-completion interface."""

    model: str

    def complete(self, messages: Messages, **gen_params) -> str:
        """Return the assistant message content."""

    def test_connection(self) -> bool:
        """Return True if the remote service is reachable."""


@dataclass
class Conversation:
    """Lightweight conversation helper used by the generator + retry policy."""
    client: ChatClient
    history: List[Dict[str, str]]

    @classmethod
    def start(cls, client: ChatClient, system_prompt: Optional[str] = None) -> "Conversation":
        hist: List[Dict[str, str]] = []
        if system_prompt:
            hist.append({"role": "system", "content": system_prompt})
        return cls(client=client, history=hist)

    def ask(self, user_content: str, **gen_params) -> str:
        self.history.append({"role": "user", "content": user_content})
        reply = self.client.complete(self.history, **gen_params)
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def append_feedback(self, feedback: str) -> None:
        self.history.append({"role": "system", "content": f"Validation feedback:\n{feedback}"})
