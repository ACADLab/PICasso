"""
Convert Python false code examples to YAML DSL format (GDSFactory-style).

Purpose: Parse Python code to extract component instantiations, placements, routes,
and convert to YAML DSL structure that gf.read.from_yaml() can parse.
"""

import re
import ast
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class PythonToYAMLConverter:
    """Convert Python gdsfactory code to YAML DSL format."""

    def __init__(self):
        """Initialize converter."""
        self.instances = {}
        self.placements = {}
        self.routes = []
        self.ports = {}
        self.errors = []  # Preserve errors in YAML format

    def convert(self, python_code: str, preserve_errors: bool = True) -> str:
        """
        Convert Python code to YAML DSL format.

        Args:
            python_code: Python gdsfactory code string
            preserve_errors: If True, preserve errors (missing routes, wrong ports, etc.) in YAML

        Returns:
            YAML string in GDSFactory format
        """
        self.instances = {}
        self.placements = {}
        self.routes = []
        self.ports = {}
        self.errors = []

        try:
            # Parse Python code
            tree = ast.parse(python_code)
            
            # Extract information
            self._extract_instances(tree)
            self._extract_placements(tree)
            self._extract_routes(tree)
            self._extract_ports(tree)

            # Build YAML structure
            yaml_dict = {
                'instances': self.instances,
                'placements': self.placements,
            }

            # Add routes if any
            if self.routes:
                yaml_dict['routes'] = {
                    'optical': {
                        'settings': {
                            'cross_section': 'strip',
                            'radius': 15,
                        },
                        'links': {}
                    }
                }
                for route in self.routes:
                    source = route.get('source')
                    target = route.get('target')
                    if source and target:
                        yaml_dict['routes']['optical']['links'][f"{source}"] = target

            # Add ports if any
            if self.ports:
                yaml_dict['ports'] = self.ports

            # Add errors as comments/metadata if preserving
            if preserve_errors and self.errors:
                yaml_dict['_errors'] = self.errors

            # Convert to YAML string
            yaml_str = yaml.dump(yaml_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
            return yaml_str

        except SyntaxError as e:
            logger.error(f"Syntax error in Python code: {e}")
            # Return minimal YAML with error
            return yaml.dump({
                '_error': f'Syntax error: {str(e)}',
                '_python_code': python_code
            }, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error converting Python to YAML: {e}")
            return yaml.dump({
                '_error': f'Conversion error: {str(e)}',
                '_python_code': python_code
            }, default_flow_style=False)

    def _extract_instances(self, tree: ast.AST):
        """Extract component instantiations from AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for patterns like: r << gf.components.xxx() or r.add_ref(gf.components.xxx())
                if isinstance(node.func, ast.Attribute):
                    # Check for add_ref or << operator
                    if node.func.attr == 'add_ref':
                        # Extract component name and settings
                        if node.args and isinstance(node.args[0], ast.Call):
                            comp_call = node.args[0]
                            if isinstance(comp_call.func, ast.Attribute):
                                comp_name = self._get_component_name(comp_call)
                                settings = self._extract_settings(comp_call)
                                
                                # Get instance name from assignment
                                instance_name = self._get_instance_name(node)
                                if instance_name:
                                    self.instances[instance_name] = {
                                        'component': comp_name,
                                        'settings': settings or {}
                                    }

    def _extract_placements(self, tree: ast.AST):
        """Extract component placements (move, rotate, mirror) from AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    
                    # Extract instance name from method call
                    if isinstance(node.func.value, ast.Name):
                        instance_name = node.func.value.id
                    elif isinstance(node.func.value, ast.Attribute):
                        instance_name = node.func.value.attr
                    else:
                        continue

                    if method_name == 'move':
                        # Extract x, y coordinates
                        if node.args and isinstance(node.args[0], ast.Tuple):
                            coords = node.args[0]
                            if len(coords.elts) >= 2:
                                x = self._eval_constant(coords.elts[0])
                                y = self._eval_constant(coords.elts[1])
                                if instance_name not in self.placements:
                                    self.placements[instance_name] = {}
                                self.placements[instance_name]['x'] = x or 0
                                self.placements[instance_name]['y'] = y or 0

                    elif method_name == 'rotate':
                        # Extract rotation angle
                        if node.args:
                            angle = self._eval_constant(node.args[0])
                            if instance_name not in self.placements:
                                self.placements[instance_name] = {}
                            self.placements[instance_name]['rotation'] = angle or 0

                    elif method_name == 'mirror':
                        # Set mirror flag
                        if instance_name not in self.placements:
                            self.placements[instance_name] = {}
                        self.placements[instance_name]['mirror'] = True

    def _extract_routes(self, tree: ast.AST):
        """Extract routing calls (route_single, route_bundle) from AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['route_single', 'route_bundle']:
                        # Extract route information
                        route_info = self._extract_route_info(node)
                        if route_info:
                            self.routes.append(route_info)
                        else:
                            # Missing route - this is an error we want to preserve
                            self.errors.append(f"Route call found but could not parse: {ast.unparse(node)}")

    def _extract_ports(self, tree: ast.AST):
        """Extract external port definitions from AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'add_port':
                        # Extract port name and source
                        if len(node.args) >= 2:
                            port_name = self._eval_constant(node.args[0])
                            # Second arg is usually port=instance.ports["xxx"]
                            if port_name:
                                # Try to extract instance and port
                                port_source = self._extract_port_source(node)
                                if port_source:
                                    self.ports[port_name] = port_source

    def _get_component_name(self, call_node: ast.Call) -> str:
        """Extract component name from gf.components.xxx() call."""
        if isinstance(call_node.func, ast.Attribute):
            # Handle nested attributes like gf.components.mzis.mzm()
            parts = []
            node = call_node.func
            while isinstance(node, ast.Attribute):
                parts.insert(0, node.attr)
                node = node.value
            # Skip 'gf', 'components', 'mzis' etc., get the actual component name
            # Usually the last part is the component name
            if parts:
                return parts[-1]
        return "unknown"

    def _extract_settings(self, call_node: ast.Call) -> Dict:
        """Extract settings/parameters from component call."""
        settings = {}
        for keyword in call_node.keywords:
            key = keyword.arg
            value = self._eval_constant(keyword.value)
            if key and value is not None:
                settings[key] = value
        return settings

    def _get_instance_name(self, node: ast.Call) -> Optional[str]:
        """Get instance name from assignment or variable."""
        # This is a simplified version - in practice, we'd need to track assignments
        # For now, return a generic name
        return None

    def _eval_constant(self, node: ast.AST) -> Optional[any]:
        """Evaluate constant value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.NameConstant):  # Python < 3.8
            return node.value
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                operand = self._eval_constant(node.operand)
                if operand is not None:
                    return -operand
        elif isinstance(node, ast.Tuple):
            # Extract tuple values
            values = [self._eval_constant(elt) for elt in node.elts]
            if all(v is not None for v in values):
                return tuple(values)
        return None

    def _extract_route_info(self, node: ast.Call) -> Optional[Dict]:
        """Extract route information from route_single/route_bundle call."""
        # Simplified - would need full parsing of route arguments
        return {
            'source': 'unknown,o1',  # Placeholder
            'target': 'unknown,o2',  # Placeholder
        }

    def _extract_port_source(self, node: ast.Call) -> Optional[str]:
        """Extract port source from add_port call."""
        # Simplified - would need full parsing
        return 'unknown,o1'  # Placeholder


def convert_python_to_yaml(python_code: str, output_path: Optional[str] = None) -> str:
    """
    Convert Python code to YAML DSL format.

    Args:
        python_code: Python gdsfactory code string
        output_path: Optional path to save YAML file

    Returns:
        YAML string
    """
    converter = PythonToYAMLConverter()
    yaml_str = converter.convert(python_code, preserve_errors=True)
    
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(yaml_str)
    
    return yaml_str


if __name__ == "__main__":
    # Example usage
    python_code = """
import gdsfactory as gf

r = gf.Component()

mmi1 = r.add_ref(gf.components.mmi1x2())
mmi1.move((0, 0))

mmi2 = r.add_ref(gf.components.mmi1x2())
mmi2.move((250, 0))

r.add_port('o1', port=mmi1.ports['o1'])
r.add_port('o2', port=mmi2.ports['o2'])
"""
    
    yaml_str = convert_python_to_yaml(python_code)
    print(yaml_str)

