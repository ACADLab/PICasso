"""
Component Spec Loader

Loads component specifications dynamically from gdsfactory.
Caches port information per component type and generates port reference for prompts.
Includes SAX model information and instructions for creating SAX models.
"""

import logging
import gdsfactory as gf
from typing import Dict, List, Optional
from pathlib import Path
import json

from ..utils.port_utils import get_port_names, get_port_items

logger = logging.getLogger(__name__)

# Try to import SAX modules
try:
    from ..sax_models.sax_model_manager import SAXModelManager
    from ..sax_models.sax_knowledge import SAXKnowledgeBase
    SAX_AVAILABLE = True
except ImportError:
    SAX_AVAILABLE = False
    SAXModelManager = None
    SAXKnowledgeBase = None

# Try to import pydoc loader
try:
    from .pydoc_component_loader import PydocComponentLoader
    PYDOC_AVAILABLE = True
except ImportError:
    PYDOC_AVAILABLE = False
    PydocComponentLoader = None


class ComponentSpecLoader:
    """Loads and caches component specifications."""

    def __init__(self, cache_file: Optional[Path] = None, use_pydoc: bool = True):
        """
        Initialize component spec loader.

        Args:
            cache_file: Optional path to cache file
            use_pydoc: Whether to use pydoc-based loader for comprehensive specs
        """
        self.cache_file = cache_file or Path(__file__).parent / "component_specs_cache.json"
        self.specs_cache = self._load_cache()
        self.port_matcher = None  # Will be set by framework
        self.use_pydoc = use_pydoc and PYDOC_AVAILABLE
        
        # Initialize pydoc loader if available
        if self.use_pydoc:
            self.pydoc_loader = PydocComponentLoader()
            logger.info("Using pydoc-based component loader for comprehensive specs")
        else:
            self.pydoc_loader = None
            if use_pydoc:
                logger.warning("Pydoc loader requested but not available, using fallback")
        
        # Initialize SAX model manager and knowledge base if available
        if SAX_AVAILABLE:
            self.sax_model_manager = SAXModelManager()
            self.sax_knowledge = SAXKnowledgeBase(self.sax_model_manager)
        else:
            self.sax_model_manager = None
            self.sax_knowledge = None

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
            
            # Extract port information using port utilities
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
            
            # Get component settings/parameters
            settings = {}
            if hasattr(comp_func, 'info'):
                settings = comp_func.info.get('defaults', {})
            
            spec = {
                "component_type": component_type,
                "ports": port_names,
                "port_details": ports,
                "port_count": len(port_names),
                "settings": settings,
            }
            
            # Cache it
            self.specs_cache[component_type] = spec
            self._save_cache()
            
            return spec
            
        except Exception as e:
            logger.error(f"Error loading component spec for '{component_type}': {e}")
            return None

    def load_multiple_specs(self, component_types: List[str]) -> Dict[str, Dict]:
        """
        Load specifications for multiple components.

        Args:
            component_types: List of component type names

        Returns:
            Dictionary mapping component_type -> spec
        """
        specs = {}
        for comp_type in component_types:
            spec = self.load_component_spec(comp_type)
            if spec:
                specs[comp_type] = spec
        return specs

    def generate_port_reference(self, component_types: List[str], include_sax: bool = True) -> str:
        """
        Generate port reference string for LLM prompts with SAX information.

        Args:
            component_types: List of component types
            include_sax: Whether to include SAX model information

        Returns:
            Formatted port reference string with SAX info
        """
        # Use pydoc loader if available for comprehensive specs
        if self.use_pydoc and self.pydoc_loader:
            try:
                # Generate comprehensive specs using pydoc loader
                formatted_specs = self.pydoc_loader.generate_formatted_specs(
                    component_names=component_types,
                    include_routing=True
                )
                
                # Add SAX information if needed
                if include_sax and self.sax_model_manager:
                    lines = formatted_specs.split('\n')
                    # Find component sections and add SAX info
                    enhanced_lines = []
                    current_component = None
                    for line in lines:
                        enhanced_lines.append(line)
                        if line.startswith("Component: "):
                            current_component = line.replace("Component: ", "").strip()
                        elif line.startswith("  Usage Example:") and current_component:
                            # Add SAX info before usage example
                            if self.sax_model_manager:
                                sax_info = self.sax_model_manager.get_model_info(current_component)
                                if sax_info:
                                    exists = sax_info.get('exists', False)
                                    sax_model_name = sax_info.get('sax_model_name')
                                    if exists:
                                        enhanced_lines.append(f"  SAX Model: ✅ Available ({sax_model_name})")
                                    else:
                                        enhanced_lines.append(f"  SAX Model: ⚠️ Not available (model name: {sax_model_name})")
                    
                    formatted_specs = '\n'.join(enhanced_lines)
                
                # Add SAX model creation instructions at the end
                if include_sax:
                    formatted_specs += "\n" + self._generate_sax_instructions()
                
                return formatted_specs
            except Exception as e:
                logger.warning(f"Pydoc loader failed, falling back to basic loader: {e}")
        
        # Fallback to basic loader
        specs = self.load_multiple_specs(component_types)
        
        lines = []
        lines.append("=" * 70)
        lines.append("AVAILABLE GDSFACTORY COMPONENTS REFERENCE")
        lines.append("=" * 70)
        lines.append("")
        lines.append("⚠️ CRITICAL: Use ONLY these components. Verify component names exist before using!")
        lines.append("")
        
        for comp_type, spec in specs.items():
            lines.append(f"Component: {comp_type}")
            
            # Enhanced port information with orientations
            ports = spec.get('ports', [])
            if ports:
                lines.append(f"  Ports ({len(ports)} total):")
                # Try to get port details if available
                try:
                    comp_func = getattr(gf.components, comp_type, None)
                    if comp_func:
                        comp = comp_func()
                        for port_name in ports:
                            port_details = None
                            for p_name, p_obj in get_port_items(comp.ports):
                                if p_name == port_name:
                                    orientation = getattr(p_obj, 'orientation', None)
                                    width = getattr(p_obj, 'width', None)
                                    port_desc = f"    - {port_name}"
                                    if orientation is not None:
                                        port_desc += f" (orientation: {orientation}°)"
                                    if width is not None:
                                        port_desc += f" (width: {width}nm)"
                                    lines.append(port_desc)
                                    break
                            else:
                                lines.append(f"    - {port_name}")
                except:
                    # Fallback to simple list
                    for port_name in ports:
                        lines.append(f"    - {port_name}")
            else:
                lines.append(f"  Ports: {', '.join(spec.get('ports', []))}")
            
            if spec.get('settings'):
                lines.append(f"  Default settings: {spec['settings']}")
            
            # Add SAX information if available
            if include_sax and self.sax_model_manager:
                sax_info = self.sax_model_manager.get_model_info(comp_type)
                if sax_info:
                    sax_model_name = sax_info.get('sax_model_name')
                    exists = sax_info.get('exists', False)
                    if exists:
                        lines.append(f"  SAX Model: ✅ Available ({sax_model_name})")
                        
                        # Add usage example from SAX knowledge
                        if self.sax_knowledge:
                            sax_comp_info = self.sax_knowledge.get_component_sax_info(comp_type)
                            if sax_comp_info and sax_comp_info.get('usage_example'):
                                lines.append(f"  SAX Usage: {sax_comp_info['usage_example'].strip()}")
                    else:
                        lines.append(f"  SAX Model: ⚠️ Not available (model name: {sax_model_name})")
                        lines.append(f"  → Action: Create SAX model (see instructions below)")
                else:
                    lines.append(f"  SAX Model: ❌ Not found")
                    lines.append(f"  → Action: Create SAX model (see instructions below)")
            
            # Add common mistake warnings
            if comp_type == 'mmi1x2':
                lines.append(f"  ⚠️ WARNING: mmi2x1 does NOT exist! Use mmi1x2() and mirror it:")
                lines.append(f"    ref = r.add_ref(gf.components.mmi1x2())")
                lines.append(f"    ref.mirror()  # Mirror to create 2x1 combiner")
            
            lines.append("")
        
        # Add SAX model creation instructions
        if include_sax:
            lines.append(self._generate_sax_instructions())
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def _generate_sax_instructions(self) -> str:
        """Generate SAX model creation instructions."""
        lines = []
        lines.append("=" * 70)
        lines.append("SAX MODEL CREATION INSTRUCTIONS")
        lines.append("=" * 70)
        lines.append("")
        lines.append("If a component does NOT have a SAX model, you can create one:")
        lines.append("")
        lines.append("Method 1: Use gplugins.sax (Recommended)")
        lines.append("```python")
        lines.append("import gplugins.sax as gs")
        lines.append("import sax")
        lines.append("")
        lines.append("# Check if model exists")
        lines.append("if hasattr(gs.models, 'component_name'):")
        lines.append("    model = gs.models.component_name")
        lines.append("else:")
        lines.append("    # Create model from component")
        lines.append("    comp = gf.components.component_name()")
        lines.append("    model = gs.read.model_from_gdsfactory(comp)")
        lines.append("```")
        lines.append("")
        lines.append("Method 2: Use default SAX models")
        lines.append("```python")
        lines.append("import sax")
        lines.append("import gplugins.sax as gs")
        lines.append("")
        lines.append("# Common model mappings:")
        lines.append("models = {")
        lines.append("    'straight': gs.models.straight,")
        lines.append("    'bend_euler': gs.models.bend,")
        lines.append("    'mmi1x2': gs.models.mmi1x2,")
        lines.append("    'straight_heater_metal': sax.models.phase_shifter,")
        lines.append("}")
        lines.append("```")
        lines.append("")
        lines.append("Method 3: Create custom SAX model")
        lines.append("```python")
        lines.append("import sax")
        lines.append("")
        lines.append("@sax.model")
        lines.append("def my_component_model(length: float = 10.0, width: float = 0.5):")
        lines.append("    # Define S-parameters")
        lines.append("    S = {...}  # S-parameter matrix")
        lines.append("    return S")
        lines.append("```")
        lines.append("")
        lines.append("⚠️ IMPORTANT:")
        lines.append("  - Always check if SAX model exists before using component")
        lines.append("  - Use standard GDSFactory components that have SAX models when possible")
        lines.append("  - If creating custom model, ensure it matches component behavior")
        lines.append("  - Test SAX model with: circuit, _ = sax.circuit(netlist, models=models)")
        lines.append("")
        return "\n".join(lines)

    def get_available_ports(self, component_type: str) -> List[str]:
        """
        Get list of available ports for a component.

        Args:
            component_type: Component type name

        Returns:
            List of port names
        """
        spec = self.load_component_spec(component_type)
        if spec:
            return spec.get('ports', [])
        return []

    def validate_port_name(self, component_type: str, port_name: str) -> bool:
        """
        Validate that a port name exists for a component.

        Args:
            component_type: Component type name
            port_name: Port name to validate

        Returns:
            True if port exists
        """
        available_ports = self.get_available_ports(component_type)
        return port_name in available_ports

