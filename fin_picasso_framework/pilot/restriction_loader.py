"""
Restriction Loader

Loads design restrictions from configuration and generates restriction rules for prompts.
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class RestrictionLoader:
    """Loads and manages design restrictions."""

    def __init__(self, restrictions_file: Optional[Path] = None):
        """
        Initialize restriction loader.

        Args:
            restrictions_file: Optional path to restrictions file
        """
        self.restrictions_file = restrictions_file
        self.restrictions = self._load_default_restrictions()

    def _load_default_restrictions(self) -> Dict:
        """Load default design restrictions."""
        return {
            "port_restrictions": [
                "Each port can only be connected once",
                "Ports must be labeled o1, o2, o3, ... clockwise",
                "Use exact port names from component API",
            ],
            "component_restrictions": [
                "Use ONLY GDSFactory library components",
                "Do not create custom component names",
                "Use exact component IDs specified in problem",
            ],
            "routing_restrictions": [
                "Use route_bundle for multiple connections (not route_single)",
                "Minimum bend radius: 15µm",
                "Route separation: >= 15µm",
                "Minimum component spacing: 80µm (150µm for complex designs)",
            ],
            "code_restrictions": [
                "Use ONLY ASCII characters (no Unicode)",
                "Use single quotes for strings",
                "No comments in code",
                "All numbers must be valid Python floats",
            ],
            "mirror_restrictions": [
                "Call mirror() AFTER add_ref(), never before",
                "Pattern: ref = c.add_ref(component); ref.mirror()",
            ],
        }

    def load_from_file(self, file_path: Path) -> bool:
        """
        Load restrictions from file.

        Args:
            file_path: Path to restrictions file

        Returns:
            True if loaded successfully
        """
        try:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    loaded = json.load(f)
                    self.restrictions.update(loaded)
                logger.info(f"Loaded restrictions from {file_path}")
                return True
        except Exception as e:
            logger.warning(f"Could not load restrictions from {file_path}: {e}")
        return False

    def get_restrictions(self, category: Optional[str] = None) -> Dict:
        """
        Get restrictions.

        Args:
            category: Optional category to filter by

        Returns:
            Restrictions dictionary
        """
        if category:
            return self.restrictions.get(category, {})
        return self.restrictions

    def generate_restriction_text(self, categories: Optional[List[str]] = None) -> str:
        """
        Generate restriction text for LLM prompts.

        Args:
            categories: Optional list of categories to include

        Returns:
            Formatted restriction text
        """
        if categories is None:
            categories = list(self.restrictions.keys())
        
        lines = []
        lines.append("DESIGN RESTRICTIONS:")
        lines.append("")
        
        for category in categories:
            if category in self.restrictions:
                restrictions = self.restrictions[category]
                if isinstance(restrictions, list):
                    lines.append(f"{category.replace('_', ' ').title()}:")
                    for restriction in restrictions:
                        lines.append(f"  - {restriction}")
                    lines.append("")
        
        return "\n".join(lines)

    def add_restriction(self, category: str, restriction: str):
        """
        Add a restriction.

        Args:
            category: Restriction category
            restriction: Restriction text
        """
        if category not in self.restrictions:
            self.restrictions[category] = []
        
        if restriction not in self.restrictions[category]:
            self.restrictions[category].append(restriction)


