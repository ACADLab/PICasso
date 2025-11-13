"""
SAX Model Manager

Manages SAX component models, detects missing models, and creates/registers them.
Handles version compatibility and provides SAX model knowledge.
"""

import logging
from typing import Dict, List, Optional, Tuple
import gdsfactory as gf
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SAXModelManager:
    """Manages SAX component models."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize SAX model manager.

        Args:
            cache_dir: Directory for SAX model cache
        """
        self.cache_dir = cache_dir or Path(__file__).parent / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_cache = {}
        self.gdsfactory_version = None
        self._detect_version()
        self._load_cache()

    def _detect_version(self):
        """Detect gdsfactory version."""
        try:
            import gdsfactory as gf
            if hasattr(gf, '__version__'):
                self.gdsfactory_version = gf.__version__
            else:
                self.gdsfactory_version = "unknown"
            logger.info(f"Detected gdsfactory version: {self.gdsfactory_version}")
        except Exception as e:
            logger.warning(f"Could not detect gdsfactory version: {e}")
            self.gdsfactory_version = "unknown"

    def _load_cache(self):
        """Load SAX model cache from disk."""
        cache_file = self.cache_dir / "sax_models_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self.model_cache = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load SAX model cache: {e}")

    def _save_cache(self):
        """Save SAX model cache to disk."""
        cache_file = self.cache_dir / "sax_models_cache.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.model_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save SAX model cache: {e}")

    def check_sax_model_exists(self, component_type: str) -> bool:
        """
        Check if SAX model exists for component.

        Args:
            component_type: Component type name

        Returns:
            True if SAX model exists
        """
        try:
            import sax
            import gplugins.sax as gs
            
            # Check if model exists in gplugins.sax.models
            if hasattr(gs.models, component_type):
                return True
            
            # Check common model mappings
            model_mappings = {
                'mmi1x2': 'mmi1x2',
                'mmi2x1': 'mmi1x2',  # Same model, different orientation
                'straight_heater_metal': 'phase_shifter',
                'straight': 'straight',
                'bend_euler': 'bend',
            }
            
            if component_type in model_mappings:
                sax_model_name = model_mappings[component_type]
                if hasattr(gs.models, sax_model_name) or hasattr(sax.models, sax_model_name):
                    return True
            
            return False
            
        except ImportError:
            logger.warning("SAX or gplugins not available")
            return False

    def get_sax_model_name(self, component_type: str) -> Optional[str]:
        """
        Get SAX model name for component.

        Args:
            component_type: Component type name

        Returns:
            SAX model name or None
        """
        # Check cache first
        if component_type in self.model_cache:
            return self.model_cache[component_type].get('sax_model_name')
        
        # Check common mappings
        model_mappings = {
            'mmi1x2': 'mmi1x2',
            'mmi2x1': 'mmi1x2',
            'straight_heater_metal': 'phase_shifter',
            'straight': 'straight',
            'bend_euler': 'bend',
            'bend_circular': 'bend',
        }
        
        if component_type in model_mappings:
            sax_name = model_mappings[component_type]
            # Cache it
            self.model_cache[component_type] = {
                'sax_model_name': sax_name,
                'gdsfactory_version': self.gdsfactory_version
            }
            self._save_cache()
            return sax_name
        
        return None

    def create_sax_model(self, component_type: str) -> Optional[str]:
        """
        Create SAX model for component if missing.

        Args:
            component_type: Component type name

        Returns:
            SAX model name if created, None otherwise
        """
        try:
            import sax
            import gplugins.sax as gs
            
            # Check if already exists
            if self.check_sax_model_exists(component_type):
                return self.get_sax_model_name(component_type)
            
            # Try to create model from component
            comp_func = getattr(gf.components, component_type, None)
            if comp_func is None:
                logger.warning(f"Cannot create SAX model: component '{component_type}' not found")
                return None
            
            # For now, return a default mapping
            # Full implementation would create actual SAX models
            logger.info(f"Creating SAX model mapping for '{component_type}'")
            
            # Use generic model if available
            if hasattr(gs.models, 'straight'):
                model_name = 'straight'
            elif hasattr(sax.models, 'straight'):
                model_name = 'straight'
            else:
                logger.warning(f"Cannot create SAX model: no base models available")
                return None
            
            # Cache it
            self.model_cache[component_type] = {
                'sax_model_name': model_name,
                'gdsfactory_version': self.gdsfactory_version,
                'created': True
            }
            self._save_cache()
            
            return model_name
            
        except ImportError:
            logger.warning("SAX or gplugins not available for model creation")
            return None
        except Exception as e:
            logger.error(f"Error creating SAX model for '{component_type}': {e}")
            return None

    def get_model_info(self, component_type: str) -> Optional[Dict]:
        """
        Get SAX model information for component.

        Args:
            component_type: Component type name

        Returns:
            Model information dictionary or None
        """
        sax_model_name = self.get_sax_model_name(component_type)
        if not sax_model_name:
            # Try to create if missing
            sax_model_name = self.create_sax_model(component_type)
        
        if sax_model_name:
            return {
                'component_type': component_type,
                'sax_model_name': sax_model_name,
                'exists': self.check_sax_model_exists(component_type),
                'gdsfactory_version': self.gdsfactory_version
            }
        
        return None

    def get_all_model_mappings(self) -> Dict[str, str]:
        """
        Get all component to SAX model mappings.

        Returns:
            Dictionary mapping component_type -> sax_model_name
        """
        mappings = {}
        
        # Common components
        common_components = [
            'mmi1x2', 'mmi2x1', 'straight_heater_metal',
            'straight', 'bend_euler', 'bend_circular'
        ]
        
        for comp_type in common_components:
            sax_name = self.get_sax_model_name(comp_type)
            if sax_name:
                mappings[comp_type] = sax_name
        
        return mappings


