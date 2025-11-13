"""
Netlist Converter

Converts JSON/YAML netlists to gdsfactory Components.
Handles port name mapping and proper routing during conversion.
"""

import logging
import gdsfactory as gf
from typing import Dict, Optional, Tuple, List
from .netlist_validator import NetlistValidator
from ..port_matching.port_matcher import PortMatcher

logger = logging.getLogger(__name__)


class NetlistConverter:
    """Converts netlists to gdsfactory Components."""

    def __init__(self, port_matcher: Optional[PortMatcher] = None):
        """
        Initialize netlist converter.

        Args:
            port_matcher: Optional port matcher for version compatibility
        """
        self.validator = NetlistValidator()
        self.port_matcher = port_matcher or PortMatcher()

    def convert_to_component(
        self,
        netlist_data: Dict,
        auto_route: bool = True
    ) -> Tuple[Optional[gf.Component], Optional[str]]:
        """
        Convert netlist to gdsfactory Component.

        Args:
            netlist_data: Netlist dictionary
            auto_route: Whether to automatically route connections

        Returns:
            (component, error_message)
        """
        # Validate netlist first
        is_valid, issues = self.validator.validate(netlist_data)
        if not is_valid:
            return None, f"Netlist validation failed: {', '.join(issues)}"
        
        try:
            # Extract netlist structure
            if 'netlist' in netlist_data:
                netlist = netlist_data['netlist']
            else:
                netlist = netlist_data
            
            instances = netlist.get('instances', {})
            connections = netlist.get('connections', {})
            ports = netlist.get('ports', {})
            placements = netlist.get('placements', {})
            
            # Create component
            component = gf.Component()
            
            # Add instances
            instance_refs = {}
            for inst_name, inst_spec in instances.items():
                ref = self._add_instance(component, inst_name, inst_spec, placements.get(inst_name))
                if ref is None:
                    return None, f"Failed to add instance: {inst_name}"
                instance_refs[inst_name] = ref
            
            # Route connections if auto_route enabled
            if auto_route and connections:
                routing_errors = self._route_connections(component, instance_refs, connections)
                if routing_errors:
                    logger.warning(f"Routing errors: {routing_errors}")
            
            # Add external ports
            for port_name, port_ref in ports.items():
                self._add_external_port(component, port_name, port_ref, instance_refs)
            
            return component, None
            
        except Exception as e:
            logger.error(f"Error converting netlist: {e}")
            return None, str(e)

    def _add_instance(
        self,
        component: gf.Component,
        inst_name: str,
        inst_spec: Dict,
        placement: Optional[Dict]
    ) -> Optional[gf.Component]:
        """
        Add instance to component.

        Args:
            component: Parent component
            inst_name: Instance name
            inst_spec: Instance specification
            placement: Optional placement information

        Returns:
            Component reference or None
        """
        try:
            # Parse instance specification
            if isinstance(inst_spec, str):
                comp_type = inst_spec
                settings = {}
            elif isinstance(inst_spec, dict):
                comp_type = inst_spec.get('component', inst_spec.get('component_type', ''))
                settings = inst_spec.get('settings', {})
            else:
                logger.error(f"Invalid instance specification for '{inst_name}'")
                return None
            
            # Get component function
            comp_func = getattr(gf.components, comp_type, None)
            if comp_func is None:
                logger.error(f"Component type '{comp_type}' not found")
                return None
            
            # Create component with settings
            comp = comp_func(**settings)
            
            # Add to parent
            ref = component.add_ref(comp)
            
            # Apply placement
            if placement:
                x = placement.get('x', 0)
                y = placement.get('y', 0)
                rotation = placement.get('rotation', 0)
                ref.move((x, y))
                if rotation != 0:
                    ref.rotate(rotation)
            
            return ref
            
        except Exception as e:
            logger.error(f"Error adding instance '{inst_name}': {e}")
            return None

    def _route_connections(
        self,
        component: gf.Component,
        instance_refs: Dict[str, gf.Component],
        connections: Dict
    ) -> List[str]:
        """
        Route connections between instances.

        Args:
            component: Parent component
            instance_refs: Dictionary of instance references
            connections: Connections dictionary

        Returns:
            List of routing errors
        """
        errors = []
        
        # Group connections by source instance for route_bundle
        source_groups = {}
        for conn_key, conn_value in connections.items():
            if ',' in conn_key:
                src_inst, src_port = conn_key.split(',', 1)
                if src_inst not in source_groups:
                    source_groups[src_inst] = []
                source_groups[src_inst].append((conn_key, conn_value))
        
        # Route each group
        for src_inst, conn_list in source_groups.items():
            if src_inst not in instance_refs:
                errors.append(f"Source instance '{src_inst}' not found")
                continue
            
            src_ref = instance_refs[src_inst]
            src_ports = []
            dst_ports = []
            
            for conn_key, conn_value in conn_list:
                # Parse source port
                _, src_port = conn_key.split(',', 1)
                src_port = self.port_matcher.map_port_name(src_port)
                
                # Parse destination
                if isinstance(conn_value, str) and ',' in conn_value:
                    dst_inst, dst_port = conn_value.split(',', 1)
                    dst_port = self.port_matcher.map_port_name(dst_port)
                    
                    if dst_inst in instance_refs:
                        dst_ref = instance_refs[dst_inst]
                        src_ports.append(src_ref.ports[src_port])
                        dst_ports.append(dst_ref.ports[dst_port])
                    else:
                        errors.append(f"Destination instance '{dst_inst}' not found")
            
            # Route bundle if we have ports
            if src_ports and dst_ports and len(src_ports) == len(dst_ports):
                try:
                    gf.routing.route_bundle(
                        component,
                        src_ports,
                        dst_ports,
                        cross_section='strip',
                        radius=15,
                        separation=15
                    )
                except Exception as e:
                    errors.append(f"Routing error for '{src_inst}': {e}")
        
        return errors

    def _add_external_port(
        self,
        component: gf.Component,
        port_name: str,
        port_ref: str,
        instance_refs: Dict[str, gf.Component]
    ):
        """
        Add external port to component.

        Args:
            component: Component to add port to
            port_name: External port name
            port_ref: Reference to instance port (e.g., "instance1,o1")
            instance_refs: Dictionary of instance references
        """
        try:
            if ',' in port_ref:
                inst_name, inst_port = port_ref.split(',', 1)
                inst_port = self.port_matcher.map_port_name(inst_port)
                
                if inst_name in instance_refs:
                    inst_ref = instance_refs[inst_name]
                    if inst_port in inst_ref.ports:
                        component.add_port(port_name, port=inst_ref.ports[inst_port])
                    else:
                        logger.warning(f"Port '{inst_port}' not found on '{inst_name}'")
                else:
                    logger.warning(f"Instance '{inst_name}' not found for port '{port_name}'")
        except Exception as e:
            logger.error(f"Error adding external port '{port_name}': {e}")

