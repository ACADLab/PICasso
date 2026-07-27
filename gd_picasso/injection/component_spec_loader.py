"""
Component Spec Loader for YAML DSL

Loads component specifications and generates YAML DSL examples for LLM injection.
Includes component specs in YAML format and common error patterns to avoid.
"""

import logging
import inspect
import gdsfactory as gf
from typing import Dict, List, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Try to import port utilities
try:
    from ..utils.port_utils import get_port_names, get_port_items
    from ..utils.gdsfactory_compat import ensure_generic_pdk_active, patch_dbr_ports
except ImportError:
    # Fallback if port_utils not available
    def get_port_names(ports):
        if hasattr(ports, 'keys'):
            return list(ports.keys())
        return []
    
    def get_port_items(ports):
        if hasattr(ports, 'items'):
            return ports.items()
        return []

    def patch_dbr_ports():
        return False

    def ensure_generic_pdk_active():
        return False


class ComponentSpecLoader:
    """Loads and caches component specifications for YAML DSL injection."""

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize component spec loader.

        Args:
            cache_file: Optional path to cache file
        """
        self.cache_file = cache_file or Path(__file__).parent / "component_specs_cache.json"
        ensure_generic_pdk_active()
        patch_dbr_ports()
        self.specs_cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cached component specs."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
        return {}

    def _save_cache(self):
        """Save component specs to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.specs_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def load_component_spec(self, component_type: str, force_reload: bool = False) -> Optional[Dict]:
        """
        Load component specification.

        Args:
            component_type: Component type name
            force_reload: Force reload even if cached

        Returns:
            Component specification dictionary or None
        """
        # Check cache first
        if not force_reload and component_type in self.specs_cache:
            return self.specs_cache[component_type]
        
        try:
            # Try to get component function
            comp_func = getattr(gf.components, component_type, None)
            if comp_func is None:
                logger.warning(f"Component '{component_type}' not found in gf.components")
                return None
            
            # Instantiate component to get specs
            comp = comp_func()
            
            # Extract port information
            ports = {}
            port_names = get_port_names(comp.ports)
            
            try:
                for port_name, port in get_port_items(comp.ports):
                    ports[port_name] = {
                        "name": port_name,
                        "orientation": getattr(port, 'orientation', None),
                        "width": getattr(port, 'width', None),
                    }
            except Exception as e:
                logger.warning(f"Error extracting ports for {component_type}: {e}")
            
            # Get component parameters using inspect
            parameters = {}
            try:
                sig = inspect.signature(comp_func)
                for param_name, param in sig.parameters.items():
                    param_info = {
                        "name": param_name,
                        "default": param.default if param.default != inspect.Parameter.empty else None,
                        "annotation": str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
                        "kind": str(param.kind)
                    }
                    # Convert non-serializable defaults to strings
                    if param_info["default"] is not None and not isinstance(param_info["default"], (str, int, float, bool, type(None))):
                        param_info["default"] = str(param_info["default"])
                    parameters[param_name] = param_info
            except Exception as e:
                logger.warning(f"Error extracting parameters for {component_type}: {e}")
            
            # Also get component settings/parameters from info if available
            settings = {}
            if hasattr(comp_func, 'info'):
                settings = comp_func.info.get('defaults', {})
            
            spec = {
                "component_type": component_type,
                "ports": port_names,
                "port_details": ports,
                "port_count": len(port_names),
                "parameters": parameters,  # Function signature parameters
                "settings": settings,  # Default settings from info
            }
            
            # Cache it
            self.specs_cache[component_type] = spec
            self._save_cache()
            
            return spec
            
        except Exception as e:
            logger.error(f"Error loading component spec for '{component_type}': {e}")
            return None

    def load_multiple_specs(self, component_types: List[str]) -> Dict[str, Dict]:
        """Load specifications for multiple components."""
        specs = {}
        for comp_type in component_types:
            spec = self.load_component_spec(comp_type)
            if spec:
                specs[comp_type] = spec
        return specs

    def generate_yaml_dsl_injection(
        self,
        component_types: Optional[List[str]] = None,
        include_examples: bool = True,
        include_error_patterns: bool = True
    ) -> str:
        """
        Generate YAML DSL injection text for LLM prompts.

        Args:
            component_types: List of component types to include (None = common components)
            include_examples: Whether to include YAML DSL examples
            include_error_patterns: Whether to include common error patterns

        Returns:
            Formatted injection text in YAML DSL format
        """
        lines = []
        lines.append("=" * 70)
        lines.append("COMPONENT SPECIFICATIONS (YAML DSL FORMAT)")
        lines.append("=" * 70)
        lines.append("")
        lines.append("⚠️ CRITICAL: Use ONLY these components. Verify component names exist before using!")
        lines.append("")

        # Default component types if not specified
        if component_types is None:
            component_types = [
                'mmi1x2', 'bend_euler', 'straight', 'straight_heater_metal',
                'coupler', 'ring_single', 'mmi2x2', 'mzi','dbr','spiral',
                'ge_detector_straight_si_contacts', 'crossing',
                'polarization_splitter_rotator',
            ]

        specs = self.load_multiple_specs(component_types)

        for comp_type, spec in specs.items():
            lines.append(f"Component: {comp_type}")
            
            # Port information
            ports = spec.get('ports', [])
            if ports:
                lines.append(f"  Ports ({len(ports)} total):")
                for port_name in ports:
                    port_details = spec.get('port_details', {}).get(port_name, {})
                    port_desc = f"    - {port_name}"
                    if port_details.get('orientation') is not None:
                        port_desc += f" (orientation: {port_details['orientation']}°)"
                    if port_details.get('width') is not None:
                        port_desc += f" (width: {port_details['width']}nm)"
                    lines.append(port_desc)
            else:
                lines.append(f"  Ports: {', '.join(spec.get('ports', []))}")
            
            # Parameters (function signature)
            if spec.get('parameters'):
                param_names = list(spec['parameters'].keys())
                # Filter out complex types (functions, ComponentSpec, etc.)
                simple_params = [p for p in param_names if p not in ['taper', 'straight', 'bend', 'cross_section', 'splitter', 'combiner']]
                if simple_params:
                    lines.append(f"  Valid Parameters: {', '.join(simple_params)}")
                    # Show a few key parameters with defaults
                    for param_name in simple_params[:5]:  # Show first 5
                        param_info = spec['parameters'][param_name]
                        param_desc = f"    - {param_name}"
                        if param_info.get('default') is not None:
                            param_desc += f" (default: {param_info['default']})"
                        if param_info.get('annotation'):
                            param_desc += f" [{param_info['annotation']}]"
                        lines.append(param_desc)
            
            # Settings (from info)
            if spec.get('settings'):
                lines.append(f"  Default settings: {spec['settings']}")
            
            # YAML DSL example
            if include_examples:
                lines.append(f"  YAML DSL Example:")
                lines.append(self._generate_yaml_example(comp_type, spec))
            
            # Common mistakes
            if comp_type == 'mmi1x2':
                lines.append(f"  ⚠️ WARNING: mmi2x1 does NOT exist! Use mmi1x2 with mirror: true")
            
            lines.append("")

        # Add error patterns
        if include_error_patterns:
            lines.append(self._generate_error_patterns())

        lines.append("=" * 70)
        
        return "\n".join(lines)

    def _generate_yaml_example(self, comp_type: str, spec: Dict) -> str:
        """Generate YAML DSL example for a component."""
        instance_name = comp_type.replace('_', '_')
        ports = spec.get('ports', [])
        
        example_lines = []
        example_lines.append(f"    instances:")
        example_lines.append(f"      {instance_name}:")
        example_lines.append(f"        component: {comp_type}")
        
        # Use parameters from signature, not settings
        if spec.get('parameters'):
            # Get simple parameters (not functions/ComponentSpec)
            simple_params = {}
            for param_name, param_info in spec['parameters'].items():
                if param_name not in ['taper', 'straight', 'bend', 'cross_section', 'splitter', 'combiner']:
                    if param_info.get('default') is not None:
                        simple_params[param_name] = param_info['default']
            
            if simple_params:
                example_lines.append(f"        settings:")
                for key, value in list(simple_params.items())[:3]:  # Show first 3
                    example_lines.append(f"          {key}: {value}")
        
        example_lines.append(f"    placements:")
        example_lines.append(f"      {instance_name}:")
        example_lines.append(f"        x: 0.0")
        example_lines.append(f"        y: 0.0")
        
        if ports:
            example_lines.append(f"    ports:")
            if len(ports) >= 1:
                example_lines.append(f"      in: {instance_name},{ports[0]}")
            if len(ports) >= 2:
                example_lines.append(f"      out: {instance_name},{ports[1]}")
        
        # example_lines is already a list, just join with newlines
        return "\n".join(example_lines)

    def _generate_error_patterns(self) -> str:
        """Generate common error patterns section."""
        lines = []
        lines.append("=" * 70)
        lines.append("COMMON ERROR PATTERNS TO AVOID")
        lines.append("=" * 70)
        lines.append("")
        lines.append("1. Missing Routes:")
        lines.append("   WRONG: Components placed but no routes section")
        lines.append("   CORRECT: Always include routes section with all connections")
        lines.append("")
        lines.append("2. Arithmetic in Port Names:")
        lines.append("   WRONG: splitter,o4-1  or  mmi1,o3+1")
        lines.append("   CORRECT: splitter,o3  or  mmi1,o4  (compute the value yourself)")
        lines.append("")
        lines.append("3. Wrong Component Names:")
        lines.append("   WRONG: component: mmi2x1  (does not exist)")
        lines.append("   CORRECT: component: mmi1x2 with mirror: true")
        lines.append("")
        lines.append("4. Component/Settings in Placements:")
        lines.append("   WRONG: placements: {ps1: {component: straight_heater_metal, x: 0}}")
        lines.append("   CORRECT: Put 'component' and 'settings' in 'instances' only.")
        lines.append("            Placements only have: x, y, rotation, mirror.")
        lines.append("")
        lines.append("5. Wrong Port Names:")
        lines.append("   WRONG: Using non-existent ports like 'p1', 'p2'")
        lines.append("   CORRECT: Use actual port names: 'o1', 'o2', 'o3', etc.")
        lines.append("")
        lines.append("6. Unicode Characters:")
        lines.append("   WRONG: Using 'um', 'x', '->', 'DeltaL'")
        lines.append("   CORRECT: Use ASCII only")
        lines.append("")
        return "\n".join(lines)

    def get_available_ports(self, component_type: str) -> List[str]:
        """Get list of available ports for a component."""
        spec = self.load_component_spec(component_type)
        if spec:
            return spec.get('ports', [])
        return []

    def validate_port_name(self, component_type: str, port_name: str) -> bool:
        """Validate that a port name exists for a component."""
        available_ports = self.get_available_ports(component_type)
        return port_name in available_ports
