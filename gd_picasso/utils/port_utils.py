"""
Port utilities for GDSFactory DPorts compatibility.

Handles differences between older dict-like port objects and newer DPorts objects.
"""

from typing import List, Dict, Tuple, Any, Optional
import gdsfactory as gf


def get_port_names(ports) -> List[str]:
    """
    Get list of port names from a ports object.

    Args:
        ports: GDSFactory ports object (dict-like or DPorts)

    Returns:
        List of port names
    """
    if hasattr(ports, 'keys'):
        return list(ports.keys())
    elif hasattr(ports, '__iter__'):
        # DPorts or similar - iterate to get names
        return [port.name for port in ports]
    else:
        return []


def get_port_items(ports) -> List[Tuple[str, Any]]:
    """
    Get (name, port) items from a ports object.

    Args:
        ports: GDSFactory ports object

    Returns:
        List of (name, port) tuples
    """
    if hasattr(ports, 'items'):
        return list(ports.items())
    elif hasattr(ports, '__iter__'):
        # DPorts or similar
        return [(port.name, port) for port in ports]
    else:
        return []


def get_port_count(ports) -> int:
    """Get number of ports."""
    return len(get_port_names(ports))


def has_port(ports, port_name: str) -> bool:
    """Check if port exists."""
    return port_name in get_port_names(ports)


def get_port(ports, port_name: str) -> Optional[Any]:
    """Get port by name."""
    port_names = get_port_names(ports)
    if port_name not in port_names:
        return None
    
    if hasattr(ports, '__getitem__'):
        return ports[port_name]
    elif hasattr(ports, '__iter__'):
        # DPorts - find by name
        for port in ports:
            if port.name == port_name:
                return port
    
    return None

