"""
Google Gemini API Agent.
"""

from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai package not available. Install with: pip install google-generativeai")


class GeminiInferenceAgent:
    """
    Google Gemini API agent.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-exp"
    ):
        """
        Initialize Google Gemini API agent.
        
        Args:
            api_key: Google API key (defaults to GEMINI_API_KEY env var)
            model: Model name (e.g., 'gemini-2.0-flash-exp', 'gemini-2.5-pro')
        """
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai package not available. Install with: pip install google-generativeai"
            )
        
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Google API key not provided. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(model)
        self.hist: List[dict] = []
        
        logger.info(f"Initialized Gemini agent with model: {model}")
    
    def _call(self, system_prompt: str, user_message: str) -> str:
        """Make API call to Gemini."""
        import time
        
        max_retries = 3
        base_delay = 5.0
        
        for attempt in range(max_retries):
            try:
                # Combine system prompt and user message
                full_prompt = f"{system_prompt}\n\n{user_message}"
                
                response = self.client.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 2048,
                    },
                    safety_settings=[
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    ]
                )
                
                # Check if response was blocked
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if candidate.finish_reason == 2:  # SAFETY
                        logger.warning(f"Gemini response blocked by safety filter (attempt {attempt + 1})")
                        if attempt < max_retries - 1:
                            time.sleep(base_delay * (attempt + 1))
                            continue
                        raise RuntimeError("Gemini response blocked by safety filter after retries")
                    
                    if hasattr(candidate, 'content') and candidate.content:
                        return candidate.content.parts[0].text
                
                # Try response.text as fallback
                if hasattr(response, 'text') and response.text:
                    return response.text
                
                # If no text, check for blocked reason
                if response.candidates and len(response.candidates) > 0:
                    finish_reason = response.candidates[0].finish_reason
                    if finish_reason == 2:
                        raise RuntimeError("Response blocked by safety filter")
                
                return ""
                
            except Exception as e:
                error_str = str(e)
                # Check for quota/rate limit errors
                is_quota = "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower()
                is_safety = "safety" in error_str.lower() or "blocked" in error_str.lower()
                
                if (is_quota or is_safety) and attempt < max_retries - 1:
                    # Extract retry delay if provided
                    delay = base_delay * (2 ** attempt)
                    if "retry in" in error_str.lower():
                        # Try to extract delay from error message
                        import re
                        match = re.search(r'retry in ([\d.]+)s', error_str.lower())
                        if match:
                            delay = float(match.group(1)) + 1  # Add 1 second buffer
                    
                    logger.warning(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {error_str[:100]}. Waiting {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Gemini API call failed: {e}")
                    raise
        
        raise RuntimeError(f"Gemini API call failed after {max_retries} attempts")
    
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

