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
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSAXValidator(unittest.TestCase):
    """Test SAX validator."""

    def setUp(self):
        """Set up test fixtures."""
        from gdsfactory.gpdk import get_generic_pdk

        get_generic_pdk().activate()
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

    def test_polarization_splitter_rotator_model(self):
        """Test the compact PSR SAX model."""
        from gd_picasso.validators.sax_models import polarization_splitter_rotator

        sdict = polarization_splitter_rotator(split_ratio=0.25, loss_dB=0.0)

        self.assertIn(("o1", "o2"), sdict)
        self.assertIn(("o2", "o1"), sdict)
        self.assertIn(("o1", "o3"), sdict)
        self.assertIn(("o3", "o1"), sdict)
        self.assertAlmostEqual(abs(sdict[("o1", "o2")]) ** 2, 0.25)
        self.assertAlmostEqual(abs(sdict[("o1", "o3")]) ** 2, 0.75)

    def test_polarization_splitter_rotator_registration(self):
        """Test that the PSR model is registered with SAX compilation."""
        import sax
        from gd_picasso.validators.sax_models import polarization_splitter_rotator

        netlist = {
            "instances": {"psr": {"component": "polarization_splitter_rotator"}},
            "connections": {},
            "ports": {
                "o1": "psr,o1",
                "o2": "psr,o2",
                "o3": "psr,o3",
            },
        }
        circuit, _ = sax.circuit(
            netlist,
            models={"polarization_splitter_rotator": polarization_splitter_rotator},
        )
        sdict = circuit()

        self.assertTrue(np.isfinite(abs(sdict[("o1", "o2")])))

    def test_mock_sax_models_are_repo_owned(self):
        """Test that temporary SAX mocks are loaded from gd_picasso."""
        from gd_picasso.validators.sax_models import get_patched_sax_models

        patched_models = get_patched_sax_models()

        for model_name in (
            "crossing",
            "DBR",
            "dbr",
            "ge_detector_straight_si_contacts",
            "spiral",
        ):
            self.assertIn(model_name, patched_models)
            self.assertEqual(
                patched_models[model_name].__module__,
                "gd_picasso.validators.sax_models",
            )

    def test_mock_sax_models_compile_from_internal_registry(self):
        """Test that the patched models satisfy SAX without installed fallbacks."""
        import sax
        from gd_picasso.validators.sax_models import get_patched_sax_models

        sax.set_port_naming_strategy("optical")
        netlist = {
            "instances": {
                "cross": {"component": "crossing"},
                "mirror": {"component": "DBR"},
                "delay": {"component": "spiral"},
                "detector": {"component": "ge_detector_straight_si_contacts"},
            },
            "connections": {
                "cross,o3": "mirror,o1",
                "mirror,o2": "delay,o1",
                "delay,o2": "detector,o1",
            },
            "ports": {
                "in": "cross,o1",
                "north": "cross,o2",
                "south": "cross,o4",
                "det_bot": "detector,bot",
                "det_top": "detector,top",
            },
        }

        circuit, _ = sax.circuit(
            netlist,
            models=get_patched_sax_models(),
            on_internal_port="as_probes",
        )

        self.assertTrue(callable(circuit))


if __name__ == '__main__':
    unittest.main()
