"""
Pydoc-based Component Loader

Uses pydoc and inspect to dynamically extract comprehensive component specifications
from gdsfactory, including signatures, parameters, ports, and orientations.
"""

import logging
import inspect
import json
import subprocess
import sys
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import gdsfactory as gf

from ..utils.port_utils import get_port_names, get_port_items

logger = logging.getLogger(__name__)

# Common components to extract specs for
COMMON_COMPONENTS = [
    # MMIs
    'mmi1x2',
    'mmi2x2',
    # MZIs
    'mzi',
    'mzm',
    # Waveguides
    'straight',
    'bend_euler',
    'bend_s',
    'bend_circular',
    # Phase shifters
    'straight_heater_metal',
    'straight_heater_metal_undercut',
    # Couplers
    'coupler',
    'coupler_ring',
    # Rings
    'ring_single',
    'ring_double',
    'ring_double_bend_coupler',
    # Other common components
    'taper',
    'crossing',
    'grating_coupler_rectangular',
    'grating_coupler_elliptical',
]

# Routing functions
ROUTING_FUNCTIONS = [
    'route_single',
    'route_bundle',
    'route_quad',
]


class PydocComponentLoader:
    """Loads component specifications using pydoc and inspect."""

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize pydoc component loader.

        Args:
            cache_file: Optional path to cache file
        """
        self.cache_file = cache_file or Path(__file__).parent / "pydoc_component_specs_cache.json"
        self.specs_cache = self._load_cache()
        self.gdsfactory_version = self._get_gdsfactory_version()

    def _get_gdsfactory_version(self) -> str:
        """Get gdsfactory version."""
        try:
            if hasattr(gf, '__version__'):
                return gf.__version__
            return "unknown"
        except:
            return "unknown"

    def _load_cache(self) -> Dict:
        """Load cached specs from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    # Check if version matches
                    if cache.get('gdsfactory_version') == self._get_gdsfactory_version():
                        return cache
                    else:
                        logger.info(f"Cache version mismatch, will regenerate")
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return {
            'gdsfactory_version': self._get_gdsfactory_version(),
            'components': {},
            'routing_functions': {}
        }

    def _save_cache(self):
        """Save specs to cache file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.specs_cache, f, indent=2)
            logger.debug(f"Saved component specs cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def _get_component_function(self, component_name: str) -> Optional[Any]:
        """Get component function from gdsfactory."""
        try:
            # Try direct access first
            if hasattr(gf.components, component_name):
                return getattr(gf.components, component_name)
            
            # Try submodules (e.g., mmis.mmi1x2)
            for attr_name in dir(gf.components):
                attr = getattr(gf.components, attr_name)
                if hasattr(attr, component_name):
                    return getattr(attr, component_name)
            
            return None
        except Exception as e:
            logger.debug(f"Could not get component function for {component_name}: {e}")
            return None

    def _get_routing_function(self, func_name: str) -> Optional[Any]:
        """Get routing function from gdsfactory.routing."""
        try:
            if hasattr(gf.routing, func_name):
                return getattr(gf.routing, func_name)
            return None
        except Exception as e:
            logger.debug(f"Could not get routing function for {func_name}: {e}")
            return None

    def _extract_signature(self, func: Any) -> Dict:
        """Extract function signature using inspect."""
        try:
            sig = inspect.signature(func)
            params = {}
            for param_name, param in sig.parameters.items():
                # Convert default to string if it's not JSON serializable
                default_val = param.default
                if default_val != inspect.Parameter.empty:
                    # Try to serialize, if fails convert to string
                    try:
                        json.dumps(default_val)
                    except (TypeError, ValueError):
                        default_val = str(default_val)
                else:
                    default_val = None
                
                params[param_name] = {
                    'name': param_name,
                    'default': default_val,
                    'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
                    'kind': str(param.kind)
                }
            return {
                'parameters': params,
                'return_annotation': str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else None
            }
        except Exception as e:
            logger.debug(f"Could not extract signature: {e}")
            return {}

    def _extract_pydoc_help(self, obj: Any, obj_name: str) -> str:
        """Extract help text using pydoc."""
        try:
            # Use pydoc to get help text
            result = subprocess.run(
                [sys.executable, '-m', 'pydoc', obj_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout
            return ""
        except Exception as e:
            logger.debug(f"Could not get pydoc help for {obj_name}: {e}")
            return ""

    def _extract_port_info(self, component_name: str, comp_func: Any) -> Dict:
        """Extract port information from component instance."""
        try:
            # Instantiate component to get ports
            comp = comp_func()
            
            port_info = {
                'ports': [],
                'port_count': 0
            }
            
            # Get port names
            port_names = get_port_names(comp.ports)
            port_info['port_count'] = len(port_names)
            
            # Get detailed port information
            for port_name, port in get_port_items(comp.ports):
                port_details = {
                    'name': port_name,
                    'orientation': getattr(port, 'orientation', None),
                    'width': getattr(port, 'width', None),
                    'port_type': getattr(port, 'port_type', 'optical'),
                }
                port_info['ports'].append(port_details)
            
            return port_info
        except Exception as e:
            logger.warning(f"Could not extract port info for {component_name}: {e}")
            return {'ports': [], 'port_count': 0}

    def _extract_component_spec(self, component_name: str) -> Optional[Dict]:
        """Extract comprehensive spec for a component."""
        # Check cache first
        if component_name in self.specs_cache.get('components', {}):
            cached = self.specs_cache['components'][component_name]
            if cached.get('gdsfactory_version') == self.gdsfactory_version:
                return cached
        
        comp_func = self._get_component_function(component_name)
        if comp_func is None:
            logger.warning(f"Component {component_name} not found")
            return None
        
        # Extract signature
        signature = self._extract_signature(comp_func)
        
        # Extract port info
        port_info = self._extract_port_info(component_name, comp_func)
        
        # Extract docstring
        docstring = inspect.getdoc(comp_func) or ""
        
        # Try to get pydoc help (may be slow, so optional)
        pydoc_help = ""
        try:
            # Try to get full path for pydoc
            if hasattr(comp_func, '__module__') and hasattr(comp_func, '__name__'):
                full_name = f"{comp_func.__module__}.{comp_func.__name__}"
                pydoc_help = self._extract_pydoc_help(comp_func, full_name)
        except:
            pass
        
        spec = {
            'component_name': component_name,
            'gdsfactory_version': self.gdsfactory_version,
            'signature': signature,
            'port_info': port_info,
            'docstring': docstring[:500] if docstring else "",  # Limit docstring length
            'pydoc_help': pydoc_help[:1000] if pydoc_help else "",  # Limit help text
        }
        
        # Cache it
        if 'components' not in self.specs_cache:
            self.specs_cache['components'] = {}
        self.specs_cache['components'][component_name] = spec
        self._save_cache()
        
        return spec

    def _extract_routing_spec(self, func_name: str) -> Optional[Dict]:
        """Extract spec for a routing function."""
        # Check cache first
        if func_name in self.specs_cache.get('routing_functions', {}):
            cached = self.specs_cache['routing_functions'][func_name]
            if cached.get('gdsfactory_version') == self.gdsfactory_version:
                return cached
        
        func = self._get_routing_function(func_name)
        if func is None:
            logger.warning(f"Routing function {func_name} not found")
            return None
        
        # Extract signature
        signature = self._extract_signature(func)
        
        # Extract docstring
        docstring = inspect.getdoc(func) or ""
        
        spec = {
            'function_name': func_name,
            'gdsfactory_version': self.gdsfactory_version,
            'signature': signature,
            'docstring': docstring[:500] if docstring else "",
        }
        
        # Cache it
        if 'routing_functions' not in self.specs_cache:
            self.specs_cache['routing_functions'] = {}
        self.specs_cache['routing_functions'][func_name] = spec
        self._save_cache()
        
        return spec

    def load_component_specs(self, component_names: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Load specs for specified components or all common components.

        Args:
            component_names: List of component names, or None for all common components

        Returns:
            Dictionary mapping component_name -> spec
        """
        if component_names is None:
            component_names = COMMON_COMPONENTS
        
        specs = {}
        for comp_name in component_names:
            try:
                spec = self._extract_component_spec(comp_name)
                if spec:
                    specs[comp_name] = spec
            except Exception as e:
                logger.warning(f"Error loading spec for {comp_name}: {e}")
        
        return specs

    def load_routing_specs(self, func_names: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Load specs for routing functions.

        Args:
            func_names: List of function names, or None for all routing functions

        Returns:
            Dictionary mapping function_name -> spec
        """
        if func_names is None:
            func_names = ROUTING_FUNCTIONS
        
        specs = {}
        for func_name in func_names:
            try:
                spec = self._extract_routing_spec(func_name)
                if spec:
                    specs[func_name] = spec
            except Exception as e:
                logger.warning(f"Error loading spec for {func_name}: {e}")
        
        return specs

    def generate_formatted_specs(
        self,
        component_names: Optional[List[str]] = None,
        include_routing: bool = True
    ) -> str:
        """
        Generate formatted component specs string for LLM injection.

        Args:
            component_names: List of component names, or None for all common components
            include_routing: Whether to include routing function specs

        Returns:
            Formatted string for LLM prompt
        """
        lines = []
        lines.append("=" * 80)
        lines.append("GDSFACTORY COMPONENTS REFERENCE (Auto-Generated)")
        lines.append("=" * 80)
        lines.append("")
        lines.append("⚠️ CRITICAL: Use ONLY these components. Verify component names exist before using!")
        lines.append("")
        
        # Load component specs
        comp_specs = self.load_component_specs(component_names)
        
        for comp_name, spec in comp_specs.items():
            lines.append(f"Component: {comp_name}")
            lines.append("-" * 80)
            
            # Signature
            if spec.get('signature', {}).get('parameters'):
                params = spec['signature']['parameters']
                param_strs = []
                for param_name, param_info in params.items():
                    default = param_info.get('default')
                    if default is not None:
                        param_strs.append(f"{param_name}={default}")
                    else:
                        param_strs.append(param_name)
                lines.append(f"  Signature: {comp_name}({', '.join(param_strs)})")
            
            # Port information
            port_info = spec.get('port_info', {})
            if port_info.get('ports'):
                lines.append(f"  Ports ({port_info['port_count']} total):")
                for port in port_info['ports']:
                    port_name = port['name']
                    orientation = port.get('orientation')
                    width = port.get('width')
                    port_type = port.get('port_type', 'optical')
                    
                    port_desc = f"    - {port_name}"
                    if orientation is not None:
                        port_desc += f" (orientation: {orientation}°)"
                    if width is not None:
                        port_desc += f" (width: {width}nm)"
                    if port_type:
                        port_desc += f" (type: {port_type})"
                    lines.append(port_desc)
            
            # Usage example
            lines.append(f"  Usage Example:")
            lines.append(f"    comp = r.add_ref(gf.components.{comp_name}())")
            if port_info.get('ports'):
                port_names = [p['name'] for p in port_info['ports']]
                if len(port_names) >= 2:
                    lines.append(f"    # Access ports: comp.ports['{port_names[0]}'], comp.ports['{port_names[1]}']")
            
            # Common mistakes
            if comp_name == 'mmi1x2':
                lines.append(f"  ⚠️ WARNING: mmi2x1 does NOT exist! Use mmi1x2() and mirror it:")
                lines.append(f"    ref = r.add_ref(gf.components.mmi1x2())")
                lines.append(f"    ref.mirror()  # Mirror to create 2x1 combiner")
            
            lines.append("")
        
        # Add routing functions
        if include_routing:
            lines.append("=" * 80)
            lines.append("ROUTING FUNCTIONS REFERENCE")
            lines.append("=" * 80)
            lines.append("")
            
            routing_specs = self.load_routing_specs()
            
            for func_name, spec in routing_specs.items():
                lines.append(f"Function: gf.routing.{func_name}()")
                lines.append("-" * 80)
                
                # Signature
                if spec.get('signature', {}).get('parameters'):
                    params = spec['signature']['parameters']
                    param_list = list(params.keys())
                    lines.append(f"  Parameters: {', '.join(param_list)}")
                    
                    # Explicit restrictions
                    if func_name == 'route_single':
                        lines.append(f"  ❌ DOES NOT ACCEPT: 'separation' parameter")
                        lines.append(f"  ✅ Use for: Single 1-to-1 connections")
                        lines.append(f"  ✅ Required params: component, port1, port2, cross_section")
                        lines.append(f"  ✅ Optional params: radius, waypoints, etc.")
                    elif func_name == 'route_bundle':
                        lines.append(f"  ✅ ACCEPTS: 'separation' parameter (for multiple parallel routes)")
                        lines.append(f"  ✅ Use for: Multiple parallel connections")
                        lines.append(f"  ✅ Required params: component, ports1, ports2, cross_section")
                        lines.append(f"  ✅ Optional params: separation, radius, etc.")
                
                # Usage example
                if func_name == 'route_single':
                    lines.append(f"  Usage Example:")
                    lines.append(f"    gf.routing.route_single(")
                    lines.append(f"        r,  # component")
                    lines.append(f"        port1,  # start port")
                    lines.append(f"        port2,  # end port")
                    lines.append(f"        cross_section='strip',")
                    lines.append(f"        radius=15  # ✅ CORRECT")
                    lines.append(f"        # ❌ DO NOT use: separation=15  # WRONG!")
                    lines.append(f"    )")
                elif func_name == 'route_bundle':
                    lines.append(f"  Usage Example:")
                    lines.append(f"    gf.routing.route_bundle(")
                    lines.append(f"        r,  # component")
                    lines.append(f"        [port1, port2],  # source ports")
                    lines.append(f"        [port3, port4],  # destination ports")
                    lines.append(f"        cross_section='strip',")
                    lines.append(f"        radius=15,")
                    lines.append(f"        separation=15  # ✅ CORRECT for route_bundle")
                    lines.append(f"    )")
                
                lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)

