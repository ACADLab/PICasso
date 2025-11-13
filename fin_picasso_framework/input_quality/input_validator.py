"""
Input Quality Validator

Pre-inference validation of problem descriptions to ensure high-quality inputs.
Validates formatting, checks for hallucination triggers, and ensures unambiguous specifications.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class InputValidator:
    """Validates problem descriptions before LLM inference."""

    def __init__(self):
        """Initialize input validator."""
        self.unicode_patterns = [
            r'[\u00B5-\u00B5]',  # Micro symbol (µ)
            r'[\u00D7-\u00D7]',  # Multiplication sign (×)
            r'[\u2192-\u2192]',  # Right arrow (→)
            r'[\u0394-\u0394]',  # Delta (Δ)
            r'[\u03BC-\u03BC]',  # Greek mu (μ)
        ]
        
        # Common hallucination triggers
        self.hallucination_triggers = [
            r'\b(?:maybe|perhaps|possibly|might|could be)\b',
            r'\b(?:unsure|uncertain|unclear|ambiguous)\b',
            r'\b(?:similar to|like|resembling)\b.*\b(?:but|however|except)\b',
        ]
        
        # Conflicting spec patterns
        self.conflicting_patterns = [
            (r'\b(?:minimum|min)\b.*\b(?:maximum|max)\b', 'min/max conflict'),
            (r'\b(?:single|one)\b.*\b(?:multiple|many|several)\b', 'count conflict'),
            (r'\b(?:input|in)\b.*\b(?:output|out)\b.*\b(?:same|identical)\b', 'port conflict'),
        ]

    def validate(self, problem_text: str) -> Tuple[bool, List[str]]:
        """
        Validate problem description.

        Args:
            problem_text: Problem description text

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []
        
        # Check for unicode characters
        unicode_issues = self._check_unicode(problem_text)
        issues.extend(unicode_issues)
        
        # Check for hallucination triggers
        hallucination_issues = self._check_hallucination_triggers(problem_text)
        issues.extend(hallucination_issues)
        
        # Check for conflicting specifications
        conflict_issues = self._check_conflicting_specs(problem_text)
        issues.extend(conflict_issues)
        
        # Check formatting
        formatting_issues = self._check_formatting(problem_text)
        issues.extend(formatting_issues)
        
        is_valid = len(issues) == 0
        
        if not is_valid:
            logger.warning(f"Input validation found {len(issues)} issues")
        
        return is_valid, issues

    def _check_unicode(self, text: str) -> List[str]:
        """Check for unicode characters that should be ASCII."""
        issues = []
        
        for pattern in self.unicode_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(
                    f"Unicode character found: {matches[0]}. "
                    "Use ASCII equivalents (e.g., 'um' instead of 'µm', 'x' instead of '×')"
                )
        
        return issues

    def _check_hallucination_triggers(self, text: str) -> List[str]:
        """Check for ambiguous language that might cause hallucinations."""
        issues = []
        
        for pattern in self.hallucination_triggers:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                issues.append(
                    f"Ambiguous language detected: '{matches[0]}'. "
                    "Use specific, unambiguous specifications."
                )
        
        return issues

    def _check_conflicting_specs(self, text: str) -> List[str]:
        """Check for conflicting specifications."""
        issues = []
        
        for pattern, description in self.conflicting_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(
                    f"Conflicting specification detected: {description}. "
                    "Clarify the requirements."
                )
        
        return issues

    def _check_formatting(self, text: str) -> List[str]:
        """Check basic formatting issues."""
        issues = []
        
        # Check for empty or very short text
        if len(text.strip()) < 10:
            issues.append("Problem description is too short or empty")
        
        # Check for excessive whitespace
        if re.search(r'\n{4,}', text):
            issues.append("Excessive blank lines detected")
        
        # Check for missing component IDs
        if 'id:' in text.lower() or 'ids:' in text.lower():
            # Check if IDs are actually specified
            id_pattern = r'id[s]?:\s*([a-zA-Z0-9_]+)'
            if not re.search(id_pattern, text, re.IGNORECASE):
                issues.append("Component IDs mentioned but not properly specified")
        
        return issues

    def sanitize(self, problem_text: str) -> str:
        """
        Sanitize problem text by removing/fixing common issues.

        Args:
            problem_text: Original problem text

        Returns:
            Sanitized problem text
        """
        sanitized = problem_text
        
        # Replace unicode characters with ASCII equivalents
        replacements = {
            'µm': 'um',
            '×': 'x',
            '→': '->',
            'Δ': 'Delta',
            'μ': 'u',
        }
        
        for unicode_char, ascii_char in replacements.items():
            sanitized = sanitized.replace(unicode_char, ascii_char)
        
        # Normalize whitespace
        sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
        sanitized = re.sub(r' +', ' ', sanitized)
        
        return sanitized.strip()


