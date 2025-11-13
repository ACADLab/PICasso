"""
Prompt Enhancer

Enhances LLM prompts with component references, design restrictions, and proper formatting.
Sanitizes inputs and formats prompts to avoid hallucinations.
"""

import logging
from typing import Dict, Optional
from ..config import ENABLE_SAX_KNOWLEDGE_INJECTION, INJECT_SAX_KNOWLEDGE_TO_LLM
from .input_validator import InputValidator

logger = logging.getLogger(__name__)


class PromptEnhancer:
    """Enhances prompts for LLM inference."""

    def __init__(self):
        """Initialize prompt enhancer."""
        self.input_validator = InputValidator()
        self.component_specs_cache = None

    def enhance(
        self,
        problem_text: str,
        component_specs: Optional[str] = None,
        sax_knowledge: Optional[str] = None,
        restrictions: Optional[str] = None
    ) -> str:
        """
        Enhance prompt with component specs, SAX knowledge, and restrictions.

        Args:
            problem_text: Original problem description
            component_specs: Component specifications (optional)
            sax_knowledge: SAX model knowledge (optional)
            restrictions: Design restrictions (optional)

        Returns:
            Enhanced prompt text
        """
        # Sanitize input
        sanitized = self.input_validator.sanitize(problem_text)
        
        # Build enhanced prompt
        parts = []
        
        # Add component specifications if available
        if component_specs:
            parts.append("--- AVAILABLE GDSFACTORY COMPONENTS REFERENCE ---")
            parts.append("Use ONLY the following components with their EXACT port names and API signatures:")
            parts.append("<warning>")
            parts.append(component_specs)
            parts.append("</warning>")
            parts.append("--- END COMPONENTS REFERENCE ---")
            parts.append("")
        
        # Add SAX knowledge if enabled
        if ENABLE_SAX_KNOWLEDGE_INJECTION and INJECT_SAX_KNOWLEDGE_TO_LLM and sax_knowledge:
            parts.append("--- SAX MODEL INFORMATION ---")
            parts.append("The following SAX models are available for simulation:")
            parts.append(sax_knowledge)
            parts.append("--- END SAX INFORMATION ---")
            parts.append("")
        
        # Add design restrictions
        if restrictions:
            parts.append("--- DESIGN RESTRICTIONS ---")
            parts.append(restrictions)
            parts.append("--- END RESTRICTIONS ---")
            parts.append("")
        
        # Add problem description
        parts.append("PROBLEM DESCRIPTION:")
        parts.append(sanitized)
        
        return "\n".join(parts)

    def add_restrictions(self, base_prompt: str, restrictions: str) -> str:
        """
        Add design restrictions to prompt.

        Args:
            base_prompt: Base prompt text
            restrictions: Restrictions to add

        Returns:
            Prompt with restrictions added
        """
        if not restrictions:
            return base_prompt
        
        restriction_section = f"\n\n--- DESIGN RESTRICTIONS ---\n{restrictions}\n--- END RESTRICTIONS ---\n"
        
        # Insert before the problem description if it exists
        if "PROBLEM DESCRIPTION:" in base_prompt:
            return base_prompt.replace("PROBLEM DESCRIPTION:", restriction_section + "\nPROBLEM DESCRIPTION:")
        else:
            return base_prompt + restriction_section

    def format_python_prompt(
        self,
        problem_text: str,
        component_specs: Optional[str] = None,
        sax_knowledge: Optional[str] = None,
        restrictions: Optional[str] = None
    ) -> str:
        """
        Format prompt for Python code generation.

        Args:
            problem_text: Problem description
            component_specs: Component specifications
            sax_knowledge: SAX knowledge
            restrictions: Design restrictions

        Returns:
            Formatted Python generation prompt
        """
        enhanced = self.enhance(problem_text, component_specs, sax_knowledge, restrictions)
        
        python_prompt = f"""You are a professional Photonic Integrated Circuit (PIC) designer with expertise in GDSFactory.
Your task is to generate Python code based on the circuit design requirements provided.

{enhanced}

IMPORTANT RESTRICTIONS (to avoid common mistakes):
  1. Component Selection:
     - Use ONLY GDSFactory library components (gf.components.*)
     - Verify component port names from the reference above
     - Use the exact component IDs specified in the problem statement

  2. Port Naming and Connection:
     - Check available ports using the component reference
     - Common mistake: Assuming port names like 'o3' exist when they don't
     - MMI ports: typically 'o1', 'o2' (outputs), check reference for exact names
     - All optical ports MUST be connected (no dangling ports)

  3. Component Mirroring (CRITICAL ERROR TO AVOID):
     - WRONG: gf.components.mmi1x2().mirror()  # Cell objects don't have mirror()
     - CORRECT: ref = r.add_ref(gf.components.mmi1x2()); ref.mirror()
     - Always call mirror() AFTER add_ref(), on the ComponentReference

  4. Spacing Rules (prevents ROUTING_COLLISION):
     - Minimum 80um spacing between components (150um for complex designs)
     - Vertical stacking: Use +/-60um or more vertical offset
     - Horizontal placement: 150-200um separation
     - Bend radius: >= 15um (20-30um for safety)
     - Route separation in route_bundle: >= 15um

  5. Parameters and Settings:
     - Use default values unless explicitly specified in the problem
     - If parameter difference specified (e.g., DeltaL = 10um), set one to default, adjust other
     - Default unit: microns (um)

  6. Code Format:
     - Use single quotes for strings (not double quotes)
     - No comments or explanations in code
     - Follow the structure: instantiate -> move -> route -> add_ports
     - CRITICAL: Use ONLY ASCII characters. Never use Unicode: 'um' not 'µm', 'x' not '×', '->' not '→', 'DeltaL' not 'ΔL'
     - CRITICAL: All numeric values must be valid Python floats. Examples:
       * "10 microns" -> use 10.0 (not 10 microns, not 10µm, not 10.0.5)
       * "DeltaL = 10" -> use delta_length=10.0 (just the number)
       * "100um spacing" -> use 100.0 (just the number)
       * Never attach units to numbers in code: use 10.0 not 10.0um

Your response MUST consist of TWO sections:

<analysis>
Provide a detailed step-by-step analysis of how you will implement the circuit.
Think through:
  1. What components are needed? (check component reference for exact names)
  2. What are their port names? (verify from reference, don't guess)
  3. How should they be arranged spatially? (spacing requirements)
  4. How should ports be connected? (routing strategy)
  5. What parameters need to be set? (use defaults unless specified)
  6. Any special considerations? (mirroring, flipping, complex routing)
</analysis>

<result>
Provide ONLY the complete, executable Python code (no explanations, no markdown).
The code must follow this structure:

import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
component1 = r.add_ref(gf.components.xxx(...))
component1.move((x1, y1))

component2 = r.add_ref(gf.components.yyy(...))
component2.move((x2, y2))

# 2. Route connections
gf.routing.route_bundle(
    r,
    [source_ports],
    [dest_ports],
    cross_section='strip',
    radius=15,
    separation=15
)

# 3. Expose external ports
r.add_port('o1', port=component1.ports['xxx'])
r.add_port('o2', port=component2.ports['yyy'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>
"""
        return python_prompt


