"""
OpenAI API agent wrapper for gd_picasso.
"""

from typing import List, Optional
from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)


class OpenAIInferenceAgent:
    """
    OpenAI API agent using `openai.OpenAI`.
    Supports direct OpenAI keys and OpenRouter keys via OPENROUTER_API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        self.model = model
        self.openrouter_key = os.getenv("OPENROUTER_API")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key and not self.openrouter_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY or OPENROUTER_API environment variable."
            )

        self.backend = "openrouter" if self.openrouter_key else "openai"
        try:
            self.temperature = float(os.getenv("GD_PICASSO_LLM_TEMPERATURE", "0.5"))
        except ValueError:
            self.temperature = 0.5
        if self.openrouter_key:
            self.client = OpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/v1"
            )
        else:
            self.client = OpenAI(api_key=self.api_key)

        self.hist: List[dict] = []
        logger.info(f"Initialized OpenAI agent with model: {model} backend: {self.backend}")

    def _call(self, messages: List[dict]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=2048,
            )
        except Exception as e:
            err = str(e).lower()
            if "unsupported parameter" in err and "max_tokens" in err:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_completion_tokens=2048,
                )
            else:
                logger.error(f"OpenAI API call failed: {e}")
                raise

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and getattr(choice.message, "content", None) is not None:
                return choice.message.content
            if hasattr(choice, "text") and choice.text is not None:
                return choice.text

        return ""

    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_q},
        ]
        return self._call(messages)

    def ask_llm(self, system_prompt: str, user_q: str) -> str:
        return self.ASK_LLM(system_prompt, user_q)

    def start_new_conversation(self):
        self.hist = []
