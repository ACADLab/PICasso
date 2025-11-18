"""
DeepSeek API Agent - OpenAI-compatible interface for DeepSeek models.
"""

from typing import List, Optional
from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)


class DeepSeekInferenceAgent:
    """
    DeepSeek API agent using OpenAI-compatible interface.
    
    DeepSeek API is compatible with OpenAI's API format, so we can use
    the OpenAI client with a custom base_url.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1"
    ):
        """
        Initialize DeepSeek API agent.
        
        Args:
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            model: Model name ('deepseek-chat' for R1, 'deepseek-reasoner' for V3)
            base_url: API base URL
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError(
                "DeepSeek API key not provided. Set DEEPSEEK_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model
        self.base_url = base_url
        
        # Initialize OpenAI client with DeepSeek's base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url
        )
        
        self.hist: List[dict] = []
        logger.info(f"Initialized DeepSeek agent with model: {model}")
    
    def _call(self, messages: List[dict]) -> str:
        """Make API call to DeepSeek."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}")
            raise
    
    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        """
        Single-shot LLM query.
        
        Args:
            system_prompt: System instructions
            user_q: User query
            
        Returns:
            Model response
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_q}
        ]
        return self._call(messages)
    
    def ask_llm(self, system_prompt: str, user_q: str) -> str:
        """Alias for ASK_LLM (lowercase)."""
        return self.ASK_LLM(system_prompt, user_q)
    
    def start_new_conversation(self):
        """Reset conversation history."""
        self.hist = []


