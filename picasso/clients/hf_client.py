"""HuggingFace Inference API-backed chat client."""
from __future__ import annotations

from typing import Dict, Sequence
from ..errors import ClientError
from ..config import HFConfig
from .base import ChatClient, Messages

try:
    from huggingface_hub import InferenceClient  # type: ignore
except Exception:  # pragma: no cover
    InferenceClient = None  # type: ignore


class HFClient(ChatClient):
    def __init__(self, config: HFConfig | None = None):
        self.config = config or HFConfig.from_env()
        self.model = self.config.repository
        if InferenceClient is None:
            raise ClientError(
                "huggingface-hub not installed. `pip install huggingface-hub`."
            )
        self._client = InferenceClient(
            model=self.config.repository,
            token=self.config.api_token,
        )

    def complete(self, messages: Messages, **gen_params) -> str:
        try:
            # Inference API uses a simple text-in/text-out interface; we stitch messages.
            prompt = ""
            for m in messages:
                role = m["role"].upper()
                prompt += f"[{role}] {m['content']}\n"
            # "messages" param is also supported by client.chat.completions, but keep simple.
            resp = self._client.text_generation(prompt, **gen_params)
            return str(resp)
        except Exception as e:  # pragma: no cover
            raise ClientError(f"HuggingFace completion failed: {e}")

    def test_connection(self) -> bool:
        try:
            _ = self.complete([{"role": "user", "content": "ping"}], max_new_tokens=1)
            return True
        except Exception:
            return False
