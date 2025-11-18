"""
YAML-Based Routing and Placement Fixer

Iteratively fixes routing collisions and placement issues using YAML netlist manipulation.
Uses GDSFactory's native gf.read.from_yaml() for automatic routing.
Automatic iterative approach with spacing and rotation fixes.
"""

import yaml
import logging
import time
from itertools import product
from typing import Dict, Optional, Tuple
import gdsfactory as gf
from .yaml_netlist_helper import (
    extract_netlist_from_component,
    netlist_to_yaml,
    yaml_to_component
)

logger = logging.getLogger(__name__)


def fix_routing_and_placement_iterative(
    component: gf.Component,
    max_iterations: int = 3,
    initial_spacing_multiplier: float = 1.5,
    spacing_increment: float = 0.5,
    enable_rotation: bool = True,
    rotation_timeout: int = 120
) -> Tuple[Optional[gf.Component], Dict]:
    """
    Iteratively fix routing collisions and placement issues using YAML netlist.
    
    Strategy:
    1. Extract netlist from component
    2. Convert to YAML
    3. Fix spacing/placement in YAML
    4. Rebuild using gf.read.from_yaml() (automatic routing)
    5. Test if routing collision resolved
    6. If not, try brute-force rotation (4 orientations per component)
    7. If still not, increase spacing and retry (up to max_iterations)
    
    Args:
        component: GDSFactory component with routing/placement issues
        max_iterations: Maximum number of fix iterations (default: 3)
        initial_spacing_multiplier: Initial spacing multiplier (default: 1.5)
        spacing_increment: Spacing increment per iteration (default: 0.5)
        enable_rotation: Enable brute-force rotation algorithm (default: True)
        rotation_timeout: Timeout for rotation algorithm in seconds (default: 120)
        
    Returns:
        (fixed_component, fix_info_dict)
        fix_info_dict contains:
            - success: bool
            - iterations: int
            - final_spacing_multiplier: float
            - method_used: str ("spacing" or "rotation")
            - errors: list of error messages
    """
    fix_info = {
        "success": False,
        "iterations": 0,
        "final_spacing_multiplier": initial_spacing_multiplier,
        "method_used": "none",
        "errors": []
    }
    
    current_component = component
    spacing_multiplier = initial_spacing_multiplier
    
    # First, try spacing-based fixes
    for iteration in range(max_iterations):
        fix_info["iterations"] = iteration + 1
        fix_info["final_spacing_multiplier"] = spacing_multiplier
        
        logger.info(f"🔄 YAML routing/placement fix iteration {iteration + 1}/{max_iterations} (spacing: {spacing_multiplier}x)")
        
        try:
            # Extract netlist
            netlist = extract_netlist_from_component(current_component)
            if not netlist or not netlist.get('instances'):
                error_msg = "Failed to extract netlist or no instances found"
                logger.warning(f"⚠️  {error_msg}")
                fix_info["errors"].append(error_msg)
                break
            
            # Convert to YAML
            yaml_str = netlist_to_yaml(netlist)
            if not yaml_str:
                error_msg = "Failed to convert netlist to YAML"
                logger.warning(f"⚠️  {error_msg}")
                fix_info["errors"].append(error_msg)
                break
            
            # Fix spacing in YAML using multiplier
            fixed_yaml = fix_yaml_spacing_with_multiplier(yaml_str, spacing_multiplier)
            
            # Rebuild component from fixed YAML
            fixed_component, rebuild_error = yaml_to_component(fixed_yaml)
            
            if fixed_component is None:
                error_msg = f"Failed to rebuild from YAML: {rebuild_error}"
                logger.warning(f"⚠️  {error_msg}")
                fix_info["errors"].append(error_msg)
                # Increase spacing for next iteration
                spacing_multiplier += spacing_increment
                continue
            
            # Test if routing collision is resolved by trying to get netlist again
            # If get_netlist() succeeds, routing is likely fixed
            try:
                test_netlist = fixed_component.get_netlist()
                logger.info(f"✅ Iteration {iteration + 1} successful - routing collision resolved with spacing fix!")
                fix_info["success"] = True
                fix_info["method_used"] = "spacing"
                return fixed_component, fix_info
            except Exception as test_error:
                # Still has routing issues, try next iteration with more spacing
                error_msg = f"Iteration {iteration + 1} still has routing issues: {test_error}"
                logger.info(f"⚠️  {error_msg}")
                fix_info["errors"].append(error_msg)
                current_component = fixed_component  # Use this as base for next iteration
                spacing_multiplier += spacing_increment
                continue
                
        except Exception as e:
            error_msg = f"Iteration {iteration + 1} failed: {e}"
            logger.warning(f"⚠️  {error_msg}")
            fix_info["errors"].append(error_msg)
            spacing_multiplier += spacing_increment
            continue
    
    # If spacing fixes failed, try brute-force rotation
    if enable_rotation and not fix_info["success"]:
        logger.info(f"🔄 Spacing fixes failed. Trying brute-force rotation algorithm (timeout: {rotation_timeout}s)...")
        rotated_component, rotation_info = try_rotation_fixes(
            component=component,
            timeout=rotation_timeout
        )
        
        if rotated_component is not None and rotation_info.get("success"):
            logger.info(f"✅ Rotation algorithm successful! Found valid routing with orientation {rotation_info.get('orientation')}°")
            fix_info["success"] = True
            fix_info["method_used"] = "rotation"
            fix_info["rotation_info"] = rotation_info
            return rotated_component, fix_info
        else:
            logger.warning(f"⚠️  Rotation algorithm failed: {rotation_info.get('error', 'Unknown error')}")
            fix_info["errors"].append(f"Rotation failed: {rotation_info.get('error', 'Unknown')}")
    
    # All methods failed
    logger.warning(f"❌ All routing fix methods failed (spacing iterations + rotation)")
    return None, fix_info


def fix_yaml_spacing_with_multiplier(yaml_str: str, spacing_multiplier: float = 1.5) -> str:
    """
    Fix spacing in YAML netlist by applying a spacing multiplier to all placements.
    
    Args:
        yaml_str: YAML netlist string
        spacing_multiplier: Multiplier to apply to all coordinates (1.5 = 50% increase)
        
    Returns:
        Fixed YAML string with increased spacing
    """
    try:
        netlist = yaml.safe_load(yaml_str)
        
        if 'placements' not in netlist:
            return yaml_str
        
        placements = netlist['placements']
        
        # Apply spacing multiplier to all placement coordinates
        for inst_name, placement in placements.items():
            if isinstance(placement, dict):
                # Multiply x and y coordinates
                if 'x' in placement:
                    placement['x'] = placement['x'] * spacing_multiplier
                if 'y' in placement:
                    placement['y'] = placement['y'] * spacing_multiplier
        
        # Convert back to YAML (use safe_dump to avoid Python-specific tags)
        try:
            return yaml.dump(netlist, default_flow_style=False, sort_keys=False, allow_unicode=False)
        except yaml.YAMLError:
            # If safe_dump fails, try with FullLoader
            return yaml.dump(netlist, default_flow_style=False, sort_keys=False)
        
    except Exception as e:
        logger.error(f"Error fixing YAML spacing: {e}")
        return yaml_str


def try_rotation_fixes(
    component: gf.Component,
    timeout: int = 120
) -> Tuple[Optional[gf.Component], Dict]:
    """
    Try brute-force rotation algorithm.
    
    Rotates each component in 4 orientations (0°, 90°, 180°, 270°) and tests if routing succeeds.
    Time complexity: O(4^N) where N is number of components.
    
    Args:
        component: GDSFactory component with routing issues
        timeout: Maximum time to spend on rotation (seconds, default: 120)
        
    Returns:
        (fixed_component, rotation_info_dict)
        rotation_info_dict contains:
            - success: bool
            - orientation: dict of {instance_name: rotation_angle}
            - error: str if failed
    """
    rotation_info = {
        "success": False,
        "orientation": {},
        "error": None
    }
    
    start_time = time.time()
    
    try:
        # Extract netlist
        netlist = extract_netlist_from_component(component)
        if not netlist or not netlist.get('instances'):
            rotation_info["error"] = "Failed to extract netlist"
            return None, rotation_info
        
        instances = list(netlist.get('instances', {}).keys())
        num_instances = len(instances)
        
        if num_instances == 0:
            rotation_info["error"] = "No instances to rotate"
            return None, rotation_info
        
        # Limit to reasonable number of components (4^10 = 1M combinations, 4^8 = 65K)
        if num_instances > 8:
            logger.warning(f"⚠️  Too many components ({num_instances}) for brute-force rotation. Limiting to first 8.")
            instances = instances[:8]
            num_instances = 8
        
        orientations = [0, 90, 180, 270]  # 4 orientations (north, east, south, west)
        total_combinations = 4 ** num_instances
        
        logger.info(f"🔄 Trying {total_combinations} rotation combinations for {num_instances} components...")
        
        # Try all combinations
        for combo_idx, rotation_combo in enumerate(product(orientations, repeat=num_instances)):
            # Check timeout
            if time.time() - start_time > timeout:
                rotation_info["error"] = f"Timeout after {timeout}s (tried {combo_idx}/{total_combinations} combinations)"
                logger.warning(f"⚠️  {rotation_info['error']}")
                return None, rotation_info
            
            # Create rotation dict: {instance_name: rotation_angle}
            rotation_dict = {inst: rot for inst, rot in zip(instances, rotation_combo)}
            
            # Skip if all rotations are 0 (already tried)
            if all(r == 0 for r in rotation_combo) and combo_idx > 0:
                continue
            
            try:
                # Apply rotations to netlist
                modified_netlist = netlist.copy()
                placements = modified_netlist.get('placements', {})
                
                for inst_name, rotation_angle in rotation_dict.items():
                    if inst_name in placements:
                        placements[inst_name] = placements[inst_name].copy()
                        placements[inst_name]['rotation'] = rotation_angle
                
                # Convert to YAML and rebuild
                yaml_str = netlist_to_yaml(modified_netlist)
                if not yaml_str:
                    continue
                
                fixed_component, rebuild_error = yaml_to_component(yaml_str)
                
                if fixed_component is None:
                    continue
                
                # Test if routing is successful
                try:
                    test_netlist = fixed_component.get_netlist()
                    # Success! Routing works with this rotation
                    logger.info(f"✅ Found valid rotation combination: {rotation_dict}")
                    rotation_info["success"] = True
                    rotation_info["orientation"] = rotation_dict
                    return fixed_component, rotation_info
                except Exception:
                    # This rotation didn't work, try next
                    continue
                    
            except Exception as e:
                # Error applying this rotation, try next
                continue
        
        # All combinations failed
        rotation_info["error"] = f"All {total_combinations} rotation combinations failed"
        logger.warning(f"⚠️  {rotation_info['error']}")
        return None, rotation_info
        
    except Exception as e:
        rotation_info["error"] = f"Rotation algorithm error: {e}"
        logger.error(f"❌ {rotation_info['error']}")
        return None, rotation_info


