"""
YAML Netlist Helper Functions

Helper functions for extracting netlists from components and converting to/from YAML.
"""

import yaml
import logging
import gdsfactory as gf
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_netlist_from_component(component: gf.Component) -> Optional[Dict]:
    """
    Extract netlist from GDSFactory component.
    
    Args:
        component: GDSFactory component
        
    Returns:
        Netlist dictionary or None if extraction fails
    """
    try:
        netlist = component.get_netlist()
        return netlist
    except Exception as e:
        logger.warning(f"Failed to extract netlist: {e}")
        return None


def netlist_to_yaml(netlist: Dict) -> Optional[str]:
    """
    Convert netlist dictionary to YAML string.
    
    Args:
        netlist: Netlist dictionary
        
    Returns:
        YAML string or None if conversion fails
    """
    try:
        yaml_str = yaml.dump(netlist, default_flow_style=False, sort_keys=False, allow_unicode=False)
        return yaml_str
    except Exception as e:
        logger.warning(f"Failed to convert netlist to YAML: {e}")
        return None


def yaml_to_component(yaml_str: str) -> Tuple[Optional[gf.Component], Optional[str]]:
    """
    Convert YAML string to GDSFactory component.
    
    Args:
        yaml_str: YAML netlist string
        
    Returns:
        (component, error_message)
    """
    try:
        component = gf.read.from_yaml(yaml_str)
        return component, None
    except Exception as e:
        return None, str(e)


