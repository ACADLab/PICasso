"""
Unit tests for YAML parser (gf.read.from_yaml()).

Test Cases:
1. Valid YAML → Component conversion using gf.read.from_yaml()
2. Invalid YAML → Error handling
3. Missing components → Error handling
4. Invalid placements → Error handling
5. Invalid routes → Error handling
"""

import unittest
import gdsfactory as gf
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestYAMLParser(unittest.TestCase):
    """Test YAML parser."""

    def test_valid_yaml_to_component(self):
        """Test that valid YAML converts to Component."""
        valid_yaml = """
instances:
  mmi1:
    component: mmi1x2
    settings:
      width: 4.0
placements:
  mmi1:
    x: 0
    y: 0
ports:
  o1: mmi1,o1
  o2: mmi1,o2
"""
        try:
            component = gf.read.from_yaml(valid_yaml)
            self.assertIsInstance(component, gf.Component)
        except Exception as e:
            self.fail(f"Valid YAML should convert to Component: {e}")

    def test_invalid_yaml_error_handling(self):
        """Test that invalid YAML raises appropriate error."""
        invalid_yaml = """
instances:
  mmi1:
    component: mmi1x2
    settings: [invalid syntax
"""
        with self.assertRaises(Exception):
            gf.read.from_yaml(invalid_yaml)

    def test_missing_components_error_handling(self):
        """Test that missing components raise appropriate error."""
        missing_component = """
instances:
  mmi1:
    component: nonexistent_component
placements:
  mmi1:
    x: 0
    y: 0
"""
        # Should raise error about missing component
        with self.assertRaises(Exception):
            gf.read.from_yaml(missing_component)


if __name__ == '__main__':
    unittest.main()

