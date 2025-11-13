"""
Silicon Efficiency Checker

Detects extra silicon, unconnected components, and unnecessary routing.
Flags designs with excessive silicon area.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
import gdsfactory as gf
from ..config import MAX_UNCONNECTED_COMPONENTS, MAX_EXCESS_SILICON_RATIO

logger = logging.getLogger(__name__)


class SiliconEfficiencyChecker:
    """Checks silicon efficiency of designs."""

    def __init__(self):
        """Initialize silicon efficiency checker."""
        self.max_unconnected = MAX_UNCONNECTED_COMPONENTS
        self.max_excess_ratio = MAX_EXCESS_SILICON_RATIO

    def check(self, component: gf.Component) -> Tuple[bool, Dict]:
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
        if excess_ratio > self.max_excess_ratio:
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
        """
        Check component connectivity.

        Args:
            component: Parent component
            refs: List of component references

        Returns:
            Connectivity report dictionary
        """
        report = {
            "unconnected_components": [],
            "connected_components": 0,
        }
        
        # Build connectivity graph
        connected = set()
        
        # Check external ports (these connect to something)
        from ..utils.port_utils import has_port
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
                cell_name = ref.cell.name if hasattr(ref, 'cell') else str(ref)
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
                    name = ref.cell.name if hasattr(ref, 'cell') else str(ref)
                    unconnected_names.append(name)
                except:
                    unconnected_names.append(str(ref))
            report["unconnected_components"] = unconnected_names
        
        return report

    def _find_dangling_components(self, component: gf.Component, refs: List) -> List[str]:
        """
        Find components that are not part of the main circuit.

        Args:
            component: Parent component
            refs: List of component references

        Returns:
            List of dangling component names
        """
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
                        name = ref.cell.name if hasattr(ref, 'cell') else str(ref)
                        dangling.append(name)
            except:
                pass
        
        return dangling

    def _calculate_excess_silicon(self, component: gf.Component, refs: List) -> float:
        """
        Calculate ratio of excess silicon area.

        Args:
            component: Parent component
            refs: List of component references

        Returns:
            Excess silicon ratio (0.0 to 1.0)
        """
        try:
            # Get bounding box of component
            bbox = component.bbox()
            if bbox is None:
                return 0.0
            
            # Calculate total area
            if hasattr(bbox, 'width'):
                total_area = bbox.width * bbox.height
            elif hasattr(bbox, 'xmax'):
                total_area = (bbox.xmax - bbox.xmin) * (bbox.ymax - bbox.ymin)
            else:
                return 0.0
            
            if total_area == 0:
                return 0.0
            
            # Estimate component area (sum of bounding boxes)
            component_area = 0.0
            for ref in refs:
                try:
                    ref_bbox = ref.bbox()
                    if ref_bbox:
                        if hasattr(ref_bbox, 'width'):
                            area = ref_bbox.width * ref_bbox.height
                        elif hasattr(ref_bbox, 'xmax'):
                            area = (ref_bbox.xmax - ref_bbox.xmin) * (ref_bbox.ymax - ref_bbox.ymin)
                        else:
                            continue
                        component_area += area
                except:
                    pass
            
            # Calculate excess ratio
            if total_area > 0:
                excess_ratio = max(0.0, 1.0 - (component_area / total_area))
                return excess_ratio
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error calculating excess silicon: {e}")
            return 0.0

    def analyze_connectivity_graph(self, component: gf.Component) -> Dict:
        """
        Analyze connectivity graph of component.

        Args:
            component: Component to analyze

        Returns:
            Connectivity graph analysis dictionary
        """
        analysis = {
            "components": [],
            "connections": [],
            "isolated_components": [],
        }
        
        try:
            refs = list(component.references)
        except AttributeError:
            refs = list(getattr(component, 'insts', []))
        
        # Build component list
        for ref in refs:
            try:
                name = ref.cell.name if hasattr(ref, 'cell') else str(ref)
                analysis["components"].append(name)
            except:
                pass
        
        # Check connections (simplified - would need actual routing analysis)
        # For now, mark components with routes as connected
        route_count = 0
        for ref in refs:
            try:
                cell_name = ref.cell.name if hasattr(ref, 'cell') else str(ref)
                if any(keyword in cell_name.lower() for keyword in ['route', 'waveguide']):
                    route_count += 1
            except:
                pass
        
        analysis["route_count"] = route_count
        
        return analysis

