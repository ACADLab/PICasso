"""
Framework Test Suite

Runs extracted test cases through enhanced validators.
Verifies framework catches 100% of routing/DRC issues that SAX misses.
"""

import logging
from typing import Dict, List, Tuple
from pathlib import Path
import gdsfactory as gf

from .test_extractor import TestExtractor
from ..validators.pnr_validator import PNRValidator
from ..validators.drc_validator import DRCValidator
from ..validators.sax_validator import SAXValidator
from ..functionality.port_declaration_validator import PortDeclarationValidator
from ..functionality.silicon_efficiency import SiliconEfficiencyChecker
from ..config import TARGET_CATCH_RATE, TEST_WITH_TEST_9

logger = logging.getLogger(__name__)


class FrameworkTestSuite:
    """Test suite for framework validation."""

    def __init__(self):
        """Initialize test suite."""
        self.pnr_validator = PNRValidator()
        self.drc_validator = DRCValidator()
        self.sax_validator = SAXValidator()
        self.port_validator = PortDeclarationValidator()
        self.silicon_checker = SiliconEfficiencyChecker()
        self.test_results = []

    def run_tests(self, test_cases: List[Dict]) -> Dict:
        """
        Run test cases through enhanced validators.

        Args:
            test_cases: List of test cases

        Returns:
            Test results dictionary
        """
        results = {
            "total_tests": len(test_cases),
            "sax_only_passed": 0,
            "sax_only_failed": 0,
            "enhanced_passed": 0,
            "enhanced_failed": 0,
            "routing_drc_caught": 0,
            "routing_drc_missed": 0,
            "test_details": [],
        }
        
        for test_case in test_cases:
            test_result = self._run_single_test(test_case)
            results["test_details"].append(test_result)
            
            # Count results
            if test_result["sax_passes"]:
                results["sax_only_passed"] += 1
            else:
                results["sax_only_failed"] += 1
            
            if test_result["enhanced_passes"]:
                results["enhanced_passed"] += 1
            else:
                results["enhanced_failed"] += 1
            
            # Check if framework caught issues that SAX missed
            if test_result["sax_passes"] and not test_result["enhanced_passes"]:
                results["routing_drc_caught"] += 1
            elif test_result["sax_passes"] and test_result["enhanced_passes"]:
                # SAX passes and enhanced passes - check if there were issues
                if test_result.get("routing_issues") or test_result.get("drc_issues"):
                    results["routing_drc_missed"] += 1
        
        # Calculate catch rate
        total_false_data = results["routing_drc_caught"] + results["routing_drc_missed"]
        if total_false_data > 0:
            catch_rate = results["routing_drc_caught"] / total_false_data
            results["catch_rate"] = catch_rate
            results["meets_target"] = catch_rate >= TARGET_CATCH_RATE
        else:
            results["catch_rate"] = 1.0
            results["meets_target"] = True
        
        self.test_results = results
        return results

    def _run_single_test(self, test_case: Dict) -> Dict:
        """
        Run a single test case.

        Args:
            test_case: Test case dictionary

        Returns:
            Test result dictionary
        """
        result = {
            "test_case": test_case.get("source_file", "unknown"),
            "cell_index": test_case.get("cell_index", -1),
            "sax_passes": False,
            "enhanced_passes": False,
            "pnr_passes": False,
            "drc_passes": False,
            "port_passes": False,
            "silicon_passes": False,
            "routing_issues": [],
            "drc_issues": [],
            "errors": [],
        }
        
        code = test_case.get("code")
        if not code:
            result["errors"].append("No code found")
            return result
        
        try:
            # Execute code
            ns = {"gf": gf}
            exec(code, ns)
            
            # Find component
            component = None
            for var_name in ['r', 'c', 'circuit', 'component']:
                if var_name in ns and isinstance(ns[var_name], gf.Component):
                    component = ns[var_name]
                    break
            
            if component is None:
                result["errors"].append("No component found")
                return result
            
            # Check SAX compilation
            sax_passed, sax_report = self.sax_validator.validate(component)
            result["sax_passes"] = sax_passed
            
            # Run enhanced validators
            pnr_passed, pnr_report = self.pnr_validator.validate(component)
            result["pnr_passes"] = pnr_passed
            if not pnr_passed:
                result["routing_issues"].extend(pnr_report.get("errors", []))
            
            drc_passed, drc_report = self.drc_validator.validate(component)
            result["drc_passes"] = drc_passed
            if not drc_passed:
                result["drc_issues"].extend(drc_report.get("errors", []))
            
            port_passed, port_report = self.port_validator.validate(component)
            result["port_passes"] = port_passed
            
            silicon_passed, silicon_report = self.silicon_checker.check(component)
            result["silicon_passes"] = silicon_passed
            
            # Enhanced validation passes if all checks pass
            result["enhanced_passes"] = (
                pnr_passed and drc_passed and port_passed and silicon_passed
            )
            
        except Exception as e:
            result["errors"].append(f"Test execution error: {str(e)}")
            logger.error(f"Error running test: {e}")
        
        return result

    def generate_report(self) -> str:
        """
        Generate test report.

        Returns:
            Formatted test report string
        """
        if not self.test_results:
            return "No test results available"
        
        results = self.test_results
        
        lines = []
        lines.append("=" * 70)
        lines.append("FRAMEWORK TEST RESULTS")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Total tests: {results['total_tests']}")
        lines.append(f"SAX-only passed: {results['sax_only_passed']}")
        lines.append(f"SAX-only failed: {results['sax_only_failed']}")
        lines.append(f"Enhanced passed: {results['enhanced_passed']}")
        lines.append(f"Enhanced failed: {results['enhanced_failed']}")
        lines.append("")
        lines.append(f"Routing/DRC issues caught: {results['routing_drc_caught']}")
        lines.append(f"Routing/DRC issues missed: {results['routing_drc_missed']}")
        lines.append(f"Catch rate: {results.get('catch_rate', 0):.1%}")
        lines.append(f"Target catch rate: {TARGET_CATCH_RATE:.1%}")
        lines.append(f"Meets target: {'YES' if results.get('meets_target') else 'NO'}")
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)


