"""
Netlist Validator

Pre-execution validation of JSON/YAML netlists.
Checks routing feasibility, placement constraints, and detects errors before GDS generation.
"""

import json
import yaml
import logging
from typing import Dict, List, Tuple, Optional
from ..config import (
    CHECK_ROUTING_FEASIBILITY,
    CHECK_PLACEMENT_CONSTRAINTS,
    MIN_NETLIST_SPACING
)

logger = logging.getLogger(__name__)


class NetlistValidator:
    """Validates netlists before GDS generation."""

    def __init__(self):
        """Initialize netlist validator."""
        self.min_spacing = MIN_NETLIST_SPACING

    def validate(self, netlist_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate netlist.

        Args:
            netlist_data: Netlist dictionary

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []
        
        # Check basic structure
        structure_issues = self._check_structure(netlist_data)
        issues.extend(structure_issues)
        
        if issues:
            return False, issues
        
        # Check routing feasibility
        if CHECK_ROUTING_FEASIBILITY:
            routing_issues = self._check_routing_feasibility(netlist_data)
            issues.extend(routing_issues)
        
        # Check placement constraints
        if CHECK_PLACEMENT_CONSTRAINTS:
            placement_issues = self._check_placement_constraints(netlist_data)
            issues.extend(placement_issues)
        
        # Check port connections
        port_issues = self._check_port_connections(netlist_data)
        issues.extend(port_issues)
        
        is_valid = len(issues) == 0
        return is_valid, issues

    def parse_netlist(self, netlist_text: str, format_type: str = "auto") -> Optional[Dict]:
        """
        Parse netlist from text (JSON or YAML).

        Args:
            netlist_text: Netlist text
            format_type: 'json', 'yaml', or 'auto'

        Returns:
            Parsed netlist dictionary or None
        """
        # Try to detect format
        if format_type == "auto":
            if netlist_text.strip().startswith('{'):
                format_type = "json"
            else:
                format_type = "yaml"
        
        try:
            if format_type == "json":
                # Remove markdown code fences if present
                text = netlist_text.strip()
                if text.startswith('```'):
                    text = text.split('```')[1]
                    if text.startswith('json'):
                        text = text[4:]
                return json.loads(text)
            elif format_type == "yaml":
                # Remove markdown code fences if present
                text = netlist_text.strip()
                if text.startswith('```'):
                    text = text.split('```')[1]
                    if text.startswith('yaml'):
                        text = text[4:]
                return yaml.safe_load(text)
        except Exception as e:
            logger.error(f"Error parsing netlist: {e}")
            return None

    def _check_structure(self, netlist: Dict) -> List[str]:
        """Check basic netlist structure."""
        issues = []
        
        # Check for required top-level keys
        if 'netlist' in netlist:
            netlist = netlist['netlist']
        
        required_keys = ['instances', 'connections', 'ports']
        for key in required_keys:
            if key not in netlist:
                issues.append(f"Missing required key: '{key}'")
        
        # Check instances
        if 'instances' in netlist:
            if not isinstance(netlist['instances'], dict):
                issues.append("'instances' must be a dictionary")
            elif len(netlist['instances']) == 0:
                issues.append("No instances defined in netlist")
        
        # Check connections
        if 'connections' in netlist:
            if not isinstance(netlist['connections'], dict):
                issues.append("'connections' must be a dictionary")
        
        # Check ports
        if 'ports' in netlist:
            if not isinstance(netlist['ports'], dict):
                issues.append("'ports' must be a dictionary")
        
        return issues

    def _check_routing_feasibility(self, netlist: Dict) -> List[str]:
        """Check if routing is feasible based on connections."""
        issues = []
        
        if 'netlist' in netlist:
            netlist = netlist['netlist']
        
        instances = netlist.get('instances', {})
        connections = netlist.get('connections', {})
        
        # Check that all connections reference valid instances
        for conn_key, conn_value in connections.items():
            # Parse connection: "instance1,port1": "instance2,port2"
            if ',' in conn_key:
                src_instance = conn_key.split(',')[0]
                if src_instance not in instances:
                    issues.append(f"Connection references unknown instance: '{src_instance}'")
            
            if isinstance(conn_value, str) and ',' in conn_value:
                dst_instance = conn_value.split(',')[0]
                if dst_instance not in instances:
                    issues.append(f"Connection references unknown instance: '{dst_instance}'")
        
        # Check for unconnected instances
        connected_instances = set()
        for conn_key, conn_value in connections.items():
            if ',' in conn_key:
                connected_instances.add(conn_key.split(',')[0])
            if isinstance(conn_value, str) and ',' in conn_value:
                connected_instances.add(conn_value.split(',')[0])
        
        unconnected = set(instances.keys()) - connected_instances
        if len(unconnected) > 0 and len(instances) > 1:
            issues.append(f"Unconnected instances detected: {', '.join(unconnected)}")
        
        return issues

    def _check_placement_constraints(self, netlist: Dict) -> List[str]:
        """Check placement constraints from netlist."""
        issues = []
        
        if 'netlist' in netlist:
            netlist = netlist['netlist']
        
        # Check placements if present
        placements = netlist.get('placements', {})
        if placements:
            positions = []
            for inst_name, pos in placements.items():
                if isinstance(pos, dict):
                    x = pos.get('x', 0)
                    y = pos.get('y', 0)
                    positions.append((inst_name, x, y))
            
            # Check spacing between placements
            for i, (name1, x1, y1) in enumerate(positions):
                for name2, x2, y2 in positions[i+1:]:
                    distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    if 0 < distance < self.min_spacing:
                        issues.append(
                            f"Placement spacing violation: '{name1}' and '{name2}' are "
                            f"{distance:.1f}µm apart (minimum: {self.min_spacing}µm)"
                        )
        
        return issues

    def _check_port_connections(self, netlist: Dict) -> List[str]:
        """Check port connection validity."""
        issues = []
        
        if 'netlist' in netlist:
            netlist = netlist['netlist']
        
        instances = netlist.get('instances', {})
        connections = netlist.get('connections', {})
        ports = netlist.get('ports', {})
        
        # Check that port connections reference valid instances
        for port_name, port_ref in ports.items():
            if isinstance(port_ref, str) and ',' in port_ref:
                inst_name = port_ref.split(',')[0]
                if inst_name not in instances:
                    issues.append(f"Port '{port_name}' references unknown instance: '{inst_name}'")
        
        return issues


