"""
Framework Pipeline

Main orchestration of the PICasso framework.
Integrates all modules: input quality → prompt → LLM → early validation → code → enhanced validation → optimization
"""

import logging
from typing import Dict, List, Optional, Tuple, Callable
from pathlib import Path
import gdsfactory as gf

from ..config import *
from ..input_quality.input_validator import InputValidator
from ..input_quality.prompt_enhancer import PromptEnhancer
from ..port_matching.port_matcher import PortMatcher
from ..port_matching.component_spec_loader import ComponentSpecLoader
from ..sax_models.sax_model_manager import SAXModelManager
from ..sax_models.sax_knowledge import SAXKnowledgeBase
from ..early_validation.netlist_validator import NetlistValidator
from ..early_validation.netlist_converter import NetlistConverter
from ..pilot.pilot_validator_enhanced import PilotValidatorEnhanced
from ..pilot.restriction_loader import RestrictionLoader
from ..validators.pnr_validator import PNRValidator
from ..validators.drc_validator import DRCValidator
from ..validators.sax_validator import SAXValidator
from ..functionality.port_declaration_validator import PortDeclarationValidator
from ..functionality.silicon_efficiency import SiliconEfficiencyChecker
from ..optimization_integration import OptimizationStage

logger = logging.getLogger(__name__)


class FrameworkPipeline:
    """Main framework pipeline."""

    def __init__(self):
        """Initialize framework pipeline."""
        # Initialize modules
        self.input_validator = InputValidator() if ENABLE_INPUT_VALIDATION else None
        self.prompt_enhancer = PromptEnhancer() if ENABLE_PROMPT_ENHANCEMENT else None
        self.port_matcher = PortMatcher() if ENABLE_PORT_MATCHING else None
        self.component_spec_loader = ComponentSpecLoader() if ENABLE_COMPONENT_SPEC_LOADING else None
        self.sax_model_manager = SAXModelManager() if ENABLE_SAX_MODEL_MANAGEMENT else None
        self.sax_knowledge = SAXKnowledgeBase(self.sax_model_manager) if ENABLE_SAX_KNOWLEDGE_INJECTION else None
        self.netlist_validator = NetlistValidator() if ENABLE_EARLY_NETLIST_VALIDATION else None
        self.netlist_converter = NetlistConverter(self.port_matcher) if ENABLE_NETLIST_CONVERSION else None
        self.pilot_validator = PilotValidatorEnhanced() if ENABLE_PILOT_VALIDATION else None
        self.restriction_loader = RestrictionLoader() if ENABLE_RESTRICTION_LOADING else None
        
        # Validators
        self.pnr_validator = PNRValidator()
        self.drc_validator = DRCValidator()
        self.sax_validator = SAXValidator()
        self.port_validator = PortDeclarationValidator() if ENABLE_PORT_DECLARATION_CHECK else None
        self.silicon_checker = SiliconEfficiencyChecker() if ENABLE_SILICON_EFFICIENCY_CHECK else None
        
        # Optimization
        self.optimizer = OptimizationStage(
            enable_optimization=ENABLE_OPTIMIZATION,
            enable_device_optimization=ENABLE_DEVICE_OPTIMIZATION
        ) if (ENABLE_OPTIMIZATION or ENABLE_DEVICE_OPTIMIZATION) else None

    def process_problem(
        self,
        problem_text: str,
        llm_call: Optional[Callable[[str], str]] = None
    ) -> Dict:
        """
        Process a problem through the full pipeline.

        Args:
            problem_text: Problem description
            llm_call: Optional LLM call function

        Returns:
            Processing result dictionary
        """
        result = {
            "success": False,
            "stages": {},
            "component": None,
            "errors": [],
            "warnings": [],
        }
        
        # Stage 1: Input Quality Check
        if self.input_validator:
            is_valid, issues = self.input_validator.validate(problem_text)
            result["stages"]["input_validation"] = {
                "passed": is_valid,
                "issues": issues
            }
            if not is_valid:
                result["errors"].extend(issues)
                return result
            problem_text = self.input_validator.sanitize(problem_text)
        
        # Stage 2: Prompt Enhancement
        enhanced_prompt = problem_text
        if self.prompt_enhancer:
            # Load component specs
            component_specs = None
            if self.component_spec_loader:
                # Extract component types from problem (simplified)
                component_types = self._extract_component_types(problem_text)
                component_specs = self.component_spec_loader.generate_port_reference(component_types)
            
            # Load SAX knowledge
            sax_knowledge = None
            if self.sax_knowledge:
                component_types = self._extract_component_types(problem_text)
                sax_knowledge = self.sax_knowledge.generate_knowledge_for_llm(component_types)
            
            # Load restrictions
            restrictions = None
            if self.restriction_loader:
                restrictions = self.restriction_loader.generate_restriction_text()
            
            enhanced_prompt = self.prompt_enhancer.format_python_prompt(
                problem_text,
                component_specs,
                sax_knowledge,
                restrictions
            )
            result["stages"]["prompt_enhancement"] = {"passed": True}
        
        # Stage 3: LLM Inference (if provided)
        llm_response = None
        if llm_call:
            try:
                llm_response = llm_call(enhanced_prompt)
                result["stages"]["llm_inference"] = {"passed": True, "response": llm_response}
            except Exception as e:
                result["errors"].append(f"LLM inference error: {e}")
                result["stages"]["llm_inference"] = {"passed": False, "error": str(e)}
                return result
        
        # Stage 4: Early Validation (if netlist)
        if llm_response and self.netlist_validator:
            # Try to parse as netlist
            netlist_data = self.netlist_validator.parse_netlist(llm_response)
            if netlist_data:
                is_valid, issues = self.netlist_validator.validate(netlist_data)
                result["stages"]["early_validation"] = {
                    "passed": is_valid,
                    "issues": issues
                }
                if not is_valid:
                    result["errors"].extend(issues)
                    return result
                
                # Convert netlist to component
                if self.netlist_converter:
                    component, error = self.netlist_converter.convert_to_component(netlist_data)
                    if component:
                        result["component"] = component
                        result["stages"]["netlist_conversion"] = {"passed": True}
                    else:
                        result["errors"].append(f"Netlist conversion error: {error}")
                        return result
        
        # Stage 5: Code Execution (if Python code)
        if llm_response and not result.get("component"):
            # Extract and execute Python code
            code = self._extract_code(llm_response)
            if code:
                # Pilot validation
                if self.pilot_validator:
                    is_valid, error = self.pilot_validator.validate(code)
                    result["stages"]["pilot_validation"] = {
                        "passed": is_valid,
                        "error": error
                    }
                    if not is_valid:
                        result["errors"].append(f"Pilot validation error: {error}")
                        return result
                
                # Execute code
                component, error = self._execute_code(code)
                if component:
                    result["component"] = component
                    result["stages"]["code_execution"] = {"passed": True}
                else:
                    result["errors"].append(f"Code execution error: {error}")
                    return result
        
        # Stage 6: Enhanced Validation
        if result.get("component"):
            component = result["component"]
            
            # P&R Validation
            pnr_passed, pnr_report = self.pnr_validator.validate(component)
            result["stages"]["pnr_validation"] = {
                "passed": pnr_passed,
                "report": pnr_report
            }
            if not pnr_passed:
                result["errors"].extend(pnr_report.get("errors", []))
            
            # DRC Validation
            drc_passed, drc_report = self.drc_validator.validate(component)
            result["stages"]["drc_validation"] = {
                "passed": drc_passed,
                "report": drc_report
            }
            if not drc_passed:
                result["errors"].extend(drc_report.get("errors", []))
            
            # SAX Validation
            sax_passed, sax_report = self.sax_validator.validate(component)
            result["stages"]["sax_validation"] = {
                "passed": sax_passed,
                "report": sax_report
            }
            if not sax_passed:
                result["errors"].extend(sax_report.get("errors", []))
            
            # Port Declaration Validation
            if self.port_validator:
                port_passed, port_report = self.port_validator.validate(component)
                result["stages"]["port_validation"] = {
                    "passed": port_passed,
                    "report": port_report
                }
                if not port_passed:
                    result["errors"].extend(port_report.get("errors", []))
            
            # Silicon Efficiency Check
            if self.silicon_checker:
                silicon_passed, silicon_report = self.silicon_checker.check(component)
                result["stages"]["silicon_efficiency"] = {
                    "passed": silicon_passed,
                    "report": silicon_report
                }
                if not silicon_passed:
                    result["warnings"].extend(silicon_report.get("warnings", []))
            
            # Overall success
            result["success"] = (
                pnr_passed and drc_passed and sax_passed and
                (port_passed if self.port_validator else True) and
                (silicon_passed if self.silicon_checker else True)
            )
        
        # Stage 7: Optimization (if validation passed)
        if result["success"] and self.optimizer and result.get("component"):
            opt_result = self.optimizer.optimize_design(result["component"])
            result["stages"]["optimization"] = {
                "passed": opt_result.get("success", False),
                "result": opt_result
            }
        
        return result

    def _extract_component_types(self, text: str) -> List[str]:
        """Extract component types from problem text."""
        # Simplified extraction - look for common component names
        component_types = []
        common_components = [
            'mmi1x2', 'mmi2x1', 'mmi2x2', 'straight_heater_metal',
            'straight', 'bend_euler', 'coupler', 'mzi'
        ]
        
        text_lower = text.lower()
        for comp in common_components:
            if comp in text_lower:
                component_types.append(comp)
        
        return component_types

    def _extract_code(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        # Try to extract from <result> tag
        if "<result>" in response and "</result>" in response:
            import re
            match = re.search(r'<result>(.*?)</result>', response, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Remove markdown code fences
        code = response.strip()
        if code.startswith('```'):
            code = code.split('```')[1]
            if code.startswith('python'):
                code = code[5:]
            code = code.strip()
        
        return code if 'import gdsfactory' in code or 'import gf' in code else None

    def _execute_code(self, code: str) -> Tuple[Optional[gf.Component], Optional[str]]:
        """Execute code and return component."""
        try:
            ns = {"gf": gf}
            exec(code, ns)
            
            # Find component
            for var_name in ['r', 'c', 'circuit', 'component']:
                if var_name in ns and isinstance(ns[var_name], gf.Component):
                    return ns[var_name], None
            
            return None, "No GDSFactory Component found in code"
        except Exception as e:
            return None, str(e)

