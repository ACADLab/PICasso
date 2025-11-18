"""
Port Connection Validator

Detects same port connections, duplicate connections, and port connection errors.
Ensures each port connects to exactly one other port.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
import gdsfactory as gf
from ..utils.port_utils import get_port_items

logger = logging.getLogger(__name__)


class PortConnectionValidator:
    """Validates port connections in designs."""

    def validate(self, component: gf.Component) -> Tuple[bool, Dict]:
        """
        Validate port connections.
        
        Checks:
        1. Each port connects to exactly one other port (no same port connections)
        2. No duplicate connections
        3. Port connection graph is valid
        
        Args:
            component: GDSFactory component to check
            
        Returns:
            (is_valid, validation_report)
        """
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "same_port_connections": [],
            "duplicate_connections": [],
            "port_connection_map": {},
        }
        
        try:
            # Get netlist to check connections
            netlist = component.get_netlist()
            
            if not netlist:
                report["errors"].append("Failed to extract netlist for port connection validation")
                report["passed"] = False
                return False, report
            
            # Check connections
            connections = netlist.get('connections', {})
            if not connections:
                # No connections - might be single component
                if len(netlist.get('instances', {})) > 1:
                    report["warnings"].append("Multiple components but no connections found")
                return True, report
            
            # Build port connection map
            port_connections = {}  # {port_name: [connected_ports]}
            
            for source_port, target_ports in connections.items():
                if source_port not in port_connections:
                    port_connections[source_port] = []
                
                # Handle both single port and list of ports
                if isinstance(target_ports, list):
                    port_connections[source_port].extend(target_ports)
                else:
                    port_connections[source_port].append(target_ports)
            
            # Check for same port connections (port connected to itself)
            for port, connected in port_connections.items():
                if port in connected:
                    report["same_port_connections"].append(port)
                    report["errors"].append(f"Port {port} is connected to itself (same port connection)")
                    report["passed"] = False
            
            # Check for duplicate connections
            for port, connected in port_connections.items():
                if len(connected) > 1:
                    # Check if all connections are the same
                    if len(set(connected)) < len(connected):
                        report["duplicate_connections"].append(port)
                        report["warnings"].append(f"Port {port} has duplicate connections: {connected}")
            
            # Check for ports connected to multiple other ports (should be exactly one)
            for port, connected in port_connections.items():
                unique_connections = set(connected)
                if len(unique_connections) > 1:
                    report["errors"].append(
                        f"Port {port} is connected to multiple ports: {unique_connections} "
                        f"(should connect to exactly one port)"
                    )
                    report["passed"] = False
            
            report["port_connection_map"] = port_connections
            
        except Exception as e:
            # If get_netlist() fails with "More than two connected optical ports", that's a port connection error
            error_str = str(e)
            if "More than two connected optical ports" in error_str or "more than two" in error_str.lower():
                report["errors"].append(f"Port connection error: {error_str}")
                report["passed"] = False
            else:
                report["warnings"].append(f"Could not validate port connections: {e}")
        
        return report["passed"], report

    def generate_feedback(self, report: Dict) -> str:
        """Generate feedback for fixing port connection errors."""
        feedback = []
        
        if report["same_port_connections"]:
            feedback.append("SAME PORT CONNECTIONS DETECTED:")
            for port in report["same_port_connections"]:
                feedback.append(f"  - Port {port} is connected to itself")
            feedback.append("\nFIX: Remove self-connections from routes section")
        
        if report.get("errors"):
            for error in report["errors"]:
                if "multiple ports" in error.lower():
                    feedback.append(f"\nPORT CONNECTION ERROR: {error}")
                    feedback.append("FIX: Each port should connect to exactly one other port")
                    feedback.append("  - Check routes.optical.links section")
                    feedback.append("  - Ensure format: 'source,port: target,port' (one-to-one mapping)")
        
        return "\n".join(feedback)


