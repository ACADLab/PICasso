"""Orchestrates generation + validation for PICasso."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, List, Dict, Optional, Sequence

from .clients.base import ChatClient, Conversation
from .clients.openai_client import OpenAIClient
from .clients.hf_client import HFClient
from .validators.base import Validator
from .validators.drc import DRCValidator
from .validators.pnr import PNRValidator
from .validators.sax import SAXValidator
from .retry import RetryPolicy, RetryResult
from .utils.logging_utils import configure_logging
import logging


_LOG = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a senior photonic circuit designer. "
    "Generate clean Python code that uses gdsfactory to build the requested design. "
    "Always include import statements, define a `build()` function that returns a `gf.Component`, "
    "and avoid crossing routes. Prefer large bend radius and proper spacing."
)


@dataclass
class PICasso:
    client: ChatClient
    validators: List[Validator] = field(default_factory=lambda: [PNRValidator(), DRCValidator(), SAXValidator()])
    retry: RetryPolicy = field(default_factory=lambda: RetryPolicy(max_attempts=3))

    @classmethod
    def with_openai(cls) -> "PICasso":
        return cls(client=OpenAIClient())

    @classmethod
    def with_huggingface(cls) -> "PICasso":
        return cls(client=HFClient())

    def generate(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> RetryResult:
        configure_logging()  # idempotent
        convo = Conversation.start(self.client, system_prompt=system_prompt)
        _LOG.info("Starting generation with %d validators and %d max attempts",
                  len(self.validators), self.retry.max_attempts)
        result = self.retry.run(convo, prompt, validators=self.validators)
        if result.success:
            _LOG.info("Generation succeeded in %d attempt(s).", len(result.attempts))
        else:
            _LOG.warning("Generation failed after %d attempt(s).", len(result.attempts))
        return result
