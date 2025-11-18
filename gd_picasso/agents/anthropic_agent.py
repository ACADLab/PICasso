"""
Anthropic Claude API Agent.
"""

from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not available. Install with: pip install anthropic")


class AnthropicInferenceAgent:
    """
    Anthropic Claude API agent.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        """
        Initialize Anthropic Claude API agent.
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name (e.g., 'claude-sonnet-4-20250514' for Sonnet 4.5)
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package not available. Install with: pip install anthropic"
            )
        
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.hist: List[dict] = []
        
        logger.info(f"Initialized Anthropic agent with model: {model}")
    
    def _call(self, system_prompt: str, user_message: str) -> str:
        """Make API call to Anthropic."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            # Anthropic returns a Message object with content as a list
            if message.content and len(message.content) > 0:
                # Content is a list of TextBlock objects
                return message.content[0].text
            return ""
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
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
        return self._call(system_prompt, user_q)
    
    def ask_llm(self, system_prompt: str, user_q: str) -> str:
        """Alias for ASK_LLM (lowercase)."""
        return self.ASK_LLM(system_prompt, user_q)
    
    def start_new_conversation(self):
        """Reset conversation history."""
        self.hist = []


