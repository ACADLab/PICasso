"""
HuggingFace Inference API Client for Photonic Circuit Generation

This module provides a cloud-based LLM interface using HuggingFace Inference API.
NO local model downloads required - all inference happens via API calls.
"""

from typing import List, Optional
from huggingface_hub import InferenceClient
import logging
from .config import HF_API_TOKEN, DEFAULT_MODEL, MODEL_PARAMS

logger = logging.getLogger(__name__)


class HFInferenceAgent:
    """
    Cloud-based LLM agent using HuggingFace Inference API.

    This agent makes API calls to HuggingFace's hosted models, requiring
    only an API token - no local model downloads or GPU required.

    Args:
        api_token: HuggingFace API token (get from hf.co/settings/tokens)
        model: Model ID on HuggingFace Hub
        **gen_params: Override default generation parameters
    """

    def __init__(
        self,
        api_token: str = HF_API_TOKEN,
        model: str = DEFAULT_MODEL,
        **gen_params
    ):
        if api_token == "ENTER_YOUR_HF_TOKEN_HERE":
            raise ValueError(
                "Please set your HuggingFace API token in config.py or "
                "set the HF_API_TOKEN environment variable. "
                "Get your token from https://huggingface.co/settings/tokens"
            )

        # Use new HuggingFace inference endpoint (router-based)
        # Old endpoint: https://api-inference.huggingface.co (deprecated)
        # New endpoint: https://router.huggingface.co/hf-inference
        self.client = InferenceClient(token=api_token)
        self.model = model
        self.gen_params = {**MODEL_PARAMS, **gen_params}
        self.hist: List[dict] = []

        logger.info(f"Initialized HFInferenceAgent with model: {model}")
        logger.info(f"Using HuggingFace Inference API (new router endpoint)")
        logger.info(f"Generation params: {self.gen_params}")

    def _format_prompt(self, system_prompt: str, user_query: str) -> str:
        """
        Format system and user prompts for the model.

        Different models use different chat templates. This method handles
        the most common format (Alpaca-style).
        """
        # DeepSeek-Coder and Qwen2.5-Coder use this format:
        prompt = f"### Instruction:\n{system_prompt}\n\n### Input:\n{user_query}\n\n### Response:\n"
        return prompt

    def _call(self, prompt: str) -> str:
        """Make API call to HuggingFace Inference endpoint (backward compatible)."""
        import time
        
        max_retries = 5  # Increased retries for rate limits
        base_delay = 5.0  # Start with 5 seconds
        
        for attempt in range(max_retries):
            try:
                # Try chat.completions.create (for models like Kimi2 that use this format)
                if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
                    try:
                        # Build model name with provider if specified (e.g., "moonshotai/Kimi-K2-Thinking:novita")
                        model_name = self.model
                        if self.provider:
                            model_name = f"{self.model}:{self.provider}"
                        
                        # Note: For models with provider tags (e.g., :novita), HuggingFace routes
                        # through the provider's API. The URL will show the provider (e.g., /novita/v3/openai/...)
                        # This is expected behavior - HuggingFace acts as a router/proxy.
                        response = self.client.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=self.gen_params.get('max_new_tokens', 2048),
                            temperature=self.gen_params.get('temperature', 0.3),
                            top_p=self.gen_params.get('top_p', 0.95)
                        )
                        if hasattr(response, 'choices') and len(response.choices) > 0:
                            return response.choices[0].message.content
                        return str(response)
                    except Exception as e:
                        error_str = str(e)
                        # Check if it's a timeout/rate limit that we should retry
                        is_rate_limit = "429" in error_str or "rate_limit" in error_str.lower() or "too many requests" in error_str.lower()
                        is_timeout = "504" in error_str or "timeout" in error_str.lower() or "503" in error_str or "502" in error_str
                        
                        if (is_rate_limit or is_timeout) and attempt < max_retries - 1:
                            # Longer delay for rate limits
                            if is_rate_limit:
                                delay = base_delay * (3 ** attempt)  # Exponential: 5s, 15s, 45s, 135s
                                logger.warning(f"API rate limit (attempt {attempt + 1}/{max_retries}): {error_str[:100]}. Waiting {delay}s...")
                            else:
                                delay = base_delay * (2 ** attempt)  # Exponential: 5s, 10s, 20s, 40s
                                logger.warning(f"API timeout/error (attempt {attempt + 1}/{max_retries}): {error_str[:100]}. Retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                        logger.debug(f"chat.completions.create failed: {e}, trying chat_completion...")
                
                # Try chat_completion (newer API)
                if hasattr(self.client, 'chat_completion'):
                    response = self.client.chat_completion(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=self.gen_params.get('max_new_tokens', 2048),
                        temperature=self.gen_params.get('temperature', 0.3),
                        top_p=self.gen_params.get('top_p', 0.95)
                    )
                    if hasattr(response, 'choices') and len(response.choices) > 0:
                        return response.choices[0].message.content
                    return str(response)

                # Fallback to direct HTTP request (works with any version)
                else:
                    import requests

                    url = f"https://api-inference.huggingface.co/models/{self.model}"
                    headers = {"Authorization": f"Bearer {self.client.token}"}
                    payload = {
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": self.gen_params.get('max_new_tokens', 2048),
                            "temperature": self.gen_params.get('temperature', 0.3),
                            "top_p": self.gen_params.get('top_p', 0.95),
                            "do_sample": self.gen_params.get('do_sample', True),
                            "return_full_text": False
                        }
                    }

                    response = requests.post(url, headers=headers, json=payload, timeout=120)
                    response.raise_for_status()
                    result = response.json()

                    if isinstance(result, list) and len(result) > 0:
                        return result[0].get('generated_text', str(result))
                    elif isinstance(result, dict):
                        return result.get('generated_text', str(result))
                    return str(result)
                    
            except Exception as e:
                error_str = str(e)
                # Retry on timeout/rate limit errors
                is_rate_limit = "429" in error_str or "rate_limit" in error_str.lower() or "too many requests" in error_str.lower()
                is_timeout = "504" in error_str or "timeout" in error_str.lower() or "503" in error_str or "502" in error_str
                
                if (is_rate_limit or is_timeout) and attempt < max_retries - 1:
                    # Longer delay for rate limits
                    if is_rate_limit:
                        delay = base_delay * (3 ** attempt)  # Exponential: 5s, 15s, 45s, 135s
                        logger.warning(f"API rate limit (attempt {attempt + 1}/{max_retries}): {error_str[:100]}. Waiting {delay}s...")
                    else:
                        delay = base_delay * (2 ** attempt)  # Exponential: 5s, 10s, 20s, 40s
                        logger.warning(f"API error (attempt {attempt + 1}/{max_retries}): {error_str[:100]}. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"API call failed after {attempt + 1} attempts: {e}")
                    raise RuntimeError(f"HuggingFace Inference API error: {e}")
        
        # If we get here, all retries failed
        raise RuntimeError(f"HuggingFace Inference API error: All {max_retries} retry attempts failed")

    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        """
        Single-shot LLM query (no conversation history).

        Args:
            system_prompt: Instructions for the model
            user_q: Problem description or query

        Returns:
            Generated response (code or JSON)
        """
        prompt = self._format_prompt(system_prompt, user_q)
        response = self._call(prompt)

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

        # Build full conversational prompt
        full_prompt = self._build_conversation_prompt()
        answer = self._call(full_prompt)

        self.hist.append({"role": "assistant", "content": answer})

        logger.debug(f"Iterative query completed. History length: {len(self.hist)}")
        return answer

    def _build_conversation_prompt(self) -> str:
        """Build prompt from conversation history."""
        prompt_parts = []

        for msg in self.hist:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                prompt_parts.append(f"### Instruction:\n{content}\n")
            elif role == "user":
                prompt_parts.append(f"### Input:\n{content}\n")
            elif role == "assistant":
                prompt_parts.append(f"### Response:\n{content}\n")

        # Add final response marker
        prompt_parts.append("### Response:\n")

        return "\n".join(prompt_parts)

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


class HFInferenceAgentWithRetry(HFInferenceAgent):
    """
    Extended agent with built-in retry logic and error handling.

    Useful for handling temporary API errors or rate limits.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _call_with_retry(self, prompt: str) -> str:
        """Call API with automatic retry on failure."""
        import time

        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._call(prompt)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        raise RuntimeError(f"API call failed after {self.max_retries} attempts: {last_error}")

    def _call(self, prompt: str) -> str:
        """Override to use retry logic."""
        return self._call_with_retry(prompt)


# Convenience function for quick testing
def test_hf_client(api_token: str = None):
    """
    Test HuggingFace Inference API connection.

    Usage:
        from hf_api_client import test_hf_client
        test_hf_client()
    """
    if api_token is None:
        api_token = HF_API_TOKEN

    print("Testing HuggingFace Inference API...")
    print(f"Model: {DEFAULT_MODEL}")

    try:
        agent = HFInferenceAgent(api_token=api_token)

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
        print("1. Check your HF_API_TOKEN in config.py")
        print("2. Verify token at https://huggingface.co/settings/tokens")
        print("3. Ensure you have access to the model")
        return False


if __name__ == "__main__":
    # Run test if executed directly
    test_hf_client()
