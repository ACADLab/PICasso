"""
Framework Main Entry Point

Provides high-level interface for framework usage.
"""

import logging
from typing import Dict, List, Optional, Callable
from .pipeline import FrameworkPipeline

logger = logging.getLogger(__name__)


class PICassoFramework:
    """Main framework interface."""

    def __init__(self):
        """Initialize framework."""
        self.pipeline = FrameworkPipeline()

    def generate_design(
        self,
        problem_text: str,
        llm_call: Optional[Callable[[str], str]] = None
    ) -> Dict:
        """
        Generate design from problem description.

        Args:
            problem_text: Problem description
            llm_call: Optional LLM call function

        Returns:
            Generation result dictionary
        """
        return self.pipeline.process_problem(problem_text, llm_call)

    def validate_design(self, component) -> Dict:
        """
        Validate an existing design.

        Args:
            component: GDSFactory component

        Returns:
            Validation result dictionary
        """
        result = {
            "success": False,
            "stages": {},
            "errors": [],
            "warnings": [],
        }
        
        # Run validators
        pnr_passed, pnr_report = self.pipeline.pnr_validator.validate(component)
        result["stages"]["pnr"] = {"passed": pnr_passed, "report": pnr_report}
        
        drc_passed, drc_report = self.pipeline.drc_validator.validate(component)
        result["stages"]["drc"] = {"passed": drc_passed, "report": drc_report}
        
        sax_passed, sax_report = self.pipeline.sax_validator.validate(component)
        result["stages"]["sax"] = {"passed": sax_passed, "report": sax_report}
        
        if self.pipeline.port_validator:
            port_passed, port_report = self.pipeline.port_validator.validate(component)
            result["stages"]["port"] = {"passed": port_passed, "report": port_report}
        
        if self.pipeline.silicon_checker:
            silicon_passed, silicon_report = self.pipeline.silicon_checker.check(component)
            result["stages"]["silicon"] = {"passed": silicon_passed, "report": silicon_report}
        
        result["success"] = (
            pnr_passed and drc_passed and sax_passed and
            (port_passed if self.pipeline.port_validator else True) and
            (silicon_passed if self.pipeline.silicon_checker else True)
        )
        
        return result

