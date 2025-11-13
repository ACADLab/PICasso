"""
Unit tests for SAX validator.

Test Cases:
1. Valid circuit → SAX compilation succeeds
2. Missing SAX models → Create/register models automatically
3. Invalid netlist → SAX compilation fails
4. Functional validation → S-matrix meets spec (IL, ER, etc.)
"""

import unittest
import gdsfactory as gf
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSAXValidator(unittest.TestCase):
    """Test SAX validator."""

    def setUp(self):
        """Set up test fixtures."""
        # TODO: Import and initialize SAX validator
        # from gd_picasso.validators.sax_validator import SAXValidator
        # self.validator = SAXValidator()
        pass

    def test_valid_circuit_sax_compilation(self):
        """Test that valid circuit compiles with SAX."""
        # Create a simple component
        c = gf.components.mmi1x2()
        
        # TODO: Implement SAX validation
        # result = self.validator.validate(c)
        # self.assertTrue(result['compilation_passed'])
        self.skipTest("SAX validator not yet implemented")

    def test_missing_sax_models(self):
        """Test that missing SAX models are created/registered."""
        # TODO: Implement test
        self.skipTest("SAX validator not yet implemented")

    def test_functional_validation(self):
        """Test functional validation (IL, ER, etc.)."""
        # TODO: Implement test
        self.skipTest("SAX validator not yet implemented")


if __name__ == '__main__':
    unittest.main()

