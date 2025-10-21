"""Centralized configuration and environment access."""
import os
from .utils.env import load_env
from dataclasses import dataclass
from .errors import ConfigError

load_env()

@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4o-mini"

    @staticmethod
    def from_env() -> "OpenAIConfig":
        key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not key or key == "ENTER_YOUR_OPENAI_KEY_HERE":
            raise ConfigError(
                "OPENAI_API_KEY is not set. Set it in your environment."
            )
        return OpenAIConfig(api_key=key, model=model)


@dataclass(frozen=True)
class HFConfig:
    api_token: str
    repository: str

    @staticmethod
    def from_env() -> "HFConfig":
        token = os.getenv("HF_API_TOKEN")
        repo = os.getenv("HF_REPOSITORY", "Qwen/Qwen2.5-Coder-7B-Instruct")
        if not token or token == "ENTER_YOUR_HF_TOKEN_HERE":
            raise ConfigError("HF_API_TOKEN is not set. Set it in your environment.")
        return HFConfig(api_token=token, repository=repo)
