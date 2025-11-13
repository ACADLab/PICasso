"""
SAX Knowledge Base

Provides SAX model information for LLM injection or system use.
Contains component-to-SAX-model mappings, model parameters, and usage examples.
"""

import logging
from typing import Dict, List, Optional
from .sax_model_manager import SAXModelManager
from ..config import SAX_KNOWLEDGE_FORMAT

logger = logging.getLogger(__name__)


class SAXKnowledgeBase:
    """Provides SAX model knowledge."""

    def __init__(self, model_manager: Optional[SAXModelManager] = None):
        """
        Initialize SAX knowledge base.

        Args:
            model_manager: Optional SAX model manager instance
        """
        self.model_manager = model_manager or SAXModelManager()
        self.usage_examples = self._load_usage_examples()

    def _load_usage_examples(self) -> Dict[str, str]:
        """Load usage examples for SAX models."""
        return {
            'mmi1x2': """
MMI 1x2 Splitter SAX Model:
  - Model name: mmi1x2
  - Parameters: length, width, gap
  - Usage: gs.models.mmi1x2(length=10.0, width=3.0, gap=0.25)
  - Ports: o1 (input), o2, o3 (outputs)
""",
            'straight_heater_metal': """
Phase Shifter SAX Model:
  - Model name: phase_shifter
  - Parameters: length, phase
  - Usage: sax.models.phase_shifter(length=10.0, phase=0.0)
  - Ports: o1, o2
""",
            'straight': """
Straight Waveguide SAX Model:
  - Model name: straight
  - Parameters: length
  - Usage: gs.models.straight(length=10.0)
  - Ports: o1, o2
""",
            'bend_euler': """
Bend SAX Model:
  - Model name: bend
  - Parameters: radius, angle
  - Usage: gs.models.bend(radius=10.0, angle=90.0)
  - Ports: o1, o2
""",
        }

    def get_component_sax_info(self, component_type: str) -> Optional[Dict]:
        """
        Get SAX information for a component.

        Args:
            component_type: Component type name

        Returns:
            SAX information dictionary or None
        """
        model_info = self.model_manager.get_model_info(component_type)
        if not model_info:
            return None
        
        info = {
            'component_type': component_type,
            'sax_model_name': model_info['sax_model_name'],
            'usage_example': self.usage_examples.get(component_type, ''),
        }
        
        return info

    def generate_knowledge_for_llm(
        self,
        component_types: List[str],
        format_type: Optional[str] = None
    ) -> str:
        """
        Generate SAX knowledge string for LLM injection.

        Args:
            component_types: List of component types
            format_type: Format type ('component_reference' or 'usage_examples')

        Returns:
            Formatted SAX knowledge string
        """
        format_type = format_type or SAX_KNOWLEDGE_FORMAT
        
        if format_type == "component_reference":
            return self._generate_component_reference(component_types)
        elif format_type == "usage_examples":
            return self._generate_usage_examples(component_types)
        else:
            return self._generate_component_reference(component_types)

    def _generate_component_reference(self, component_types: List[str]) -> str:
        """Generate component reference format."""
        lines = []
        lines.append("SAX MODEL REFERENCE:")
        lines.append("")
        
        mappings = self.model_manager.get_all_model_mappings()
        
        for comp_type in component_types:
            if comp_type in mappings:
                sax_name = mappings[comp_type]
                lines.append(f"{comp_type} -> SAX model: {sax_name}")
                
                # Add usage example if available
                if comp_type in self.usage_examples:
                    lines.append(self.usage_examples[comp_type])
                lines.append("")
        
        return "\n".join(lines)

    def _generate_usage_examples(self, component_types: List[str]) -> str:
        """Generate usage examples format."""
        lines = []
        lines.append("SAX MODEL USAGE EXAMPLES:")
        lines.append("")
        
        for comp_type in component_types:
            if comp_type in self.usage_examples:
                lines.append(self.usage_examples[comp_type])
                lines.append("")
        
        return "\n".join(lines)

    def get_model_parameters(self, component_type: str) -> Dict:
        """
        Get SAX model parameters for a component.

        Args:
            component_type: Component type name

        Returns:
            Dictionary of model parameters
        """
        # Common parameter mappings
        param_mappings = {
            'mmi1x2': {
                'length': {'default': 10.0, 'range': (5.0, 25.0)},
                'width': {'default': 3.0, 'range': (2.0, 6.0)},
                'gap': {'default': 0.25, 'range': (0.1, 0.5)},
            },
            'straight_heater_metal': {
                'length': {'default': 10.0, 'range': (5.0, 100.0)},
                'phase': {'default': 0.0, 'range': (-3.14, 3.14)},
            },
            'straight': {
                'length': {'default': 10.0, 'range': (1.0, 1000.0)},
            },
            'bend_euler': {
                'radius': {'default': 10.0, 'range': (5.0, 50.0)},
                'angle': {'default': 90.0, 'range': (0.0, 360.0)},
            },
        }
        
        return param_mappings.get(component_type, {})


