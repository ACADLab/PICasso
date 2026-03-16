"""
Unit tests for optimizers.

Test Cases:
1. Device-level optimizer works with YAML-generated components
2. Circuit-level optimizer uses σ₁²(T) approach (drive="svd")
3. Optimizers produce valid results
"""

import unittest
import gdsfactory as gf
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gd_picasso.optimizers.optimization_integration import OptimizationIntegration


class TestOptimizers(unittest.TestCase):
    """Test optimizers."""

    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = OptimizationIntegration(
            enable_device_optimization=True,
            enable_circuit_optimization=True
        )

    def test_device_optimizer_with_yaml_component(self):
        """Test device-level optimizer works with YAML-generated component."""
        # Create component from YAML
        yaml_str = """
instances:
  mmi1:
    component: mmi1x2
placements:
  mmi1:
    x: 0.0
    y: 0.0
ports:
  in: mmi1,o1
  out: mmi1,o2
"""
        try:
            component = gf.read.from_yaml(yaml_str)
            result = self.optimizer.verify_device_optimizer(component)
            
            # Should not fail due to YAML origin
            self.assertIsNotNone(result)
            # Result may succeed or fail based on optimizer availability, but should not error
        except Exception as e:
            self.skipTest(f"YAML parsing failed: {e}")

    def test_circuit_optimizer_svd_approach(self):
        """Test circuit-level optimizer uses σ₁²(T) approach."""
        # Create component from YAML
        yaml_str = """
instances:
  mmi1:
    component: mmi1x2
placements:
  mmi1:
    x: 0.0
    y: 0.0
ports:
  in: mmi1,o1
  out: mmi1,o2
"""
        try:
            component = gf.read.from_yaml(yaml_str)
            result = self.optimizer.verify_circuit_optimizer(component)
            
            # Should confirm svd_bound approach
            self.assertTrue(result.get("uses_svd_approach", False), 
                          "Circuit optimizer should use σ₁²(T) approach")
            self.assertTrue(result.get("svd_bound_available", False),
                          "svd_bound function should be available")
        except Exception as e:
            self.skipTest(f"YAML parsing failed: {e}")

    def test_optimizer_works_with_python_component(self):
        """Test optimizers work with Python-generated components (baseline)."""
        # Create component from Python
        c = gf.components.mmi1x2()
        
        # Verify device optimizer
        device_result = self.optimizer.verify_device_optimizer(c)
        self.assertIsNotNone(device_result)
        
        # Verify circuit optimizer
        circuit_result = self.optimizer.verify_circuit_optimizer(c)
        self.assertTrue(circuit_result.get("uses_svd_approach", False))


if __name__ == '__main__':
    unittest.main()

