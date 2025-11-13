"""
Port Matcher

Handles port name mapping across different gdsfactory versions.
Detects version and provides port mapping reference for LLM prompts.
"""

import logging
import gdsfactory as gf
from typing import Dict, List, Optional, Tuple
from ..config import PORT_NAME_MAPPINGS, AUTO_DETECT_GDSFACTORY_VERSION, DEFAULT_GDSFACTORY_VERSION

logger = logging.getLogger(__name__)


class PortMatcher:
    """Handles port matching across gdsfactory versions."""

    def __init__(self):
        """Initialize port matcher."""
        self.gdsfactory_version = None
        self.port_mappings = PORT_NAME_MAPPINGS.copy()
        self._detect_version()

    def _detect_version(self):
        """Detect gdsfactory version."""
        if AUTO_DETECT_GDSFACTORY_VERSION:
            try:
                import gdsfactory as gf
                if hasattr(gf, '__version__'):
                    self.gdsfactory_version = gf.__version__
                else:
                    self.gdsfactory_version = DEFAULT_GDSFACTORY_VERSION
                logger.info(f"Detected gdsfactory version: {self.gdsfactory_version}")
            except Exception as e:
                logger.warning(f"Could not detect gdsfactory version: {e}")
                self.gdsfactory_version = DEFAULT_GDSFACTORY_VERSION
        else:
            self.gdsfactory_version = DEFAULT_GDSFACTORY_VERSION

    def get_version(self) -> str:
        """Get detected gdsfactory version."""
        return self.gdsfactory_version

    def map_port_name(self, port_name: str, component_type: Optional[str] = None) -> str:
        """
        Map port name to current version format.

        Args:
            port_name: Port name to map
            component_type: Optional component type for context

        Returns:
            Mapped port name
        """
        # Check if port name needs mapping
        if port_name in self.port_mappings:
            mapped = self.port_mappings[port_name]
            logger.debug(f"Mapped port '{port_name}' -> '{mapped}'")
            return mapped
        
        # If port name follows standard o1, o2, o3 pattern, return as-is
        if port_name.startswith('o') and port_name[1:].isdigit():
            return port_name
        
        # If port name follows I1, I2, O1, O2 pattern, map it
        if len(port_name) == 2 and port_name[0] in ['I', 'O'] and port_name[1].isdigit():
            # Convert I1->o1, O1->o1, etc.
            return f"o{port_name[1]}"
        
        return port_name

    def validate_port_exists(
        self,
        component: gf.Component,
        port_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that port exists on component.

        Args:
            component: GDSFactory component
            port_name: Port name to check

        Returns:
            (exists, error_message)
        """
        try:
            # Map port name first
            mapped_port = self.map_port_name(port_name)
            
            # Check if port exists
            if mapped_port in component.ports:
                return True, None
            
            # Try original port name
            if has_port(component.ports, port_name):
                return True, None
            
            # List available ports
            available_ports = get_port_names(component.ports)
            error_msg = (
                f"Port '{port_name}' (mapped: '{mapped_port}') not found. "
                f"Available ports: {available_ports}"
            )
            return False, error_msg
            
        except Exception as e:
            return False, f"Error validating port: {str(e)}"

    def get_port_reference(self, component_type: str) -> Optional[Dict[str, List[str]]]:
        """
        Get port reference for a component type.

        Args:
            component_type: Component type (e.g., 'mmi1x2', 'straight_heater_metal')

        Returns:
            Dictionary with port information or None
        """
        try:
            # Try to instantiate component to get ports
            comp_func = getattr(gf.components, component_type, None)
            if comp_func is None:
                logger.warning(f"Component type '{component_type}' not found")
                return None
            
            comp = comp_func()
            ports = get_port_names(comp.ports)
            
            return {
                "component_type": component_type,
                "ports": ports,
                "port_count": len(ports)
            }
            
        except Exception as e:
            logger.warning(f"Could not get port reference for '{component_type}': {e}")
            return None

    def generate_port_mapping_reference(self, component_types: List[str]) -> str:
        """
        Generate port mapping reference for LLM prompts.

        Args:
            component_types: List of component types to include

        Returns:
            Formatted port reference string
        """
        references = []
        references.append("PORT NAME REFERENCE:")
        references.append(f"GDSFactory version: {self.gdsfactory_version}")
        references.append("")
        
        for comp_type in component_types:
            ref = self.get_port_reference(comp_type)
            if ref:
                references.append(f"{comp_type}:")
                references.append(f"  Ports: {', '.join(ref['ports'])}")
                references.append("")
        
        references.append("NOTE: Port names are case-sensitive and must match exactly.")
        references.append("Common ports: o1 (input), o2, o3 (outputs) for MMI components.")
        
        return "\n".join(references)

