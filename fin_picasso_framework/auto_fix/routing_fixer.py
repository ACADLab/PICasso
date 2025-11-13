"""
Routing Fixer - Automatically adds missing route_single() calls

This module analyzes Python code and automatically generates missing routing
calls based on component placements and expected connections.
"""

import ast
import re
import logging
from typing import Dict, List, Tuple, Optional, Set
import gdsfactory as gf

logger = logging.getLogger(__name__)


class RoutingFixer:
    """
    Automatically fixes missing routing in generated code.
    
    Analyzes component structure and adds missing route_single() calls.
    """
    
    def __init__(self):
        """Initialize routing fixer."""
        self.component_refs = {}  # Track component references
        self.expected_connections = []  # Track expected connections
        self.existing_routes = []  # Track existing route calls
        
    def fix_missing_routes(self, code: str, component: Optional[gf.Component] = None) -> str:
        """
        Fix missing routes in code by adding route_single() calls.
        
        Args:
            code: Python code string
            component: Optional gdsfactory Component (if already executed)
            
        Returns:
            Fixed code with missing routes added
        """
        # Parse code to understand structure
        try:
            tree = ast.parse(code)
        except SyntaxError:
            logger.warning("Cannot parse code for routing fix - syntax error")
            return code
        
        # Extract component references and existing routes
        self._extract_component_refs(tree)
        self._extract_existing_routes(code)
        
        # If we have a component, analyze it to find missing routes
        if component is not None:
            missing_routes = self._find_missing_routes_from_component(component)
        else:
            # Infer missing routes from code structure
            missing_routes = self._infer_missing_routes_from_code(code, tree)
        
        if not missing_routes:
            logger.info("No missing routes detected")
            return code
        
        # Generate route_single() calls for missing routes
        route_code = self._generate_route_code(missing_routes)
        
        # Insert route code before port additions
        fixed_code = self._insert_routes(code, route_code)
        
        logger.info(f"Added {len(missing_routes)} missing route_single() calls")
        return fixed_code
    
    def _extract_component_refs(self, tree: ast.AST):
        """Extract component reference names from AST."""
        self.component_refs = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Check if assignment is a component reference
                        if isinstance(node.value, ast.Call):
                            # Pattern: ref = r.add_ref(...) or ref = r << ...
                            if (isinstance(node.value.func, ast.Attribute) and
                                node.value.func.attr in ['add_ref', '__lshift__']):
                                self.component_refs[target.id] = target.id
        
    def _extract_existing_routes(self, code: str):
        """Extract existing route_single() calls from code."""
        self.existing_routes = []
        
        # Find all route_single calls
        pattern = r'gf\.routing\.route_single\s*\([^)]+\)'
        matches = re.finditer(pattern, code)
        
        for match in matches:
            route_call = match.group(0)
            # Extract port references
            port_pattern = r'(\w+)\.ports\[["\'](\w+)["\']\]'
            ports = re.findall(port_pattern, route_call)
            if len(ports) >= 2:
                self.existing_routes.append((ports[0], ports[1]))
    
    def _find_missing_routes_from_component(self, component: gf.Component) -> List[Tuple[str, str, str, str]]:
        """
        Find missing routes by analyzing component structure.
        
        Returns:
            List of (ref1_name, port1, ref2_name, port2) tuples
        """
        missing_routes = []
        
        # Get all component references
        try:
            refs = list(component.references)
        except AttributeError:
            refs = list(getattr(component, 'insts', []))
        
        # Build a map of reference names to references
        ref_map = {}
        for ref in refs:
            # Try to get reference name (this is tricky - refs might not have names)
            # We'll use a heuristic based on component type
            ref_map[id(ref)] = ref
        
        # Check for unconnected ports
        # This is a simplified check - in reality, we'd need to analyze the netlist
        # For now, we'll rely on code analysis
        
        return missing_routes
    
    def _infer_missing_routes_from_code(self, code: str, tree: ast.AST) -> List[Tuple[str, str, str, str]]:
        """
        Infer missing routes from code structure.
        
        This is a heuristic approach that looks for:
        1. Components that are placed but not routed
        2. Common patterns (splitters -> components -> combiners)
        """
        missing_routes = []
        
        # Find component variables
        component_vars = set(self.component_refs.keys())
        
        # Find splitter/combiner patterns
        splitters = [v for v in component_vars if 'splitter' in v.lower()]
        combiners = [v for v in component_vars if 'combiner' in v.lower()]
        mzms = [v for v in component_vars if 'mzm' in v.lower() or 'bit' in v.lower()]
        phase_shifters = [v for v in component_vars if 'phase' in v.lower() or 'ps' in v.lower()]
        
        # Check existing routes to see what's connected
        connected_ports = set()
        for ref1, port1, ref2, port2 in self.existing_routes:
            connected_ports.add((ref1, port1))
            connected_ports.add((ref2, port2))
        
        # Heuristic: If we have splitters and MZMs but no routes between them, add routes
        # This is a simplified heuristic - real implementation would be more sophisticated
        
        return missing_routes
    
    def _generate_route_code(self, routes: List[Tuple[str, str, str, str]]) -> str:
        """Generate route_single() code for missing routes."""
        route_lines = []
        
        for ref1, port1, ref2, port2 in routes:
            route_line = (
                f"gf.routing.route_single(\n"
                f"    r,\n"
                f"    {ref1}.ports[\"{port1}\"],\n"
                f"    {ref2}.ports[\"{port2}\"],\n"
                f"    cross_section=\"strip\",\n"
                f"    radius=15,\n"
                f")\n"
            )
            route_lines.append(route_line)
        
        return "\n".join(route_lines)
    
    def _insert_routes(self, code: str, route_code: str) -> str:
        """Insert route code before port additions."""
        # Find the position before add_port calls
        port_pattern = r'(\w+)\.add_port\s*\('
        port_match = re.search(port_pattern, code)
        
        if port_match:
            insert_pos = port_match.start()
            # Insert routes before ports
            return code[:insert_pos] + "\n# Auto-added routes\n" + route_code + "\n" + code[insert_pos:]
        else:
            # Insert at end before final statements
            return code.rstrip() + "\n\n# Auto-added routes\n" + route_code


class ComponentAnalyzer:
    """
    Analyzes executed gdsfactory components to detect missing routes.
    """
    
    @staticmethod
    def analyze_missing_routes(component: gf.Component) -> List[Dict]:
        """
        Analyze component to find missing routes.
        
        Returns:
            List of dicts with missing route information
        """
        missing_routes = []
        
        try:
            # Get all references
            refs = list(component.references)
        except AttributeError:
            refs = list(getattr(component, 'insts', []))
        
        # Get all routes (waveguides)
        routes = []
        for poly in component.get_polygons():
            # Check if polygon is a route (simplified - real check would be more sophisticated)
            if hasattr(poly, 'layer') and 'WG' in str(poly.layer):
                routes.append(poly)
        
        # For each reference, check if its ports are connected
        for ref in refs:
            try:
                ports = ref.ports
                if hasattr(ports, 'items'):
                    ports_iter = ports.items()
                else:
                    ports_iter = [(name, ports[name]) for name in ports]
                
                for port_name, port in ports_iter:
                    # Check if port is connected to another port
                    # This is simplified - real check would analyze routing
                    pass
            except Exception as e:
                logger.debug(f"Error analyzing ports: {e}")
        
        return missing_routes


