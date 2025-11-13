"""
Error Pattern Extractor

Extracts detailed error information from validation failures and categorizes them.
Generates structured error templates with suggested fixes and prevention rules.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification."""
    PORT_MISMATCH = "port_mismatch"
    SAX_COMPONENT_NOT_FOUND = "sax_component_not_found"
    PACKAGE_ERROR = "package_error"
    ROUTING_ERROR = "routing_error"
    SPACING_VIOLATION = "spacing_violation"
    MIRROR_ERROR = "mirror_error"
    SYNTAX_ERROR = "syntax_error"
    MISSING_ROUTE = "missing_route"
    INCOMPLETE_ROUTING = "incomplete_routing"
    WRONG_API = "wrong_api"
    DRC_VIOLATION = "drc_violation"
    FUNCTIONAL_FAILURE = "functional_failure"
    UNKNOWN = "unknown"


class ErrorExtractor:
    """
    Extracts and categorizes errors from validation failures.
    
    Analyzes error messages, code snippets, and validation reports to:
    1. Identify error type and category
    2. Extract specific error details
    3. Generate structured error templates
    4. Suggest fixes with examples
    5. Create prevention rules for pilot validator
    """
    
    def __init__(self):
        """Initialize error extractor."""
        self.error_patterns = self._initialize_patterns()
        self.error_history = []
    
    def _initialize_patterns(self) -> Dict[ErrorCategory, List[re.Pattern]]:
        """Initialize regex patterns for error detection."""
        return {
            ErrorCategory.PORT_MISMATCH: [
                re.compile(r"port.*not found", re.IGNORECASE),
                re.compile(r"port.*does not exist", re.IGNORECASE),
                re.compile(r"ports\[['\"](\w+)['\"]\]", re.IGNORECASE),
                re.compile(r"AttributeError.*ports", re.IGNORECASE),
            ],
            ErrorCategory.SAX_COMPONENT_NOT_FOUND: [
                re.compile(r"component.*not found", re.IGNORECASE),
                re.compile(r"SAX.*component", re.IGNORECASE),
                re.compile(r"no model.*component", re.IGNORECASE),
            ],
            ErrorCategory.PACKAGE_ERROR: [
                re.compile(r"ModuleNotFoundError", re.IGNORECASE),
                re.compile(r"ImportError", re.IGNORECASE),
                re.compile(r"has no attribute", re.IGNORECASE),
                re.compile(r"object has no attribute", re.IGNORECASE),
            ],
            ErrorCategory.ROUTING_ERROR: [
                re.compile(r"routing.*error", re.IGNORECASE),
                re.compile(r"route.*failed", re.IGNORECASE),
                re.compile(r"cannot route", re.IGNORECASE),
                re.compile(r"routing.*collision", re.IGNORECASE),
            ],
            ErrorCategory.SPACING_VIOLATION: [
                re.compile(r"spacing.*violation", re.IGNORECASE),
                re.compile(r"too close", re.IGNORECASE),
                re.compile(r"overlap", re.IGNORECASE),
                re.compile(r"minimum.*spacing", re.IGNORECASE),
            ],
            ErrorCategory.MIRROR_ERROR: [
                re.compile(r"mirror.*error", re.IGNORECASE),
                re.compile(r"mirror\(\)", re.IGNORECASE),
                re.compile(r"reflect\(\)", re.IGNORECASE),
            ],
            ErrorCategory.SYNTAX_ERROR: [
                re.compile(r"SyntaxError", re.IGNORECASE),
                re.compile(r"invalid character", re.IGNORECASE),
                re.compile(r"invalid syntax", re.IGNORECASE),
                re.compile(r"unterminated", re.IGNORECASE),
                re.compile(r"missing.*\)", re.IGNORECASE),
                re.compile(r"missing.*\}", re.IGNORECASE),
                re.compile(r"unmatched.*\)", re.IGNORECASE),
                re.compile(r"unmatched.*\}", re.IGNORECASE),
                re.compile(r"invalid decimal", re.IGNORECASE),
                re.compile(r"syntax.*error", re.IGNORECASE),
            ],
            ErrorCategory.MISSING_ROUTE: [
                re.compile(r"no.*route", re.IGNORECASE),
                re.compile(r"missing.*route", re.IGNORECASE),
                re.compile(r"not.*routed", re.IGNORECASE),
            ],
            ErrorCategory.INCOMPLETE_ROUTING: [
                re.compile(r"incomplete.*routing", re.IGNORECASE),
                re.compile(r"not.*connected", re.IGNORECASE),
                re.compile(r"unconnected", re.IGNORECASE),
            ],
            ErrorCategory.WRONG_API: [
                re.compile(r"wrong.*method", re.IGNORECASE),
                re.compile(r"add_route", re.IGNORECASE),
                re.compile(r"does not.*take", re.IGNORECASE),
            ],
            ErrorCategory.DRC_VIOLATION: [
                re.compile(r"DRC.*violation", re.IGNORECASE),
                re.compile(r"design rule", re.IGNORECASE),
                re.compile(r"violations", re.IGNORECASE),
            ],
            ErrorCategory.FUNCTIONAL_FAILURE: [
                re.compile(r"functional.*fail", re.IGNORECASE),
                re.compile(r"test.*fail", re.IGNORECASE),
                re.compile(r"spec.*not.*met", re.IGNORECASE),
            ],
        }
    
    def extract_error(
        self,
        error_message: str,
        code: Optional[str] = None,
        validation_report: Optional[Dict] = None,
        failed_stage: Optional[str] = None
    ) -> Dict:
        """
        Extract structured error information.
        
        Args:
            error_message: Error message string
            code: Code that caused the error (optional)
            validation_report: Validation report dictionary (optional)
            failed_stage: Stage where error occurred (optional)
            
        Returns:
            Dictionary with structured error information:
            {
                'category': ErrorCategory,
                'error_type': str,
                'error_message': str,
                'code_snippet': str,
                'suggested_fix': str,
                'fix_example': str,
                'prevention_rule': str,
                'severity': str,
                'failed_stage': str
            }
        """
        # Categorize error
        category = self._categorize_error(error_message)
        
        # Extract code snippet if available
        code_snippet = self._extract_code_snippet(error_message, code)
        
        # Generate fix suggestions
        fix_info = self._generate_fix_suggestions(category, error_message, code_snippet)
        
        # Create prevention rule
        prevention_rule = self._create_prevention_rule(category, error_message)
        
        # Determine severity
        severity = self._determine_severity(category, error_message)
        
        error_info = {
            'category': category.value,
            'error_type': self._get_error_type_name(category),
            'error_message': error_message,
            'code_snippet': code_snippet,
            'suggested_fix': fix_info['suggestion'],
            'fix_example': fix_info['example'],
            'prevention_rule': prevention_rule,
            'severity': severity,
            'failed_stage': failed_stage or 'unknown',
            'validation_report': validation_report
        }
        
        # Store in history
        self.error_history.append(error_info)
        
        return error_info
    
    def _categorize_error(self, error_message: str) -> ErrorCategory:
        """Categorize error based on message patterns."""
        error_lower = error_message.lower()
        
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if pattern.search(error_message):
                    return category
        
        return ErrorCategory.UNKNOWN
    
    def _extract_code_snippet(self, error_message: str, code: Optional[str]) -> str:
        """Extract relevant code snippet from error or code."""
        if not code:
            return ""
        
        # Try to extract line number from error
        line_match = re.search(r'line (\d+)', error_message)
        if line_match:
            try:
                line_num = int(line_match.group(1))
                lines = code.split('\n')
                if 0 < line_num <= len(lines):
                    # Return context around error line
                    start = max(0, line_num - 3)
                    end = min(len(lines), line_num + 2)
                    snippet = '\n'.join(lines[start:end])
                    return f"# Line {line_num}:\n{snippet}"
            except (ValueError, IndexError):
                pass
        
        # If no line number, try to find relevant patterns
        if 'port' in error_message.lower():
            port_match = re.search(r"ports\[['\"](\w+)['\"]\]", error_message)
            if port_match:
                port_name = port_match.group(1)
                # Find lines with this port
                for line in code.split('\n'):
                    if port_name in line and 'ports' in line:
                        return line
        
        return ""
    
    def _generate_fix_suggestions(
        self,
        category: ErrorCategory,
        error_message: str,
        code_snippet: str
    ) -> Dict[str, str]:
        """Generate fix suggestions based on error category."""
        suggestions = {
            ErrorCategory.PORT_MISMATCH: {
                'suggestion': (
                    "Check component port names. Common ports are 'o1', 'o2', 'o3' for outputs, "
                    "and 'o1' for inputs. Use component.ports to verify available ports."
                ),
                'example': (
                    "# WRONG:\n"
                    "component.ports['p1']  # Port 'p1' doesn't exist\n\n"
                    "# CORRECT:\n"
                    "component.ports['o1']  # Use correct port name\n"
                    "# Or check available ports:\n"
                    "print(component.ports.keys())  # See all available ports"
                )
            },
            ErrorCategory.SAX_COMPONENT_NOT_FOUND: {
                'suggestion': (
                    "Component not found in SAX models. Either use a supported component "
                    "or create a SAX model for this component."
                ),
                'example': (
                    "# Use standard GDSFactory components that have SAX models:\n"
                    "gf.components.mmi1x2()  # ✅ Has SAX model\n"
                    "gf.components.mzis.mzm()  # ✅ Has SAX model\n"
                    "# Avoid custom components without SAX models"
                )
            },
            ErrorCategory.PACKAGE_ERROR: {
                'suggestion': (
                    "Import error or attribute error. Check that you're using correct "
                    "GDSFactory API and component names."
                ),
                'example': (
                    "# WRONG:\n"
                    "gf.components.mzm_bit1()  # Doesn't exist\n\n"
                    "# CORRECT:\n"
                    "gf.components.mzis.mzm()  # Correct component path"
                )
            },
            ErrorCategory.ROUTING_ERROR: {
                'suggestion': (
                    "Routing failed. Check port positions, ensure ports are aligned, "
                    "and use appropriate bend radius (>= 15µm)."
                ),
                'example': (
                    "# Ensure proper routing:\n"
                    "gf.routing.route_single(\n"
                    "    r,\n"
                    "    port1=component1.ports['o2'],\n"
                    "    port2=component2.ports['o1'],\n"
                    "    cross_section='strip',\n"
                    "    radius=15,  # Minimum 15µm\n"
                    ")"
                )
            },
            ErrorCategory.SPACING_VIOLATION: {
                'suggestion': (
                    "Components are too close together. Increase spacing to at least 20µm "
                    "(100µm for complex circuits)."
                ),
                'example': (
                    "# WRONG:\n"
                    "component1.move((0, 0))\n"
                    "component2.move((10, 0))  # Too close!\n\n"
                    "# CORRECT:\n"
                    "component1.move((0, 0))\n"
                    "component2.move((100, 0))  # Proper spacing"
                )
            },
            ErrorCategory.MIRROR_ERROR: {
                'suggestion': (
                    "Call mirror() on ComponentReference (after add_ref), not on Component."
                ),
                'example': (
                    "# WRONG:\n"
                    "gf.components.mmi1x2().mirror()  # ❌ Cell doesn't have mirror()\n\n"
                    "# CORRECT:\n"
                    "combiner = r.add_ref(gf.components.mmi1x2())\n"
                    "combiner.mirror()  # ✅ ComponentReference has mirror()"
                )
            },
            ErrorCategory.SYNTAX_ERROR: {
                'suggestion': (
                    "Syntax error detected. Check for Unicode characters, invalid decimal "
                    "literals, or missing colons/indentation."
                ),
                'example': (
                    "# WRONG:\n"
                    "length = 10µm  # Unicode character\n"
                    "value = 10.0.5  # Invalid decimal\n\n"
                    "# CORRECT:\n"
                    "length = 10.0  # Use ASCII only\n"
                    "value = 10.5  # Valid float"
                )
            },
            ErrorCategory.MISSING_ROUTE: {
                'suggestion': (
                    "Components are placed but not routed. Add route_single() or route_bundle() "
                    "calls to create physical waveguides."
                ),
                'example': (
                    "# WRONG:\n"
                    "component1.move((0, 0))\n"
                    "component2.move((100, 0))\n"
                    "# No routing! ❌\n\n"
                    "# CORRECT:\n"
                    "component1.move((0, 0))\n"
                    "component2.move((100, 0))\n"
                    "gf.routing.route_single(r, component1.ports['o2'], component2.ports['o1'], cross_section='strip', radius=15)  # ✅"
                )
            },
            ErrorCategory.INCOMPLETE_ROUTING: {
                'suggestion': (
                    "Not all connections are routed. Ensure every component port that should "
                    "be connected has a corresponding route_single() call."
                ),
                'example': (
                    "# Check all connections:\n"
                    "# Splitter has 3 ports: o1 (input), o2, o3 (outputs)\n"
                    "# Both outputs must be routed:\n"
                    "gf.routing.route_single(r, splitter.ports['o2'], mzm1.ports['o1'], ...)\n"
                    "gf.routing.route_single(r, splitter.ports['o3'], mzm2.ports['o1'], ...)  # Don't forget this!"
                )
            },
            ErrorCategory.WRONG_API: {
                'suggestion': (
                    "Using wrong API method. Use gf.routing.route_single() or route_bundle(), "
                    "not add_route() or other non-existent methods."
                ),
                'example': (
                    "# WRONG:\n"
                    "r.add_route(...)  # Doesn't exist\n\n"
                    "# CORRECT:\n"
                    "gf.routing.route_single(r, port1, port2, cross_section='strip', radius=15)"
                )
            },
            ErrorCategory.DRC_VIOLATION: {
                'suggestion': (
                    "Design rule violations detected. Increase spacing, use larger bend radius, "
                    "and ensure proper clearance between features."
                ),
                'example': (
                    "# Fix DRC violations:\n"
                    "# 1. Increase spacing: 20µm minimum\n"
                    "# 2. Use bend radius >= 15µm\n"
                    "# 3. Ensure route separation >= 15µm\n"
                    "gf.routing.route_bundle(r, ports1, ports2, separation=20, radius=15)"
                )
            },
            ErrorCategory.FUNCTIONAL_FAILURE: {
                'suggestion': (
                    "Circuit does not meet functional specifications. Check component parameters, "
                    "phase relationships, and circuit topology."
                ),
                'example': (
                    "# For 8-QAM: Ensure all 3 MZMs are properly connected\n"
                    "# For MZM: Ensure phase shifter has correct length\n"
                    "# Check that circuit topology matches specification"
                )
            },
        }
        
        default = {
            'suggestion': "Review error message and fix accordingly.",
            'example': code_snippet or "See error message for details."
        }
        
        return suggestions.get(category, default)
    
    def _create_prevention_rule(
        self,
        category: ErrorCategory,
        error_message: str
    ) -> str:
        """Create prevention rule for pilot validator."""
        rules = {
            ErrorCategory.PORT_MISMATCH: (
                "PILOT_RULE: Verify port names exist before using. "
                "Common ports: 'o1', 'o2', 'o3' for outputs."
            ),
            ErrorCategory.SAX_COMPONENT_NOT_FOUND: (
                "PILOT_RULE: Use only GDSFactory components with SAX models. "
                "Check component availability before instantiation."
            ),
            ErrorCategory.PACKAGE_ERROR: (
                "PILOT_RULE: Verify component paths and API methods exist. "
                "Use correct GDSFactory component hierarchy."
            ),
            ErrorCategory.ROUTING_ERROR: (
                "PILOT_RULE: Ensure ports are aligned and use radius >= 15µm for routing."
            ),
            ErrorCategory.SPACING_VIOLATION: (
                "PILOT_RULE: Minimum spacing 20µm (100µm for complex circuits). "
                "Check all .move() coordinates."
            ),
            ErrorCategory.MIRROR_ERROR: (
                "PILOT_RULE: Call mirror() only on ComponentReference (after add_ref), "
                "never on Component directly."
            ),
            ErrorCategory.SYNTAX_ERROR: (
                "PILOT_RULE: Use only ASCII characters. No Unicode (µm, ×, Δ). "
                "Use valid Python float literals."
            ),
            ErrorCategory.MISSING_ROUTE: (
                "PILOT_RULE: Every component connection must have a route_single() or "
                "route_bundle() call. Components placed but not routed will fail."
            ),
            ErrorCategory.INCOMPLETE_ROUTING: (
                "PILOT_RULE: All component ports that should be connected must have "
                "corresponding routing calls. Check for missing routes."
            ),
            ErrorCategory.WRONG_API: (
                "PILOT_RULE: Use gf.routing.route_single() or route_bundle() only. "
                "No other routing methods exist."
            ),
            ErrorCategory.DRC_VIOLATION: (
                "PILOT_RULE: Spacing >= 20µm, bend radius >= 15µm, route separation >= 15µm."
            ),
            ErrorCategory.FUNCTIONAL_FAILURE: (
                "PILOT_RULE: Verify circuit topology matches specification. "
                "Check component parameters and connections."
            ),
        }
        
        return rules.get(category, "PILOT_RULE: Review error and add appropriate check.")
    
    def _determine_severity(self, category: ErrorCategory, error_message: str) -> str:
        """Determine error severity."""
        critical = [
            ErrorCategory.SYNTAX_ERROR,
            ErrorCategory.PACKAGE_ERROR,
            ErrorCategory.MISSING_ROUTE,
        ]
        
        high = [
            ErrorCategory.PORT_MISMATCH,
            ErrorCategory.ROUTING_ERROR,
            ErrorCategory.SPACING_VIOLATION,
            ErrorCategory.DRC_VIOLATION,
        ]
        
        if category in critical:
            return "critical"
        elif category in high:
            return "high"
        else:
            return "medium"
    
    def _get_error_type_name(self, category: ErrorCategory) -> str:
        """Get human-readable error type name."""
        names = {
            ErrorCategory.PORT_MISMATCH: "Port Mismatch Error",
            ErrorCategory.SAX_COMPONENT_NOT_FOUND: "SAX Component Not Found",
            ErrorCategory.PACKAGE_ERROR: "Package/API Error",
            ErrorCategory.ROUTING_ERROR: "Routing Error",
            ErrorCategory.SPACING_VIOLATION: "Spacing Violation",
            ErrorCategory.MIRROR_ERROR: "Mirror Method Error",
            ErrorCategory.SYNTAX_ERROR: "Syntax Error",
            ErrorCategory.MISSING_ROUTE: "Missing Route",
            ErrorCategory.INCOMPLETE_ROUTING: "Incomplete Routing",
            ErrorCategory.WRONG_API: "Wrong API Usage",
            ErrorCategory.DRC_VIOLATION: "DRC Violation",
            ErrorCategory.FUNCTIONAL_FAILURE: "Functional Test Failure",
            ErrorCategory.UNKNOWN: "Unknown Error",
        }
        return names.get(category, "Unknown Error")
    
    def get_error_statistics(self) -> Dict:
        """Get statistics on extracted errors."""
        if not self.error_history:
            return {}
        
        category_counts = {}
        severity_counts = {}
        
        for error in self.error_history:
            cat = error['category']
            sev = error['severity']
            category_counts[cat] = category_counts.get(cat, 0) + 1
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'by_category': category_counts,
            'by_severity': severity_counts,
            'recent_errors': self.error_history[-10:]  # Last 10 errors
        }

