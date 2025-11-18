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

        # Check 3: Required fields and YAML structure
        required_check = self._check_required_fields(yaml_data)
        if not required_check[0]:
            error_details = required_check[2] if len(required_check) > 2 else {'error_type': 'syntax', 'category': 'missing_fields'}
            return False, required_check[1], error_details

        # Check 4: Valid component names
        component_check = self._check_component_names(yaml_data)
        if not component_check[0]:
            error_details = component_check[2] if len(component_check) > 2 else {'error_type': 'component', 'category': 'invalid_name'}
            return False, component_check[1], error_details

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

        # Check 8: Invalid numeric values (e.g., "4-1" instead of 3 or 4.0)
        numeric_check = self._check_numeric_values(yaml_data)
        if not numeric_check[0]:
            return False, numeric_check[1], {'error_type': 'syntax', 'category': 'invalid_numeric'}

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

    def _check_required_fields(self, yaml_data: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Check for required fields and YAML structure."""
        if not isinstance(yaml_data, dict):
            return False, "YAML must be a dictionary", {'error_type': 'syntax', 'category': 'yaml'}
        
        if 'instances' not in yaml_data:
            return False, "Missing required field: 'instances'", {'error_type': 'syntax', 'category': 'missing_fields'}
        
        if 'placements' not in yaml_data:
            return False, "Missing required field: 'placements'", {'error_type': 'syntax', 'category': 'missing_fields'}
        
        # Check YAML structure: placements and ports should be dictionaries, not lists
        if isinstance(yaml_data.get('placements'), list):
            return False, "placements must be a dictionary (not a list). Format: placements: {instance_name: {x: 0, y: 0, ...}}", {'error_type': 'syntax', 'category': 'yaml_structure'}
        
        if 'ports' in yaml_data and isinstance(yaml_data.get('ports'), list):
            return False, "ports must be a dictionary (not a list). Format: ports: {port_name: instance,port}", {'error_type': 'syntax', 'category': 'yaml_structure'}
        
        if 'connections' in yaml_data and isinstance(yaml_data.get('connections'), list):
            return False, "connections should use 'routes' section instead. Format: routes: {optical: {links: {source,port: target,port}}}", {'error_type': 'syntax', 'category': 'yaml_structure'}
        
        return True, None, None

    def _check_component_names(self, yaml_data: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Check that component names are valid GDSFactory components."""
        if 'instances' not in yaml_data:
            return True, None, None  # Already checked in required fields
        
        instances = yaml_data['instances']
        invalid_components = []
        component_mappings = {
            'mmi2x1': 'mmi1x2 (with mirror: true)',
            'phase_shifter': 'straight_heater_metal',
            'heater': 'straight_heater_metal',
            'y_splitter': 'coupler or mmi1x2',
            'y_junction': 'coupler or mmi1x2',
            'dc_2x2': 'coupler',
            'waveguide': 'straight',
            'star_coupler': 'coupler or mmi2x2',
            'photodiode': 'NOT AVAILABLE in generic_tech PDK',
        }
        
        for inst_name, inst_data in instances.items():
            if not isinstance(inst_data, dict):
                continue
            comp_type = inst_data.get('component')
            if comp_type:
                # Check if component exists in gdsfactory
                if not hasattr(gf.components, comp_type):
                    invalid_components.append({
                        'instance': inst_name,
                        'invalid': comp_type,
                        'suggestion': component_mappings.get(comp_type, 'Check ALLOWED_COMPONENTS list')
                    })
        
        if invalid_components:
            error_parts = [f"{ic['instance']}: {ic['invalid']}" for ic in invalid_components]
            error_msg = f"Invalid component names: {', '.join(error_parts)}"
            error_details = {
                'error_type': 'component',
                'category': 'invalid_name',
                'invalid_components': invalid_components
            }
            return False, error_msg, error_details
        
        return True, None, None

    def _check_port_names(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """Check that port names are valid."""
        # This is a simplified check - full validation would require component instantiation
        # For now, check common patterns
        if 'routes' in yaml_data:
            routes = yaml_data['routes']
            if isinstance(routes, dict) and 'optical' in routes:
                optical = routes['optical']
                if isinstance(optical, dict) and 'links' in optical:
                    links = optical.get('links', {})
                    # links should be a dict, but iterate over values if it's a dict
                    if isinstance(links, dict):
                        for link in links.values():
                            # Format: "instance,port: target,port"
                            if isinstance(link, str) and ':' in link:
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
        
        # Handle case where placements might be a string or list instead of dict
        if not isinstance(placements, dict):
            return True, None  # Skip spacing check if placements is not a dict
        
        positions = []
        
        for inst_name, placement in placements.items():
            if isinstance(placement, dict):
                x = placement.get('x', 0) or 0  # Handle None values
                y = placement.get('y', 0) or 0  # Handle None values
                # Only add if both x and y are valid numbers
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    positions.append((inst_name, float(x), float(y)))
        
        # Determine required spacing based on circuit complexity
        num_components = len(positions)
        if num_components > 20:
            required_spacing = 300.0  # Very complex: 300um+
        elif num_components > 10:
            required_spacing = 250.0  # Complex: 250um+
        else:
            required_spacing = self.min_spacing_um  # Simple: 200um
        
        # Check spacing
        violations = []
        for i, (name1, x1, y1) in enumerate(positions):
            for name2, x2, y2 in positions[i+1:]:
                distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                if 0 < distance < required_spacing:
                    violations.append((name1, name2, distance, required_spacing))
        
        if violations:
            # Return first violation with context about complexity
            name1, name2, dist, req = violations[0]
            complexity_note = f" (required: {req}um for {num_components} components)" if num_components > 10 else ""
            return False, f"Components {name1} and {name2} too close ({dist:.1f}um < {req}um{complexity_note})"
        
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
            if not isinstance(routes, dict) or 'optical' not in routes:
                return False, "Missing routes.optical section"
            
            optical = routes['optical']
            if not isinstance(optical, dict) or 'links' not in optical:
                return False, "Missing routes.optical.links section"
            
            links = optical.get('links', {})
            if not links:
                return False, "Routes section exists but no links defined"
        
        return True, None

    def _check_numeric_values(self, yaml_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check that all numeric values are valid (not expressions like "4-1").
        Note: cross_section can be a string (e.g., 'strip'), so we skip it.
        
        Args:
            yaml_data: Parsed YAML data
            
        Returns:
            (is_valid, error_message)
        """
        def is_valid_numeric(value, key_name=""):
            """Check if a value is a valid numeric literal."""
            # Skip cross_section - it can be a string like 'strip'
            if key_name == "cross_section":
                return True
            
            # If it's already a number, it's valid
            if isinstance(value, (int, float)):
                return True
            
            # If it's a string, check if it's a valid number or expression
            if isinstance(value, str):
                # Allow strings for cross_section
                if key_name == "cross_section":
                    return True
                # Check if it's a valid numeric string
                try:
                    float(value)
                    # Check for invalid patterns like "4-1", "10/2", etc.
                    if '-' in value and not value.startswith('-'):
                        # Has minus in middle (e.g., "4-1")
                        return False
                    if '/' in value or '*' in value or '+' in value:
                        # Has arithmetic operators
                        return False
                    return True
                except ValueError:
                    # Not a numeric string - might be valid (e.g., 'strip' for cross_section)
                    # But we already checked cross_section above, so this is invalid
                    return False
            
            return True  # Non-numeric values are OK (bools, None, etc.)
        
        def check_dict_values(d, path=""):
            """Recursively check all values in a dictionary."""
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    if not check_dict_values(value, current_path):
                        return False
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            if not check_dict_values(item, f"{current_path}[{i}]"):
                                return False
                        elif not is_valid_numeric(item):
                            return False, f"Invalid numeric value at {current_path}[{i}]: '{item}'"
                elif not is_valid_numeric(value):
                    return False, f"Invalid numeric value at {current_path}: '{value}'"
            return True
        
        # Check instances settings
        if 'instances' in yaml_data:
            for inst_name, inst_data in yaml_data['instances'].items():
                if isinstance(inst_data, dict) and 'settings' in inst_data:
                    settings = inst_data['settings']
                    if isinstance(settings, dict):
                        for param, value in settings.items():
                            if not is_valid_numeric(value, param):
                                return False, f"Invalid numeric value in {inst_name}.settings.{param}: '{value}'. Use a number (e.g., 3 or 4.0), not an expression like '4-1'."
        
        # Check placements (x, y, rotation)
        if 'placements' in yaml_data:
            placements = yaml_data['placements']
            if isinstance(placements, dict):
                for inst_name, placement in placements.items():
                    if isinstance(placement, dict):
                        for coord in ['x', 'y', 'rotation']:
                            if coord in placement:
                                value = placement[coord]
                                if not is_valid_numeric(value):
                                    return False, f"Invalid numeric value in placements.{inst_name}.{coord}: '{value}'. Use a number (e.g., 0 or 90.0), not an expression."
        
        # Check routes settings
        if 'routes' in yaml_data:
            routes = yaml_data['routes']
            if isinstance(routes, dict) and 'optical' in routes:
                optical = routes['optical']
                if isinstance(optical, dict) and 'settings' in optical:
                    settings = optical['settings']
                    if isinstance(settings, dict):
                        for param, value in settings.items():
                            if not is_valid_numeric(value, param):
                                return False, f"Invalid numeric value in routes.optical.settings.{param}: '{value}'. Use a number (e.g., 20.0), not an expression."
        
        return True, None

    def get_feedback(self, error_details: Optional[Dict] = None) -> str:
        """
        Generate feedback for LLM retry.

        Args:
            error_details: Error details dictionary (must include 'error_message')

        Returns:
            Actionable feedback string
        """
        if not error_details:
            return "YAML validation failed. Please check the YAML syntax and structure."
        
        error_msg = error_details.get('error_message', 'Validation failed')
        feedback = [f"YAML PILOT VALIDATION ERROR: {error_msg}"]
        
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
                elif category == 'yaml_structure':
                    feedback.append("\nFIX: YAML structure error - use correct format:")
                    feedback.append("  ❌ WRONG: placements: [{instance: name, x: 0, ...}]")
                    feedback.append("  ✅ CORRECT: placements: {name: {x: 0, y: 0, rotation: 0, mirror: false}}")
                    feedback.append("  ❌ WRONG: ports: [[instance, port, name]]")
                    feedback.append("  ✅ CORRECT: ports: {name: instance,port}")
                    feedback.append("  ❌ WRONG: connections: [[inst1, port1, inst2, port2]]")
                    feedback.append("  ✅ CORRECT: routes: {optical: {links: {inst1,port1: inst2,port2}}}")
                elif category == 'invalid_numeric':
                    feedback.append("\nFIX: Invalid numeric value detected:")
                    feedback.append("  - Use actual numbers, NOT expressions")
                    feedback.append("  - ❌ WRONG: '4-1', '10/2', '5*2', '3+1'")
                    feedback.append("  - ✅ CORRECT: 3, 4.0, 5.5, 10.0")
                    feedback.append("  - Calculate the value first, then use the result")
                    feedback.append("  - Example: If you need 4-1, use 3.0 instead")
                elif category == 'missing_fields':
                    feedback.append("\nFIX: Ensure 'instances' and 'placements' sections exist")
            
            elif error_type == 'component':
                if category == 'invalid_parameter':
                    feedback.append("\nFIX: Use valid component parameters")
                    feedback.append("  - Check component function signature for valid parameters")
                    feedback.append("  - Common mistake: 'mmi1x2' does not have 'length' parameter, use 'length_mmi' instead")
                    feedback.append("  - Remove invalid parameters from settings section")
                elif category == 'invalid_name':
                    invalid_components = error_details.get('invalid_components', [])
                    feedback.append("\nFIX: Replace invalid component names with valid alternatives:")
                    feedback.append("\nCOMPONENT MAPPING (use these instead):")
                    for ic in invalid_components:
                        feedback.append(f"  ❌ {ic['instance']}: component: {ic['invalid']}")
                        feedback.append(f"  ✅ {ic['instance']}: component: {ic['suggestion']}")
                    feedback.append("\nCommon component replacements:")
                    feedback.append("  - mmi2x1 → mmi1x2 (and set mirror: true in placements)")
                    feedback.append("  - phase_shifter → straight_heater_metal")
                    feedback.append("  - heater → straight_heater_metal")
                    feedback.append("  - y_splitter → coupler or mmi1x2")
                    feedback.append("  - y_junction → coupler or mmi1x2")
                    feedback.append("  - dc_2x2 → coupler")
                    feedback.append("  - waveguide → straight")
                    feedback.append("  - star_coupler → coupler or mmi2x2")
                    feedback.append("  - photodiode → NOT AVAILABLE in generic_tech PDK")
                else:
                    feedback.append("\nFIX: Use valid GDSFactory component names")
                    feedback.append("  - Check component name exists in gf.components")
                    feedback.append("  - Common mistake: 'mmi2x1' does not exist, use 'mmi1x2' with mirror: true")
            
            elif error_type == 'port':
                feedback.append("\nFIX: Use valid port names (typically 'o1', 'o2', 'o3', etc.)")
                feedback.append("  - Check component.ports to see available ports")
            
            elif error_type == 'spacing':
                # Extract number of components from error message if available
                error_msg = error_details.get('error_message', '')
                if 'required:' in error_msg:
                    # Extract required spacing from error message
                    import re
                    req_match = re.search(r'required: ([\d.]+)um', error_msg)
                    if req_match:
                        required = req_match.group(1)
                        feedback.append(f"\nFIX: Increase spacing to at least {required}um")
                    else:
                        feedback.append(f"\nFIX: Increase spacing to at least {self.min_spacing_um}um")
                else:
                    feedback.append(f"\nFIX: Increase spacing to at least {self.min_spacing_um}um")
                
                feedback.append("  - Update placements x/y coordinates")
                feedback.append("  - For complex circuits (>10 components): Use 250um+ spacing")
                feedback.append("  - For very complex circuits (>20 components): Use 300um+ spacing")
                feedback.append("  - Example: If components are at (0,0) and (150,0), change to (0,0) and (250,0)")
            
            elif error_type == 'routing':
                # Extract number of components from error message if available
                error_msg = error_details.get('error_message', '')
                import re
                num_comp_match = re.search(r'(\d+) components', error_msg)
                if num_comp_match:
                    num_comp = int(num_comp_match.group(1))
                    feedback.append(f"\nFIX: Add routes section (REQUIRED for {num_comp} components)")
                else:
                    feedback.append("\nFIX: Add routes section with all component connections")
                
                feedback.append("  - Format: routes.optical.links: {source,port: target,port}")
                feedback.append("  - ALL components must be connected via routes")
                feedback.append("  - Example:")
                feedback.append("    routes:")
                feedback.append("      optical:")
                feedback.append("        settings:")
                feedback.append("          cross_section: strip")
                feedback.append("          radius: 20.0")
                feedback.append("        links:")
                feedback.append("          comp1,o2: comp2,o1")
                feedback.append("          comp2,o2: comp3,o1")
        
        return "\n".join(feedback)

