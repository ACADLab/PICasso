"""OpenAI-backed chat client with the `ChatClient` interface."""
from __future__ import annotations

import os
from typing import Dict, Sequence
from ..errors import ClientError
from ..config import OpenAIConfig
from .base import ChatClient, Messages

try:
    # Using the official OpenAI SDK v1 style import path if available.
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class OpenAIClient(ChatClient):
    def __init__(self, config: OpenAIConfig | None = None):
        self.config = config or OpenAIConfig.from_env()
        self.model = self.config.model

        if OpenAI is None:
            raise ClientError(
                "openai package not installed. `pip install openai` to use this client."
            )
        self._client = OpenAI(api_key=self.config.api_key)

    def complete(self, messages: Messages, **gen_params) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=list(messages),
                **gen_params,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # pragma: no cover
            raise ClientError(f"OpenAI completion failed: {e}")

    def test_connection(self) -> bool:
        try:
            _ = self.complete([{"role": "user", "content": "ping"}], max_tokens=1)
            return True
        except Exception:
            return False
