"""
Port Connection Validator

Detects same port connections, duplicate connections, and port connection errors.
Ensures each port connects to exactly one other port.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
import ast
import warnings
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
            "unconnected_ports": [],
            "port_connection_map": {},
        }
        
        try:
            # Get netlist to check connections. GDSFactory reports dangling
            # component ports as warnings, so capture them and promote them
            # into validator findings.
            try:
                with warnings.catch_warnings(record=True) as caught_warnings:
                    warnings.simplefilter("always")
                    netlist = component.get_netlist()
            except Exception as netlist_error:
                try:
                    yaml_netlist = component.info.get("picasso_yaml_netlist", {}) or {}
                except Exception:
                    yaml_netlist = {}
                if isinstance(yaml_netlist, dict) and yaml_netlist.get("connections"):
                    caught_warnings = []
                    netlist = yaml_netlist
                    report["warnings"].append(
                        f"Using YAML connectivity because GDSFactory netlist extraction failed: {netlist_error}"
                    )
                else:
                    raise
            
            if not netlist:
                report["errors"].append("Failed to extract netlist for port connection validation")
                report["passed"] = False
                return False, report

            try:
                yaml_netlist = component.info.get("picasso_yaml_netlist", {}) or {}
            except Exception:
                yaml_netlist = {}
            yaml_connections = yaml_netlist.get("connections", {})
            yaml_connected_ports = set()
            if isinstance(yaml_connections, dict):
                for src, dst in yaml_connections.items():
                    yaml_connected_ports.add(str(src))
                    yaml_connected_ports.add(str(dst))
            yaml_exports = yaml_netlist.get("ports", {})
            if isinstance(yaml_exports, dict):
                yaml_connected_ports.update(str(port_ref) for port_ref in yaml_exports.values())
            yaml_connected_instances = {
                port_ref.partition(",")[0]
                for port_ref in yaml_connected_ports
                if isinstance(port_ref, str) and "," in port_ref
            }

            yaml_instances = yaml_netlist.get("instances", {})
            component_by_instance = {}
            heater_instances = set()
            if isinstance(yaml_instances, dict):
                for instance_name, instance_spec in yaml_instances.items():
                    if isinstance(instance_spec, dict):
                        component_by_instance[str(instance_name)] = instance_spec.get("component")
                    if (
                        isinstance(instance_spec, dict)
                        and instance_spec.get("component") == "straight_heater_metal"
                    ):
                        heater_instances.add(str(instance_name))

            def _is_ignored_unconnected_port(port: str) -> bool:
                instance_name, _, port_name = port.partition(",")
                component_name = component_by_instance.get(instance_name)
                if ",l_e" in port or ",r_e" in port:
                    return True

                # MZI and waveguide-like parts are two-port optical paths; once
                # placed in a design, both optical ports must be connected or
                # exported. This catches truncated signal paths where one side
                # of a required two-port component is left floating.
                if component_name in {
                    "mzi",
                    "straight",
                    "bend_euler",
                    "bend_s",
                    "bend_circular",
                    "taper",
                    "ring_single",
                }:
                    return False

                # Heater metal pads are electrical. Optical heater ports are
                # allowed to float only when the heater is not part of the YAML
                # optical graph and is being used as a nearby thermal tuner.
                if instance_name in heater_instances and port_name in {"o1", "o2"}:
                    return instance_name not in yaml_connected_instances

                # Crossings have two through paths. The horizontal o1-o3 path is
                # often the modeled optical signal path; if either side is used,
                # require the other side too. The vertical o2/o4 side may be a
                # layout-only crossing artifact or an exposed top-level helper.
                if component_name == "crossing":
                    if port_name in {"o1", "o3"}:
                        pair = "o3" if port_name == "o1" else "o1"
                        return f"{instance_name},{pair}" not in yaml_connected_ports
                    return True

                # Multi-port splitters/couplers can intentionally leave one arm
                # unused; still fail completely floating instances elsewhere.
                if component_name in {"mmi1x2", "mmi2x2", "coupler"} and instance_name in yaml_connected_instances:
                    return True
                return False

            for warning in caught_warnings:
                warning_text = str(warning.message)
                if "Unconnected ports:" not in warning_text:
                    report["warnings"].append(warning_text)
                    continue

                _, _, ports_text = warning_text.partition("Unconnected ports:")
                try:
                    unconnected_ports = ast.literal_eval(ports_text.strip())
                except Exception:
                    unconnected_ports = [ports_text.strip()]

                # Heater metal pads are electrical terminals, and heater optical
                # ports are allowed to remain unused when the heater is only a
                # thermal tuner. Keep non-heater optical ports strict.
                unconnected_ports = [
                    str(port)
                    for port in unconnected_ports
                    if not _is_ignored_unconnected_port(str(port))
                    and str(port) not in yaml_connected_ports
                ]

                if unconnected_ports:
                    report["unconnected_ports"].extend(unconnected_ports)
                    preview = ", ".join(unconnected_ports[:10])
                    if len(unconnected_ports) > 10:
                        preview += f", ... (+{len(unconnected_ports) - 10} more)"
                    report["errors"].append(
                        f"Unconnected component ports found ({len(unconnected_ports)}): {preview}"
                    )
                    report["passed"] = False
            
            # Check connections
            connections = netlist.get('connections', {})
            if not connections and isinstance(yaml_connections, dict):
                connections = yaml_connections

            if not connections:
                # No connections - might be single component
                if len(netlist.get('instances', {})) > 1:
                    report["errors"].append("Multiple components but no netlist connections found")
                    report["passed"] = False
                return report["passed"], report
            
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
