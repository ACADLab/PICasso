"""
YAML Pilot Validator

Pre-execution validation of YAML DSL syntax, structure, components, ports, routing, and spacing.
"""

import yaml
import logging
import re
import inspect
from typing import Dict, List, Tuple, Optional
import gdsfactory as gf

logger = logging.getLogger(__name__)


class YAMLPilotValidator:
    """Validates YAML DSL before execution."""

    def __init__(self):
        """Initialize YAML pilot validator."""
        self.min_spacing_um = 200.0
        self.min_route_radius_um = 20.0
        self.valid_components = set()  # Will be populated with available components

    def validate(self, yaml_str: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate YAML DSL.

        Args:
            yaml_str: YAML DSL string

        Returns:
            (is_valid, error_message, error_details)
        """
        # Check 1: ASCII only (most critical)
        ascii_check = self._check_ascii_only(yaml_str)
        if not ascii_check[0]:
            return False, ascii_check[1], {'error_type': 'syntax', 'category': 'unicode'}

        # Check 2: Valid YAML syntax
        yaml_check = self._check_yaml_syntax(yaml_str)
        if not yaml_check[0]:
            return False, yaml_check[1], {'error_type': 'syntax', 'category': 'yaml'}

        yaml_data = yaml_check[2]

        # Check 3: Required fields
        required_check = self._check_required_fields(yaml_data)
        if not required_check[0]:
            return False, required_check[1], {'error_type': 'syntax', 'category': 'missing_fields'}

        # Check 4: Valid component names
        component_check = self._check_component_names(yaml_data)
        if not component_check[0]:
            return False, component_check[1], {'error_type': 'component', 'category': 'invalid_name'}

        # Check 5: Valid port names
        port_check = self._check_port_names(yaml_data)
        if not port_check[0]:
            return False, port_check[1], {'error_type': 'port', 'category': 'invalid_name'}

        # Check 5.5: Valid component parameters
        param_check = self._check_component_parameters(yaml_data)
        if not param_check[0]:
            return False, param_check[1], {'error_type': 'component', 'category': 'invalid_parameter'}

        # Check 6: Spacing violations
        spacing_check = self._check_spacing(yaml_data)
        if not spacing_check[0]:
            return False, spacing_check[1], {'error_type': 'spacing', 'category': 'too_close'}

        # Check 7: Missing routes
        routing_check = self._check_routing(yaml_data)
        if not routing_check[0]:
            return False, routing_check[1], {'error_type': 'routing', 'category': 'missing_routes'}

        return True, None, None

    def _check_ascii_only(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check for Unicode characters."""
        unicode_chars = re.findall(r'[^\x00-\x7F]', text)
        if unicode_chars:
            unique_chars = set(unicode_chars)
            return False, f"Unicode characters found: {unique_chars}. Use ASCII only (um, x, ->, DeltaL)"
        return True, None

    def _check_yaml_syntax(self, yaml_str: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Check valid YAML syntax."""
        try:
            yaml_data = yaml.safe_load(yaml_str)
            return True, None, yaml_data
        except yaml.YAMLError as e:
            return False, f"YAML syntax error: {str(e)}", None

    def _check_required_fields(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check for required fields."""
        if not isinstance(yaml_data, dict):
            return False, "YAML must be a dictionary"
        
        if 'instances' not in yaml_data:
            return False, "Missing required field: 'instances'"
        
        if 'placements' not in yaml_data:
            return False, "Missing required field: 'placements'"
        
        return True, None

    def _check_component_names(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check that component names are valid GDSFactory components."""
        if 'instances' not in yaml_data:
            return True, None  # Already checked in required fields
        
        instances = yaml_data['instances']
        invalid_components = []
        
        for inst_name, inst_data in instances.items():
            if not isinstance(inst_data, dict):
                continue
            comp_type = inst_data.get('component')
            if comp_type:
                # Check if component exists in gdsfactory
                if not hasattr(gf.components, comp_type):
                    invalid_components.append(f"{inst_name}: {comp_type}")
        
        if invalid_components:
            return False, f"Invalid component names: {', '.join(invalid_components)}"
        
        return True, None

    def _check_port_names(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check that port names are valid."""
        # This is a simplified check - full validation would require component instantiation
        # For now, check common patterns
        if 'routes' in yaml_data and 'optical' in yaml_data['routes']:
            links = yaml_data['routes']['optical'].get('links', {})
            for link in links:
                # Format: "instance,port: target,port"
                if ':' in link:
                    parts = link.split(':')
                    if len(parts) == 2:
                        source = parts[0].strip()
                        if ',' in source:
                            port = source.split(',')[1]
                            # Check for common invalid port names
                            if port.startswith('p') and port[1:].isdigit():
                                return False, f"Invalid port name pattern: {port} (use 'o1', 'o2', etc.)"
        
        return True, None

    def _check_component_parameters(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check that component parameters are valid."""
        if 'instances' not in yaml_data:
            return True, None
        
        instances = yaml_data['instances']
        invalid_params = []
        
        for inst_name, inst_data in instances.items():
            if not isinstance(inst_data, dict):
                continue
            comp_type = inst_data.get('component')
            if not comp_type:
                continue
            
            # Check if component exists
            if not hasattr(gf.components, comp_type):
                continue  # Already caught by component name check
            
            # Get component function
            comp_func = getattr(gf.components, comp_type)
            
            # Get valid parameters from function signature
            try:
                sig = inspect.signature(comp_func)
                valid_params = set(sig.parameters.keys())
            except Exception:
                # If we can't get signature, skip parameter validation
                continue
            
            # Check settings in YAML
            settings = inst_data.get('settings', {})
            if isinstance(settings, dict):
                for param_name in settings.keys():
                    if param_name not in valid_params:
                        invalid_params.append(f"{inst_name}.{comp_type}: invalid parameter '{param_name}'")
        
        if invalid_params:
            # Get valid params for first component to show in error
            first_comp = invalid_params[0].split(':')[0].split('.')[1]
            comp_func = getattr(gf.components, first_comp, None)
            if comp_func:
                try:
                    sig = inspect.signature(comp_func)
                    valid_params_list = list(sig.parameters.keys())[:10]  # Show first 10
                    valid_params_str = ', '.join(valid_params_list)
                    return False, f"Invalid parameters: {', '.join(invalid_params[:3])}. Valid parameters for {first_comp}: {valid_params_str}"
                except:
                    pass
            return False, f"Invalid parameters: {', '.join(invalid_params[:3])}"
        
        return True, None

    def _check_spacing(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check spacing between components."""
        if 'placements' not in yaml_data:
            return True, None
        
        placements = yaml_data['placements']
        positions = []
        
        for inst_name, placement in placements.items():
            if isinstance(placement, dict):
                x = placement.get('x', 0)
                y = placement.get('y', 0)
                positions.append((inst_name, x, y))
        
        # Check spacing
        for i, (name1, x1, y1) in enumerate(positions):
            for name2, x2, y2 in positions[i+1:]:
                distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                if 0 < distance < self.min_spacing_um:
                    return False, f"Components {name1} and {name2} too close ({distance:.1f}um < {self.min_spacing_um}um)"
        
        return True, None

    def _check_routing(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check that routes exist if multiple components are present."""
        if 'instances' not in yaml_data:
            return True, None
        
        instances = yaml_data['instances']
        num_instances = len(instances)
        
        # If multiple components, routes should exist
        if num_instances > 1:
            if 'routes' not in yaml_data:
                return False, f"Missing routes section (required when {num_instances} components are placed)"
            
            routes = yaml_data.get('routes', {})
            if 'optical' not in routes or 'links' not in routes['optical']:
                return False, "Missing routes.optical.links section"
            
            links = routes['optical'].get('links', {})
            if not links:
                return False, "Routes section exists but no links defined"
        
        return True, None

    def get_feedback(self, error_message: str, error_details: Optional[Dict] = None) -> str:
        """
        Generate feedback for LLM retry.

        Args:
            error_message: Error message
            error_details: Error details dictionary

        Returns:
            Actionable feedback string
        """
        feedback = [f"YAML PILOT VALIDATION ERROR: {error_message}"]
        
        if error_details:
            error_type = error_details.get('error_type')
            category = error_details.get('category')
            
            if error_type == 'syntax':
                if category == 'unicode':
                    feedback.append("\nFIX: Replace all Unicode characters with ASCII equivalents:")
                    feedback.append("  - 'µm' → 'um'")
                    feedback.append("  - '×' → 'x'")
                    feedback.append("  - '→' → '->'")
                    feedback.append("  - 'ΔL' → 'DeltaL'")
                elif category == 'yaml':
                    feedback.append("\nFIX: Check YAML syntax (indentation, quotes, brackets)")
                elif category == 'missing_fields':
                    feedback.append("\nFIX: Ensure 'instances' and 'placements' sections exist")
            
            elif error_type == 'component':
                if category == 'invalid_parameter':
                    feedback.append("\nFIX: Use valid component parameters")
                    feedback.append("  - Check component function signature for valid parameters")
                    feedback.append("  - Common mistake: 'mmi1x2' does not have 'length' parameter, use 'length_mmi' instead")
                    feedback.append("  - Remove invalid parameters from settings section")
                else:
                    feedback.append("\nFIX: Use valid GDSFactory component names")
                    feedback.append("  - Check component name exists in gf.components")
                    feedback.append("  - Common mistake: 'mmi2x1' does not exist, use 'mmi1x2' with mirror: true")
            
            elif error_type == 'port':
                feedback.append("\nFIX: Use valid port names (typically 'o1', 'o2', 'o3', etc.)")
                feedback.append("  - Check component.ports to see available ports")
            
            elif error_type == 'spacing':
                feedback.append(f"\nFIX: Increase spacing to at least {self.min_spacing_um}um")
                feedback.append("  - Update placements x/y coordinates")
            
            elif error_type == 'routing':
                feedback.append("\nFIX: Add routes section with all component connections")
                feedback.append("  - Format: routes.optical.links: {source,port: target,port}")
        
        return "\n".join(feedback)

