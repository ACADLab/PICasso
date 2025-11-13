"""
Enhanced Feedback Generator

Generates detailed LLM feedback with specific error locations, before/after examples,
common patterns to avoid, and step-by-step fix instructions.
"""

import logging
from typing import Dict, List, Optional, Tuple
from .error_extractor import ErrorExtractor, ErrorCategory

logger = logging.getLogger(__name__)


class FeedbackGenerator:
    """
    Generates detailed, actionable feedback for LLM retries.
    
    Uses ErrorExtractor to analyze errors and creates comprehensive feedback
    with examples, code snippets, and step-by-step instructions.
    """
    
    def __init__(self):
        """Initialize feedback generator."""
        self.error_extractor = ErrorExtractor()
    
    def generate_feedback(
        self,
        error_message: str,
        code: Optional[str] = None,
        validation_report: Optional[Dict] = None,
        failed_stage: Optional[str] = None,
        attempt_number: int = 1,
        problem_description: Optional[str] = None
    ) -> str:
        """
        Generate comprehensive feedback for LLM retry.
        
        Args:
            error_message: Error message from validation
            code: Code that caused the error
            validation_report: Full validation report
            failed_stage: Stage where error occurred
            attempt_number: Current retry attempt number
            problem_description: Original problem description
            
        Returns:
            Formatted feedback string for LLM
        """
        # Extract structured error information
        error_info = self.error_extractor.extract_error(
            error_message=error_message,
            code=code,
            validation_report=validation_report,
            failed_stage=failed_stage
        )
        
        # Build comprehensive feedback
        feedback_parts = []
        
        # Header
        feedback_parts.append("=" * 70)
        feedback_parts.append(f"RETRY ATTEMPT {attempt_number} - VALIDATION FAILED")
        feedback_parts.append("=" * 70)
        feedback_parts.append("")
        
        # Error summary
        feedback_parts.append(f"❌ ERROR TYPE: {error_info['error_type']}")
        feedback_parts.append(f"📍 FAILED STAGE: {error_info['failed_stage'].upper()}")
        feedback_parts.append(f"🔴 SEVERITY: {error_info['severity'].upper()}")
        feedback_parts.append("")
        
        # Error message
        feedback_parts.append("ERROR MESSAGE:")
        feedback_parts.append("-" * 70)
        feedback_parts.append(error_info['error_message'])
        feedback_parts.append("")
        
        # Code snippet (if available)
        if error_info['code_snippet']:
            feedback_parts.append("PROBLEMATIC CODE:")
            feedback_parts.append("-" * 70)
            feedback_parts.append("```python")
            feedback_parts.append(error_info['code_snippet'])
            feedback_parts.append("```")
            feedback_parts.append("")
        
        # Suggested fix
        feedback_parts.append("🔧 SUGGESTED FIX:")
        feedback_parts.append("-" * 70)
        feedback_parts.append(error_info['suggested_fix'])
        feedback_parts.append("")
        
        # Fix example
        if error_info['fix_example']:
            feedback_parts.append("📝 FIX EXAMPLE:")
            feedback_parts.append("-" * 70)
            feedback_parts.append("```python")
            feedback_parts.append(error_info['fix_example'])
            feedback_parts.append("```")
            feedback_parts.append("")
        
        # Stage-specific feedback
        stage_feedback = self._generate_stage_specific_feedback(
            failed_stage or 'unknown',
            validation_report,
            error_info
        )
        if stage_feedback:
            feedback_parts.append(stage_feedback)
            feedback_parts.append("")
        
        # Common patterns to avoid
        patterns = self._get_common_patterns_to_avoid(error_info['category'])
        if patterns:
            feedback_parts.append("⚠️  COMMON PATTERNS TO AVOID:")
            feedback_parts.append("-" * 70)
            for pattern in patterns:
                feedback_parts.append(f"  • {pattern}")
            feedback_parts.append("")
        
        # Step-by-step fix instructions
        steps = self._generate_step_by_step_fix(error_info)
        if steps:
            feedback_parts.append("📋 STEP-BY-STEP FIX INSTRUCTIONS:")
            feedback_parts.append("-" * 70)
            for i, step in enumerate(steps, 1):
                feedback_parts.append(f"  {i}. {step}")
            feedback_parts.append("")
        
        # Prevention rule
        feedback_parts.append("🛡️  PREVENTION RULE:")
        feedback_parts.append("-" * 70)
        feedback_parts.append(error_info['prevention_rule'])
        feedback_parts.append("")
        
        # Original problem (if provided)
        if problem_description:
            feedback_parts.append("=" * 70)
            feedback_parts.append("ORIGINAL PROBLEM:")
            feedback_parts.append("=" * 70)
            feedback_parts.append(problem_description)
            feedback_parts.append("")
        
        # Closing instructions
        feedback_parts.append("=" * 70)
        feedback_parts.append("ACTION REQUIRED:")
        feedback_parts.append("=" * 70)
        feedback_parts.append("Please carefully address ALL the issues mentioned above.")
        feedback_parts.append("Focus on:")
        feedback_parts.append("  • Fixing the specific error type identified")
        feedback_parts.append("  • Following the fix example provided")
        feedback_parts.append("  • Avoiding the common patterns listed")
        feedback_parts.append("  • Following the step-by-step instructions")
        feedback_parts.append("")
        feedback_parts.append("Generate the corrected design below:")
        
        return "\n".join(feedback_parts)
    
    def _generate_stage_specific_feedback(
        self,
        failed_stage: str,
        validation_report: Optional[Dict],
        error_info: Dict
    ) -> str:
        """Generate stage-specific feedback."""
        stage_lower = failed_stage.lower()
        
        if 'pilot' in stage_lower or 'parsing' in stage_lower:
            return self._format_pilot_feedback(validation_report, error_info)
        elif 'pnr' in stage_lower:
            return self._format_pnr_feedback(validation_report, error_info)
        elif 'drc' in stage_lower:
            return self._format_drc_feedback(validation_report, error_info)
        elif 'sax' in stage_lower:
            return self._format_sax_feedback(validation_report, error_info)
        elif 'functional' in stage_lower:
            return self._format_functional_feedback(validation_report, error_info)
        
        return ""
    
    def _format_pilot_feedback(self, report: Optional[Dict], error_info: Dict) -> str:
        """Format pilot validation feedback."""
        parts = []
        parts.append("🔍 PILOT VALIDATION FEEDBACK:")
        parts.append("-" * 70)
        parts.append("The code failed pre-execution validation (before running).")
        parts.append("This means the code has structural issues that would prevent execution.")
        parts.append("")
        parts.append("Key Issues:")
        parts.append(f"  • {error_info['error_type']}")
        if error_info['code_snippet']:
            parts.append("  • See problematic code above")
        return "\n".join(parts)
    
    def _format_pnr_feedback(self, report: Optional[Dict], error_info: Dict) -> str:
        """Format P&R validation feedback."""
        parts = []
        parts.append("🔍 PLACE & ROUTE VALIDATION FEEDBACK:")
        parts.append("-" * 70)
        
        if report:
            if report.get('errors'):
                parts.append("Critical Errors:")
                for error in report['errors']:
                    parts.append(f"  ❌ {error}")
                parts.append("")
            
            if report.get('warnings'):
                parts.append("Warnings:")
                for warning in report['warnings']:
                    parts.append(f"  ⚠️  {warning}")
                parts.append("")
            
            if report.get('metrics'):
                parts.append("Layout Metrics:")
                metrics = report['metrics']
                for key, value in metrics.items():
                    if isinstance(value, float):
                        parts.append(f"  • {key}: {value:.2f}")
                    else:
                        parts.append(f"  • {key}: {value}")
                parts.append("")
        
        parts.append("Key Improvements Needed:")
        parts.append("  1. Increase spacing between components (minimum 20µm, 100µm for complex)")
        parts.append("  2. Use .move() to position components without overlap")
        parts.append("  3. Ensure all components are properly routed with route_single() or route_bundle()")
        parts.append("  4. Use bend radius >= 15µm for routing")
        parts.append("  5. Keep layout compact but not cramped")
        
        return "\n".join(parts)
    
    def _format_drc_feedback(self, report: Optional[Dict], error_info: Dict) -> str:
        """Format DRC validation feedback."""
        parts = []
        parts.append("🔍 DESIGN RULE CHECK (DRC) FEEDBACK:")
        parts.append("-" * 70)
        
        if report:
            violations = report.get('violations', 0)
            if violations > 0:
                parts.append(f"Total DRC Violations: {violations}")
                parts.append("")
                
                if 'violations_by_category' in report:
                    parts.append("Violations by Category:")
                    for category, count in report['violations_by_category'].items():
                        parts.append(f"  • {category}: {count}")
                    parts.append("")
            
            if report.get('errors'):
                parts.append("Errors:")
                for error in report['errors']:
                    parts.append(f"  ❌ {error}")
                parts.append("")
        
        parts.append("DRC Fix Checklist:")
        parts.append("  1. Minimum waveguide spacing: 2-3µm")
        parts.append("  2. Minimum bend radius: 15µm (20µm recommended)")
        parts.append("  3. No overlapping waveguides or components")
        parts.append("  4. Metal traces have proper clearance from waveguides")
        parts.append("  5. All features meet minimum size requirements")
        parts.append("  6. Use route_bundle with adequate separation parameter (>= 15µm)")
        
        return "\n".join(parts)
    
    def _format_sax_feedback(self, report: Optional[Dict], error_info: Dict) -> str:
        """Format SAX validation feedback."""
        parts = []
        parts.append("🔍 SAX VALIDATION FEEDBACK:")
        parts.append("-" * 70)
        
        if report:
            if not report.get('sax_compiled', False):
                parts.append("❌ Circuit failed to compile in SAX simulator")
                parts.append("This usually means:")
                parts.append("  • Missing or incorrect component names")
                parts.append("  • Invalid netlist structure")
                parts.append("  • Unsupported component types")
                parts.append("")
            
            if not report.get('routing_validated', False):
                parts.append("❌ Physical routing validation failed")
                parts.append("This means the circuit may compile but routing is incorrect:")
                parts.append("  • Components placed but not physically connected")
                parts.append("  • Missing waveguide routes between components")
                parts.append("  • Port orientations misaligned")
                parts.append("")
            
            if report.get('errors'):
                parts.append("Specific Errors:")
                for error in report['errors']:
                    parts.append(f"  ❌ {error}")
                parts.append("")
        
        parts.append("SAX/Routing Fix Checklist:")
        parts.append("  1. Use route_single() or route_bundle() to create actual waveguide connections")
        parts.append("  2. Ensure all component optical ports are connected or exposed")
        parts.append("  3. Verify port orientations are cardinal (0°, 90°, 180°, 270°)")
        parts.append("  4. Don't just place components - route between them!")
        parts.append("  5. Use proper GDSFactory component names from the PDK")
        parts.append("  6. Check that all components have SAX models available")
        
        return "\n".join(parts)
    
    def _format_functional_feedback(self, report: Optional[Dict], error_info: Dict) -> str:
        """Format functional validation feedback."""
        parts = []
        parts.append("🔍 FUNCTIONAL VALIDATION FEEDBACK:")
        parts.append("-" * 70)
        
        if report:
            test_name = report.get('test_name', 'unknown')
            expected = report.get('expected', 'N/A')
            actual = report.get('actual', 'N/A')
            
            parts.append(f"Test: {test_name}")
            parts.append(f"Expected: {expected}")
            parts.append(f"Actual: {actual}")
            parts.append("")
            
            if report.get('error'):
                parts.append(f"Error: {report['error']}")
                parts.append("")
        
        parts.append("Functional Fix Suggestions:")
        parts.append("  1. Verify circuit topology matches specification")
        parts.append("  2. Check component parameters (phase relationships, lengths)")
        parts.append("  3. Ensure all required components are present and connected")
        parts.append("  4. Verify phase shifter settings for correct operation")
        parts.append("  5. Check that circuit implements the intended function")
        
        return "\n".join(parts)
    
    def _get_common_patterns_to_avoid(self, category: str) -> List[str]:
        """Get common patterns to avoid for error category."""
        patterns = {
            'port_mismatch': [
                "Using port names like 'p1', 'p2' instead of 'o1', 'o2'",
                "Assuming port names without checking component.ports",
                "Using 'output1', 'input1' instead of standard 'o1', 'o2', 'o3'",
            ],
            'sax_component_not_found': [
                "Using custom components without SAX models",
                "Using incorrect component paths (e.g., mzm_bit1() instead of mzis.mzm())",
                "Assuming all components have SAX models",
            ],
            'package_error': [
                "Using non-existent component methods or attributes",
                "Incorrect import statements",
                "Wrong GDSFactory API usage",
            ],
            'routing_error': [
                "Using radius < 15µm for routing",
                "Routing between misaligned ports",
                "Not checking port positions before routing",
            ],
            'spacing_violation': [
                "Placing components < 20µm apart",
                "Using small spacing values (10µm, 5µm) in .move()",
                "Not considering component bounding boxes",
            ],
            'mirror_error': [
                "Calling mirror() on Component instead of ComponentReference",
                "Using reflect() instead of mirror()",
                "Calling mirror() before add_ref()",
            ],
            'syntax_error': [
                "Using Unicode characters (µm, ×, Δ) in code",
                "Invalid decimal literals (10.0.5)",
                "Missing colons, parentheses, or brackets",
            ],
            'missing_route': [
                "Placing components without routing them",
                "Assuming components are connected just by placement",
                "Not adding route_single() or route_bundle() calls",
            ],
            'incomplete_routing': [
                "Routing only some connections, missing others",
                "Not routing all output ports of splitters",
                "Forgetting to route between intermediate components",
            ],
            'wrong_api': [
                "Using r.add_route() instead of gf.routing.route_single()",
                "Using non-existent routing methods",
                "Incorrect method signatures",
            ],
            'drc_violation': [
                "Spacing violations between waveguides",
                "Bend radius too small",
                "Overlapping features",
            ],
            'functional_failure': [
                "Incorrect circuit topology",
                "Wrong component parameters",
                "Missing required components",
            ],
        }
        
        return patterns.get(category, [])
    
    def _generate_step_by_step_fix(self, error_info: Dict) -> List[str]:
        """Generate step-by-step fix instructions."""
        category = error_info['category']
        
        steps_map = {
            'port_mismatch': [
                "Identify the component with the port error",
                "Check available ports using: component.ports.keys()",
                "Use the correct port name (typically 'o1', 'o2', 'o3')",
                "Update all references to the incorrect port name",
            ],
            'missing_route': [
                "Identify all component pairs that should be connected",
                "For each pair, add a route_single() call",
                "Use correct port names for source and destination",
                "Set appropriate radius (>= 15µm) and cross_section",
                "Verify all routes are added before add_port() calls",
            ],
            'spacing_violation': [
                "Identify components that are too close",
                "Calculate current spacing between components",
                "Increase spacing to at least 20µm (100µm for complex circuits)",
                "Update .move() coordinates accordingly",
                "Re-check spacing after changes",
            ],
            'mirror_error': [
                "Find the component that needs mirroring",
                "Ensure it's added with add_ref() first",
                "Call mirror() on the ComponentReference, not the Component",
                "Place mirror() call after add_ref() but before move()",
            ],
            'syntax_error': [
                "Identify the line with syntax error",
                "Check for Unicode characters and replace with ASCII",
                "Fix invalid decimal literals (remove extra dots)",
                "Verify all brackets, parentheses, and quotes are balanced",
                "Check indentation is consistent",
            ],
            'incomplete_routing': [
                "List all components in the circuit",
                "For each component, identify all ports that should be connected",
                "Check which connections have route_single() calls",
                "Add missing route_single() calls for unconnected ports",
                "Verify all connections are complete",
            ],
        }
        
        default_steps = [
            "Review the error message carefully",
            "Identify the problematic code section",
            "Apply the suggested fix",
            "Test the fix",
        ]
        
        return steps_map.get(category, default_steps)
    
    def generate_retry_prompt(
        self,
        original_prompt: str,
        feedback: str,
        attempt_number: int
    ) -> str:
        """
        Generate complete retry prompt combining original prompt with feedback.
        
        Args:
            original_prompt: Original system/instruction prompt
            feedback: Generated feedback string
            attempt_number: Current retry attempt number
            
        Returns:
            Complete retry prompt for LLM
        """
        retry_prompt = f"""
{original_prompt}

{'='*70}
RETRY ATTEMPT {attempt_number}
{'='*70}

{feedback}

IMPORTANT: Please carefully address ALL the issues mentioned above.
Focus on:
  • Proper component spacing (minimum 20µm, 100µm for complex circuits)
  • Using route_single() or route_bundle() for all connections
  • Clean, organized layout
  • All ports properly connected
  • Following the example structure provided

Generate the corrected design below:
"""
        return retry_prompt


