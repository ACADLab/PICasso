"""
YAML Netlist Helper - Using GDSFactory Native YAML Support

Based on: https://gdsfactory.github.io/gdsfactory/notebooks/10_yaml_component.html

This module provides utilities to:
1. Extract netlist from Python-generated components
2. Convert netlist to YAML format
3. Validate and fix YAML netlists
4. Rebuild components from YAML using gf.read.from_yaml()
"""

import yaml
import logging
import gdsfactory as gf
from typing import Dict, Optional, Tuple
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


def extract_netlist_from_component(component: gf.Component) -> Dict:
    """
    Extract netlist from a gdsfactory Component.
    
    Args:
        component: GDSFactory component
        
    Returns:
        Netlist dictionary in GDSFactory format, or empty dict if extraction fails
        
    Note:
        Some components with complex port connections (e.g., external ports connected
        to multiple internal ports) may fail with "More than two connected optical ports".
        This is a GDSFactory limitation, not a YAML issue. In such cases, we return
        an empty dict and skip YAML-based fixes.
    """
    try:
        netlist = component.get_netlist()
        return netlist
    except Exception as e:
        error_msg = str(e)
        # Check if it's the "More than two connected ports" error (GDSFactory limitation)
        if "more than two connected" in error_msg.lower():
            logger.warning(f"⚠️  Netlist extraction failed: {error_msg}")
            logger.warning("   This is a GDSFactory limitation for complex port connections.")
            logger.warning("   Skipping YAML-based fixes for this component.")
        else:
            logger.error(f"Error extracting netlist: {e}")
        return {}


def netlist_to_yaml(netlist: Dict) -> str:
    """
    Convert netlist dictionary to YAML string.
    
    Args:
        netlist: Netlist dictionary
        
    Returns:
        YAML string
    """
    try:
        # GDSFactory expects YAML format with specific structure
        # Ensure placements exist (required for routing)
        if 'placements' not in netlist:
            netlist['placements'] = {}
        
        # Convert to YAML
        yaml_str = yaml.dump(netlist, default_flow_style=False, sort_keys=False)
        return yaml_str
    except Exception as e:
        logger.error(f"Error converting netlist to YAML: {e}")
        return ""


def yaml_to_component(yaml_str: str) -> Tuple[Optional[gf.Component], Optional[str]]:
    """
    Convert YAML string to gdsfactory Component using native gf.read.from_yaml().
    
    Based on: https://gdsfactory.github.io/gdsfactory/notebooks/10_yaml_component.html
    
    Args:
        yaml_str: YAML string
        
    Returns:
        (component, error_message)
    """
    try:
        # GDSFactory's from_yaml can take a string directly
        component = gf.read.from_yaml(yaml_str)
        return component, None
    except Exception as e:
        error_msg = f"Error converting YAML to component: {e}"
        logger.error(error_msg)
        return None, error_msg


def fix_yaml_spacing(yaml_str: str, min_spacing: float = 50.0) -> str:
    """
    Fix spacing issues in YAML netlist by adjusting placements.
    
    Args:
        yaml_str: YAML string
        min_spacing: Minimum spacing between components
        
    Returns:
        Fixed YAML string
    """
    try:
        netlist = yaml.safe_load(yaml_str)
        
        if 'placements' not in netlist:
            return yaml_str
        
        placements = netlist['placements']
        positions = []
        
        # Extract current positions
        for inst_name, placement in placements.items():
            if isinstance(placement, dict):
                x = placement.get('x', 0)
                y = placement.get('y', 0)
                positions.append((inst_name, x, y))
        
        # Check and fix spacing
        fixed = False
        for i, (name1, x1, y1) in enumerate(positions):
            for name2, x2, y2 in positions[i+1:]:
                distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                if 0 < distance < min_spacing:
                    # Increase spacing by moving components apart
                    scale = min_spacing / distance
                    new_x2 = x1 + (x2 - x1) * scale
                    new_y2 = y1 + (y2 - y1) * scale
                    
                    # Update placement
                    if name2 in placements:
                        placements[name2]['x'] = new_x2
                        placements[name2]['y'] = new_y2
                        fixed = True
                        logger.info(f"Fixed spacing: {name1} and {name2} (distance: {distance:.1f} -> {min_spacing:.1f})")
        
        if fixed:
            return yaml.dump(netlist, default_flow_style=False, sort_keys=False)
        
        return yaml_str
    except Exception as e:
        logger.error(f"Error fixing YAML spacing: {e}")
        return yaml_str


def component_to_yaml_and_back(component: gf.Component, fix_spacing: bool = True) -> Tuple[Optional[gf.Component], Optional[str]]:
    """
    Extract netlist from component, convert to YAML, optionally fix, and rebuild.
    
    This is useful for:
    1. Fixing routing collisions by adjusting spacing in YAML
    2. Validating netlist structure
    3. Rebuilding component with proper routing
    
    Args:
        component: GDSFactory component
        fix_spacing: Whether to fix spacing issues
        
    Returns:
        (rebuilt_component, error_message)
    """
    try:
        # Extract netlist
        netlist = extract_netlist_from_component(component)
        if not netlist:
            return None, "Failed to extract netlist"
        
        # Convert to YAML
        yaml_str = netlist_to_yaml(netlist)
        if not yaml_str:
            return None, "Failed to convert netlist to YAML"
        
        # Fix spacing if requested
        if fix_spacing:
            yaml_str = fix_yaml_spacing(yaml_str)
        
        # Rebuild component from YAML
        rebuilt, error = yaml_to_component(yaml_str)
        return rebuilt, error
        
    except Exception as e:
        error_msg = f"Error in component_to_yaml_and_back: {e}"
        logger.error(error_msg)
        return None, error_msg


