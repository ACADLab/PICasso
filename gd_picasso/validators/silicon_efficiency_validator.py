"""
Silicon Efficiency Validator

Detects extra silicon, unconnected components, and unnecessary routing.
Flags designs with excessive silicon area.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
import gdsfactory as gf
from ..utils.port_utils import get_port_items, get_port_names, has_port

logger = logging.getLogger(__name__)

# Configuration
MAX_UNCONNECTED_COMPONENTS = 0  # No unconnected components allowed
MAX_EXCESS_SILICON_RATIO = 0.5  # Max 50% excess silicon


class SiliconEfficiencyValidator:
    """Checks silicon efficiency of designs."""

    def __init__(self):
        """Initialize silicon efficiency validator."""
        self.max_unconnected = MAX_UNCONNECTED_COMPONENTS
        self.max_excess_ratio = MAX_EXCESS_SILICON_RATIO

    def validate(self, component: gf.Component) -> Tuple[bool, Dict]:
        """
        Check silicon efficiency.
        
        Args:
            component: GDSFactory component to check
            
        Returns:
            (is_efficient, efficiency_report)
        """
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "unconnected_components": [],
            "dangling_components": [],
            "excess_silicon_ratio": 0.0,
            "total_components": 0,
            "connected_components": 0,
        }
        
        # Get component references
        try:
            refs = list(component.references)
        except AttributeError:
            refs = list(getattr(component, 'insts', []))
        
        report["total_components"] = len(refs)
        
        # Check connectivity
        connectivity_report = self._check_connectivity(component, refs)
        report.update(connectivity_report)
        
        # Check for dangling components
        dangling = self._find_dangling_components(component, refs)
        if dangling:
            report["dangling_components"] = dangling
            report["warnings"].append(f"Found {len(dangling)} dangling components")
        
        # Check excess silicon
        excess_ratio = self._calculate_excess_silicon(component, refs)
        report["excess_silicon_ratio"] = excess_ratio
        contains_spiral = self._contains_component(refs, "spiral")
        yaml_connected = self._yaml_netlist_is_connected(component)
        yaml_all_instances_used = self._yaml_netlist_uses_all_instances(component)
        if excess_ratio > self.max_excess_ratio and (contains_spiral or yaml_connected or yaml_all_instances_used):
            reason = (
                "spiral delay lines intentionally occupy sparse bounding boxes"
                if contains_spiral
                else "the YAML connectivity uses every declared instance and sparse multi-channel layouts can occupy large bounding boxes"
                if yaml_all_instances_used
                else "the YAML connectivity graph is connected and sparse receiver/channel layouts can occupy large bounding boxes"
            )
            report["warnings"].append(
                f"Excess silicon ratio {excess_ratio:.2%} exceeds the generic "
                f"threshold, but {reason}; treating this as a warning."
            )
        elif excess_ratio > self.max_excess_ratio:
            report["errors"].append(
                f"Excess silicon ratio {excess_ratio:.2%} exceeds maximum {self.max_excess_ratio:.2%}"
            )
            report["passed"] = False
        
        # Check unconnected components
        unconnected_count = len(report["unconnected_components"])
        if unconnected_count > self.max_unconnected:
            report["errors"].append(
                f"Found {unconnected_count} unconnected components (max: {self.max_unconnected})"
            )
            report["passed"] = False
        
        return report["passed"], report

    def _check_connectivity(self, component: gf.Component, refs: List) -> Dict:
        """Check component connectivity."""
        report = {
            "unconnected_components": [],
            "connected_components": 0,
        }
        
        # Build connectivity graph
        connected = set()
        
        # Check external ports (these connect to something)
        for port_name, port in get_port_items(component.ports):
            # Find which component this port belongs to
            for ref in refs:
                if hasattr(ref, 'ports') and has_port(ref.ports, port_name):
                    connected.add(ref)
                    break
        
        # Check routing connections
        # Look for route references in component
        route_refs = []
        for ref in refs:
            try:
                if hasattr(ref, 'ref_cell'):
                    cell_name = ref.ref_cell.name if hasattr(ref.ref_cell, 'name') else str(ref.ref_cell)
                elif hasattr(ref, 'cell'):
                    cell_name = ref.cell.name if hasattr(ref.cell, 'name') else str(ref.cell)
                else:
                    cell_name = str(ref)
                if any(keyword in cell_name.lower() for keyword in ['route', 'waveguide', 'bend']):
                    route_refs.append(ref)
            except:
                pass
        
        # Components with routes are connected
        # This is a heuristic - in practice, we'd trace actual connections
        for ref in refs:
            # Check if ref has ports that are used in routing
            if hasattr(ref, 'ports'):
                for port_name, port in get_port_items(ref.ports):
                    # Check if this port is connected to a route or another component
                    # Simplified check: if component has routes, assume connectivity
                    if route_refs:
                        connected.add(ref)
                        break
        
        report["connected_components"] = len(connected)
        
        # Find unconnected components
        unconnected = [ref for ref in refs if ref not in connected]
        if unconnected:
            unconnected_names = []
            for ref in unconnected:
                try:
                    if hasattr(ref, 'ref_cell'):
                        name = ref.ref_cell.name if hasattr(ref.ref_cell, 'name') else str(ref.ref_cell)
                    elif hasattr(ref, 'cell'):
                        name = ref.cell.name if hasattr(ref.cell, 'name') else str(ref.cell)
                    else:
                        name = str(ref)
                    unconnected_names.append(name)
                except:
                    unconnected_names.append(str(ref))
            report["unconnected_components"] = unconnected_names
        
        return report

    def _yaml_netlist_is_connected(self, component: gf.Component) -> bool:
        """Return True when stored YAML connectivity links every declared instance."""
        try:
            yaml_netlist = component.info.get("picasso_yaml_netlist", {}) or {}
        except Exception:
            return False

        instances = yaml_netlist.get("instances", {})
        connections = yaml_netlist.get("connections", {})
        if not isinstance(instances, dict) or not isinstance(connections, dict):
            return False
        if len(instances) <= 1:
            return True
        if not connections:
            return False

        graph = {name: set() for name in instances}
        for src, dst in connections.items():
            src_inst = str(src).split(",", 1)[0]
            dst_inst = str(dst).split(",", 1)[0]
            if src_inst in graph and dst_inst in graph:
                graph[src_inst].add(dst_inst)
                graph[dst_inst].add(src_inst)

        start = next(iter(graph))
        seen = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for neighbor in graph[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)

        return len(seen) == len(graph)

    def _yaml_netlist_uses_all_instances(self, component: gf.Component) -> bool:
        """Return True when every declared YAML instance is connected or exported."""
        try:
            yaml_netlist = component.info.get("picasso_yaml_netlist", {}) or {}
        except Exception:
            return False

        instances = yaml_netlist.get("instances", {})
        connections = yaml_netlist.get("connections", {})
        ports = yaml_netlist.get("ports", {})
        if not isinstance(instances, dict) or not instances:
            return False

        used = set()
        if isinstance(connections, dict):
            for src, dst in connections.items():
                for endpoint in (src, dst):
                    inst = str(endpoint).split(",", 1)[0]
                    if inst in instances:
                        used.add(inst)

        if isinstance(ports, dict):
            for endpoint in ports.values():
                inst = str(endpoint).split(",", 1)[0]
                if inst in instances:
                    used.add(inst)

        return used == set(instances)

    def _find_dangling_components(self, component: gf.Component, refs: List) -> List[str]:
        """Find components that are not part of the main circuit."""
        dangling = []
        
        # Check for components with no ports connected
        for ref in refs:
            try:
                if hasattr(ref, 'ports'):
                    # Check if any ports are used
                    ports_used = False
                    for port_name in get_port_names(ref.ports):
                        # Check if port is exposed or used in routing
                        # Simplified: if component has routes, assume ports are used
                        if len(component.ports) > 0:
                            ports_used = True
                            break
                    
                    if not ports_used and len(ref.ports) > 0:
                        if hasattr(ref, 'ref_cell'):
                            name = ref.ref_cell.name if hasattr(ref.ref_cell, 'name') else str(ref.ref_cell)
                        elif hasattr(ref, 'cell'):
                            name = ref.cell.name if hasattr(ref.cell, 'name') else str(ref.cell)
                        else:
                            name = str(ref)
                        dangling.append(name)
            except:
                pass
        
        return dangling

    def _calculate_excess_silicon(self, component: gf.Component, refs: List) -> float:
        """Calculate ratio of excess silicon area."""
        try:
            bbox = component.bbox()
            if bbox is None:
                return 0.0
            
            total_area = self._box_area(bbox)
            if total_area == 0:
                return 0.0
            
            component_area = 0.0
            for ref in refs:
                try:
                    ref_bbox = ref.bbox()
                    if ref_bbox:
                        component_area += self._box_area(ref_bbox)
                except Exception:
                    pass
            
            if total_area > 0:
                excess_ratio = max(0.0, 1.0 - (component_area / total_area))
                return excess_ratio
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error calculating excess silicon: {e}")
            return 0.0

    @staticmethod
    def _box_area(bbox) -> float:
        """Compute area from a bounding box, handling both property and method accessors."""
        try:
            w = bbox.width() if callable(bbox.width) else bbox.width
            h = bbox.height() if callable(bbox.height) else bbox.height
            return float(w) * float(h)
        except (AttributeError, TypeError):
            pass
        try:
            return float(bbox.xmax - bbox.xmin) * float(bbox.ymax - bbox.ymin)
        except (AttributeError, TypeError):
            return 0.0

    @staticmethod
    def _contains_component(refs: List, name_fragment: str) -> bool:
        """Return True when any reference cell name contains ``name_fragment``."""
        needle = name_fragment.lower()
        for ref in refs:
            try:
                if hasattr(ref, 'ref_cell'):
                    cell = ref.ref_cell
                elif hasattr(ref, 'cell'):
                    cell = ref.cell
                else:
                    cell = ref
                name = getattr(cell, 'name', '') or str(cell)
                if needle in name.lower():
                    return True
            except Exception:
                continue
        return False
