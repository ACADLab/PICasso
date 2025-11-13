"""
Enhanced Functional Validator

Extends existing functional validator with port declaration and silicon efficiency checks.
"""

import logging
from typing import Dict, Tuple, Optional
import gdsfactory as gf

from .port_declaration_validator import PortDeclarationValidator
from .silicon_efficiency import SiliconEfficiencyChecker
from ..validators.functional_validator import FunctionalValidator

logger = logging.getLogger(__name__)


class FunctionalValidatorEnhanced(FunctionalValidator):
    """Enhanced functional validator with port and silicon checks."""

    def __init__(self, enable: bool = True):
        """
        Initialize enhanced functional validator.

        Args:
            enable: Enable functional validation
        """
        super().__init__(enable)
        self.port_validator = PortDeclarationValidator()
        self.silicon_checker = SiliconEfficiencyChecker()

    def validate(
        self,
        component: gf.Component,
        circuit_type: str,
        problem_spec: Optional[Dict] = None
    ) -> Dict:
        """
        Enhanced validation including port declaration and silicon efficiency.

        Args:
            component: GDSFactory component to test
            circuit_type: Type of circuit
            problem_spec: Optional problem specification

        Returns:
            Enhanced validation result dictionary
        """
        # Run base functional validation
        base_result = super().validate(component, circuit_type)
        
        # Add port declaration check
        port_passed, port_report = self.port_validator.validate(component, problem_spec)
        
        # Add silicon efficiency check
        silicon_passed, silicon_report = self.silicon_checker.check(component)
        
        # Combine results
        enhanced_result = {
            **base_result,
            "port_declaration": {
                "passed": port_passed,
                "report": port_report
            },
            "silicon_efficiency": {
                "passed": silicon_passed,
                "report": silicon_report
            },
            "enhanced_passed": (
                base_result.get("passed", False) and
                port_passed and
                silicon_passed
            )
        }
        
        return enhanced_result


