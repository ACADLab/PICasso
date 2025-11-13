"""
Generate base pilot prompt with rules from failure analysis.

Purpose: Generate comprehensive base pilot prompt with rules for each error category,
including "What NOT to do" examples from failed cases.
"""

from typing import Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BasePilotGenerator:
    """Generate base pilot prompt from failure analysis."""

    def __init__(self, failure_analyzer=None):
        """
        Initialize generator.

        Args:
            failure_analyzer: Optional FailureAnalyzer instance with analyzed errors
        """
        self.analyzer = failure_analyzer
        if self.analyzer is None:
            # Create a dummy analyzer with empty error categories
            from types import SimpleNamespace
            self.analyzer = SimpleNamespace(
                error_categories={},
                get_error_statistics=lambda: {}
            )

    def generate_base_pilot_prompt(self) -> str:
        """Generate base pilot prompt (alias for generate)."""
        return self.generate()
    
    def generate(self) -> str:
        """
        Generate base pilot prompt.

        Returns:
            Base pilot prompt text
        """
        prompt_parts = []

        # RULE #0: ASCII ONLY (most critical)
        prompt_parts.append(self._generate_ascii_rule())

        # Syntax rules
        prompt_parts.append(self._generate_syntax_rules())

        # Component rules
        prompt_parts.append(self._generate_component_rules())

        # Port rules
        prompt_parts.append(self._generate_port_rules())

        # Routing rules
        prompt_parts.append(self._generate_routing_rules())

        # Spacing rules
        prompt_parts.append(self._generate_spacing_rules())

        # DRC rules
        prompt_parts.append(self._generate_drc_rules())

        return "\n\n".join(prompt_parts)

    def _generate_ascii_rule(self) -> str:
        """Generate ASCII-only rule (most critical)."""
        return """RULE #0 - MOST CRITICAL: ASCII ONLY - NO UNICODE!

⚠️⚠️⚠️ MANDATORY: Use ONLY ASCII characters in YAML DSL output! ⚠️⚠️⚠️

NEVER use Unicode characters:
  ❌ 'µm' (micro symbol) → ✅ Use 'um'
  ❌ '×' (multiplication) → ✅ Use 'x'
  ❌ '→' (arrow) → ✅ Use '->'
  ❌ 'ΔL' (Greek delta) → ✅ Use 'DeltaL'
  ❌ '°' (degree) → ✅ Use 'deg'

Unicode characters will cause YAML parsing errors and circuit generation will fail!
This is the #1 cause of syntax errors - ALWAYS use ASCII equivalents."""

    def _generate_syntax_rules(self) -> str:
        """Generate syntax rules."""
        stats = self.analyzer.get_error_statistics() if hasattr(self.analyzer, 'get_error_statistics') else {}
        syntax_errors = getattr(self.analyzer, 'error_categories', {}).get('syntax', [])
        
        rules = ["YAML SYNTAX RULES:"]
        rules.append("1. Required fields: 'instances', 'placements' (at minimum)")
        rules.append("2. Valid YAML syntax: proper indentation, no tabs (use spaces)")
        rules.append("3. No Unicode characters (see RULE #0)")
        rules.append("4. Valid data types: strings, numbers, booleans, lists, dictionaries")
        
        if syntax_errors:
            rules.append("\nCommon syntax errors to avoid:")
            for error in syntax_errors[:5]:  # Top 5
                rules.append(f"  - {error['error']}")
        
        return "\n".join(rules)

    def _generate_component_rules(self) -> str:
        """Generate component rules."""
        component_errors = getattr(self.analyzer, 'error_categories', {}).get('component', [])
        
        rules = ["COMPONENT RULES:"]
        rules.append("1. Use valid GDSFactory component names (e.g., 'mmi1x2', 'bend_euler', 'straight_heater_metal')")
        rules.append("2. Component names must match exactly (case-sensitive)")
        rules.append("3. Settings must be valid for the component type")
        rules.append("4. All numeric values must be valid floats (e.g., 10.0, not '10 microns')")
        
        if component_errors:
            rules.append("\nCommon component errors to avoid:")
            for error in component_errors[:5]:
                rules.append(f"  - {error['error']}")
        
        return "\n".join(rules)

    def _generate_port_rules(self) -> str:
        """Generate port rules."""
        port_errors = getattr(self.analyzer, 'error_categories', {}).get('port', [])
        
        rules = ["PORT RULES:"]
        rules.append("1. Port names must match component port names exactly (typically 'o1', 'o2', 'o3', etc.)")
        rules.append("2. Ports are labeled clockwise: o1 (left-bottom), o2 (left-top), o3 (right-top), etc.")
        rules.append("3. All optical ports MUST be connected (no dangling ports)")
        rules.append("4. External ports must be defined in 'ports' section")
        
        if port_errors:
            rules.append("\nCommon port errors to avoid:")
            for error in port_errors[:5]:
                rules.append(f"  - {error['error']}")
        
        return "\n".join(rules)

    def _generate_routing_rules(self) -> str:
        """Generate routing rules."""
        routing_errors = getattr(self.analyzer, 'error_categories', {}).get('routing', [])
        
        rules = ["ROUTING RULES:"]
        rules.append("1. ALL components MUST be connected via routes (no components placed but not routed)")
        rules.append("2. Routes section is REQUIRED if you have multiple components")
        rules.append("3. Route format: 'source_instance,port: target_instance,port'")
        rules.append("4. Use 'routes.optical.links' for optical connections")
        rules.append("5. Route settings: cross_section='strip', radius>=20 (not 15)")
        
        if routing_errors:
            rules.append("\nCommon routing errors to avoid:")
            for error in routing_errors[:5]:
                rules.append(f"  - {error['error']}")
            rules.append("\n❌ WRONG: Components placed but no routes section")
            rules.append("✅ CORRECT: Always include routes section with all connections")
        
        return "\n".join(rules)

    def _generate_spacing_rules(self) -> str:
        """Generate spacing rules."""
        spacing_errors = getattr(self.analyzer, 'error_categories', {}).get('spacing', [])
        
        rules = ["SPACING RULES (CRITICAL - prevents routing collisions):"]
        rules.append("1. MINIMUM 200um spacing between components (MANDATORY)")
        rules.append("2. Simple designs (≤5 components): 200um minimum")
        rules.append("3. Complex designs (>5 components): 250um+ spacing required")
        rules.append("4. Vertical stacking: Use +/-100um or more vertical offset")
        rules.append("5. Horizontal placement: 250-300um separation")
        rules.append("6. Route radius: >= 20um (not 15um - larger is safer)")
        rules.append("7. Route separation in bundles: >= 20um")
        
        if spacing_errors:
            rules.append("\nCommon spacing errors to avoid:")
            for error in spacing_errors[:5]:
                rules.append(f"  - {error['error']}")
        
        return "\n".join(rules)

    def _generate_drc_rules(self) -> str:
        """Generate DRC rules."""
        drc_errors = getattr(self.analyzer, 'error_categories', {}).get('drc', [])
        
        rules = ["DRC RULES (Design Rule Check):"]
        rules.append("1. Waveguide width: >= 0.45um (generic_tech PDK)")
        rules.append("2. Spacing: >= 0.2um between waveguides")
        rules.append("3. Heater-to-waveguide spacing: >= 1.0um")
        rules.append("4. No routing collisions (components/waveguides overlapping)")
        rules.append("5. All components must be within valid layer bounds")
        
        if drc_errors:
            rules.append("\nCommon DRC errors to avoid:")
            for error in drc_errors[:5]:
                rules.append(f"  - {error['error']}")
        
        return "\n".join(rules)

    def save(self, output_path: str):
        """
        Save base pilot prompt to file.

        Args:
            output_path: Path to save prompt file
        """
        prompt = self.generate()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(prompt)
        logger.info(f"Saved base pilot prompt to {output_path}")


if __name__ == "__main__":
    from .failure_analyzer import FailureAnalyzer
    
    # Example usage
    analyzer = FailureAnalyzer()
    # ... analyze errors ...
    
    generator = BasePilotGenerator(analyzer)
    prompt = generator.generate()
    print(prompt)
    
    generator.save("base_pilot_prompt.txt")

