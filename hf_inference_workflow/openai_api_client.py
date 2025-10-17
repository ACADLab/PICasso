"""
OpenAI API Client for Photonic Circuit Generation

This module provides a cloud-based LLM interface using OpenAI API.
Drop-in replacement for HFInferenceAgent with same interface.
NO local model downloads required - all inference happens via API calls.
"""

from typing import List, Optional
from openai import OpenAI
import logging
import os

logger = logging.getLogger(__name__)


class OpenAIInferenceAgent:
    """
    Cloud-based LLM agent using OpenAI API (gpt-4o-mini).

    This agent makes API calls to OpenAI's hosted models, requiring
    only an API token - no local model downloads or GPU required.

    Args:
        api_key: OpenAI API key (get from platform.openai.com/api-keys)
        model: Model ID (default: gpt-4o-mini for cost-optimized code generation)
        **gen_params: Override default generation parameters
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o-mini",
        **gen_params
    ):
        # Get API key from parameter or environment variable
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key == "ENTER_YOUR_OPENAI_KEY_HERE":
            raise ValueError(
                "Please set your OpenAI API key in config.py or "
                "set the OPENAI_API_KEY environment variable. "
                "Get your token from https://platform.openai.com/api-keys"
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model

        # Default generation parameters optimized for code generation
        default_params = {
            "temperature": 0.3,      # Lower for more deterministic code
            "max_tokens": 2048,      # Sufficient for photonic circuit code
            "top_p": 0.95,
        }
        self.gen_params = {**default_params, **gen_params}

        self.hist: List[dict] = []

        logger.info(f"Initialized OpenAIInferenceAgent with model: {model}")
        logger.info(f"Generation params: {self.gen_params}")

    def _call(self, messages: List[dict]) -> str:
        """Make API call to OpenAI endpoint with rate limit handling."""
        import time

        max_retries = 5
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **self.gen_params
                )

                # Extract generated text
                return response.choices[0].message.content

            except Exception as e:
                error_str = str(e)

                # Handle rate limit errors (429)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit. Waiting {delay}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Max retries reached for rate limit")
                        raise RuntimeError(f"Rate limit exceeded after {max_retries} attempts")

                # Other errors - fail immediately
                logger.error(f"OpenAI API call failed: {e}")
                raise RuntimeError(f"OpenAI API error: {e}")

        raise RuntimeError("API call failed after all retries")

    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        """
        Single-shot LLM query (no conversation history).

        Args:
            system_prompt: Instructions for the model
            user_q: Problem description or query

        Returns:
            Generated response (code or JSON)
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_q}
        ]

        response = self._call(messages)
        logger.debug(f"Single-shot query completed. Response length: {len(response)}")
        return response

    def ASK_LLM_iterate(
        self,
        system_prompt: str,
        user_q: str,
        clear_context: bool = False
    ) -> str:
        """
        Multi-turn conversation with history tracking.

        Useful for iterative refinement with validation feedback.

        Args:
            system_prompt: Instructions for the model
            user_q: Query or feedback
            clear_context: Reset conversation history if True

        Returns:
            Generated response
        """
        if clear_context or not self.hist:
            self.hist = [
                {"role": "system", "content": system_prompt}
            ]

        self.hist.append({"role": "user", "content": user_q})

        # Make API call with full conversation history
        answer = self._call(self.hist)

        self.hist.append({"role": "assistant", "content": answer})

        logger.debug(f"Iterative query completed. History length: {len(self.hist)}")
        return answer

    def start_new_conversation(self):
        """Reset conversation history."""
        self.hist = []
        logger.debug("Conversation history cleared")

    def get_model_info(self) -> dict:
        """Get information about the current model."""
        return {
            "model": self.model,
            "generation_params": self.gen_params,
            "conversation_length": len(self.hist)
        }


class OpenAIInferenceAgentWithRetry(OpenAIInferenceAgent):
    """
    Extended agent with built-in retry logic and error handling.

    Useful for handling temporary API errors or rate limits.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0, **kwargs):
        super().__init__(**kwargs)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _call_with_retry(self, messages: List[dict]) -> str:
        """Call API with automatic retry on failure."""
        import time

        last_error = None
        for attempt in range(self.max_retries):
            try:
                return super()._call(messages)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        raise RuntimeError(f"API call failed after {self.max_retries} attempts: {last_error}")

    def _call(self, messages: List[dict]) -> str:
        """Override to use retry logic."""
        return self._call_with_retry(messages)


# Convenience function for quick testing
def test_openai_client(api_key: str = None):
    """
    Test OpenAI API connection.

    Usage:
        from openai_api_client import test_openai_client
        test_openai_client()
    """
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")

    print("Testing OpenAI API...")
    print(f"Model: gpt-4o-mini")

    try:
        agent = OpenAIInferenceAgent(api_key=api_key)

        # Simple test query
        response = agent.ASK_LLM(
            system_prompt="You are a helpful coding assistant.",
            user_q="Write a Python function that adds two numbers."
        )

        print("\n✅ API connection successful!")
        print(f"\nResponse (first 200 chars):\n{response[:200]}...")
        return True

    except Exception as e:
        print(f"\n❌ API connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check your OPENAI_API_KEY in config.py")
        print("2. Verify token at https://platform.openai.com/api-keys")
        print("3. Ensure you have API credits available")
        return False


if __name__ == "__main__":
    # Run test if executed directly
    test_openai_client()
