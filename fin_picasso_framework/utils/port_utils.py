"""
Port Utilities

Helper functions to handle different GDSFactory port interfaces (dict-like vs DPorts).
"""

from typing import List, Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_port_names(ports) -> List[str]:
    """
    Get list of port names from ports object (handles both dict-like and DPorts).
    
    Args:
        ports: Ports object (dict-like or DPorts)
        
    Returns:
        List of port names
    """
    try:
        # Try dict-like interface first (older gdsfactory)
        if hasattr(ports, 'keys'):
            return list(ports.keys())
        elif hasattr(ports, '__iter__'):
            # DPorts or similar - iterate directly
            return [p.name if hasattr(p, 'name') else str(p) for p in ports]
        else:
            return []
    except Exception as e:
        logger.debug(f"Error getting port names: {e}")
        return []


def get_port_items(ports) -> List[Tuple[str, Any]]:
    """
    Get list of (port_name, port) tuples from ports object.
    
    Args:
        ports: Ports object (dict-like or DPorts)
        
    Returns:
        List of (port_name, port) tuples
    """
    try:
        # Try dict-like interface first (older gdsfactory)
        if hasattr(ports, 'items'):
            return list(ports.items())
        elif hasattr(ports, '__iter__'):
            # DPorts or similar - iterate directly
            return [(p.name if hasattr(p, 'name') else str(p), p) for p in ports]
        else:
            return []
    except Exception as e:
        logger.debug(f"Error getting port items: {e}")
        return []


def get_port_count(ports) -> int:
    """
    Get count of ports (handles both dict-like and DPorts).
    
    Args:
        ports: Ports object (dict-like or DPorts)
        
    Returns:
        Number of ports
    """
    try:
        if hasattr(ports, '__len__'):
            return len(ports)
        elif hasattr(ports, '__iter__'):
            return len(list(ports))
        else:
            return 0
    except Exception as e:
        logger.debug(f"Error getting port count: {e}")
        return 0


def has_port(ports, port_name: str) -> bool:
    """
    Check if port exists (handles both dict-like and DPorts).
    
    Args:
        ports: Ports object (dict-like or DPorts)
        port_name: Name of port to check
        
    Returns:
        True if port exists
    """
    try:
        # Try dict-like interface first
        if hasattr(ports, '__contains__'):
            return port_name in ports
        elif hasattr(ports, '__iter__'):
            # DPorts - check by name
            return any((p.name if hasattr(p, 'name') else str(p)) == port_name for p in ports)
        else:
            return False
    except Exception as e:
        logger.debug(f"Error checking port existence: {e}")
        return False


def get_port(ports, port_name: str) -> Optional[Any]:
    """
    Get port by name (handles both dict-like and DPorts).
    
    Args:
        ports: Ports object (dict-like or DPorts)
        port_name: Name of port to get
        
    Returns:
        Port object or None
    """
    try:
        # Try dict-like interface first
        if hasattr(ports, '__getitem__'):
            try:
                return ports[port_name]
            except (KeyError, TypeError):
                pass
        
        # DPorts - search by name
        if hasattr(ports, '__iter__'):
            for p in ports:
                p_name = p.name if hasattr(p, 'name') else str(p)
                if p_name == port_name:
                    return p
        
        return None
    except Exception as e:
        logger.debug(f"Error getting port: {e}")
        return None


