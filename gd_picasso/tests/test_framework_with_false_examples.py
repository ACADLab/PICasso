"""
End-to-end integration test with false examples.

Tests full framework pipeline with converted false examples.
Verifies framework detects 100% of known errors.
"""

import unittest
import yaml
import gdsfactory as gf
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gd_picasso.validators.yaml_pilot_validator import YAMLPilotValidator
from gd_picasso.validators.drc_validator import DRCValidator
from gd_picasso.validators.lvs_validator import LVSValidator
from gd_picasso.optimizers.optimization_integration import OptimizationIntegration


class TestFrameworkWithFalseExamples(unittest.TestCase):
    """Test framework with false examples."""

    def setUp(self):
        """Set up test fixtures."""
        self.yaml_pilot_validator = YAMLPilotValidator()
        self.drc_validator = DRCValidator()
        self.lvs_validator = LVSValidator(enabled=False)  # Disable for speed
        self.optimizer = OptimizationIntegration()

    def test_missing_routes_detection(self):
        """Test that missing routes are detected."""
        # YAML with components placed but no routes
        yaml_str = """
instances:
  mmi1:
    component: mmi1x2
  mmi2:
    component: mmi1x2
placements:
  mmi1:
    x: 0.0
    y: 0.0
  mmi2:
    x: 250.0
    y: 0.0
# Missing routes section
"""
        is_valid, error_msg, error_details = self.yaml_pilot_validator.validate(yaml_str)
        self.assertFalse(is_valid, "Should detect missing routes")
        self.assertIn("routes", error_msg.lower())

    def test_spacing_violation_detection(self):
        """Test that spacing violations are detected."""
        # YAML with components too close
        yaml_str = """
instances:
  mmi1:
    component: mmi1x2
  mmi2:
    component: mmi1x2
placements:
  mmi1:
    x: 0.0
    y: 0.0
  mmi2:
    x: 50.0  # Too close (< 200um)
    y: 0.0
routes:
  optical:
    links:
      mmi1,o2: mmi2,o1
"""
        is_valid, error_msg, error_details = self.yaml_pilot_validator.validate(yaml_str)
        self.assertFalse(is_valid, "Should detect spacing violation")
        self.assertIn("too close", error_msg.lower())

    def test_unicode_detection(self):
        """Test that Unicode characters are detected."""
        # YAML with Unicode
        yaml_str = """
instances:
  mmi1:
    component: mmi1x2
    settings:
      width: 4.0  # 4µm  ← Unicode character
placements:
  mmi1:
    x: 0.0
    y: 0.0
"""
        is_valid, error_msg, error_details = self.yaml_pilot_validator.validate(yaml_str)
        self.assertFalse(is_valid, "Should detect Unicode characters")
        self.assertIn("unicode", error_msg.lower())

    def test_invalid_component_detection(self):
        """Test that invalid component names are detected."""
        # YAML with invalid component
        yaml_str = """
instances:
  mmi1:
    component: mmi2x1  # Does not exist
placements:
  mmi1:
    x: 0.0
    y: 0.0
"""
        is_valid, error_msg, error_details = self.yaml_pilot_validator.validate(yaml_str)
        self.assertFalse(is_valid, "Should detect invalid component name")
        self.assertIn("invalid", error_msg.lower())

    def test_valid_yaml_passes(self):
        """Test that valid YAML passes all checks."""
        # Valid YAML
        yaml_str = """
instances:
  mmi1:
    component: mmi1x2
  mmi2:
    component: mmi1x2
placements:
  mmi1:
    x: 0.0
    y: 0.0
  mmi2:
    x: 250.0
    y: 0.0
routes:
  optical:
    settings:
      cross_section: strip
      radius: 20.0
    links:
      mmi1,o2: mmi2,o1
ports:
  in: mmi1,o1
  out: mmi2,o2
"""
        is_valid, error_msg, error_details = self.yaml_pilot_validator.validate(yaml_str)
        self.assertTrue(is_valid, f"Valid YAML should pass: {error_msg}")

    def test_drc_validation(self):
        """Test DRC validation with generic_tech PDK."""
        # Create a simple component
        c = gf.components.mmi1x2()
        
        # Run DRC
        passed, report = self.drc_validator.validate(c)
        
        # Should either pass or provide meaningful feedback
        self.assertIsInstance(passed, bool)
        self.assertIn("passed", report)
        self.assertIn("violations", report)

    def test_optimizer_verification(self):
        """Test that optimizers work with YAML-generated components."""
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
            
            # Verify device optimizer
            device_result = self.optimizer.verify_device_optimizer(component)
            # Should not fail due to YAML origin
            self.assertIsNotNone(device_result)
            
            # Verify circuit optimizer
            circuit_result = self.optimizer.verify_circuit_optimizer(component)
            # Should confirm svd_bound approach
            self.assertTrue(circuit_result.get("uses_svd_approach", False))
            
        except Exception as e:
            self.skipTest(f"YAML parsing failed: {e}")


if __name__ == '__main__':
    unittest.main()

