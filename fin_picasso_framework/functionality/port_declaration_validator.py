"""
Port Declaration Validator

Verifies that all required external ports are declared and no extra ports are exposed.
Validates port naming matches problem specification.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Set
import gdsfactory as gf
from ..config import REQUIRE_EXACT_PORT_MATCH, ALLOW_EXTRA_PORTS

logger = logging.getLogger(__name__)


class PortDeclarationValidator:
    """Validates port declarations in generated designs."""

    def __init__(self):
        """Initialize port declaration validator."""
        self.require_exact_match = REQUIRE_EXACT_PORT_MATCH
        self.allow_extra_ports = ALLOW_EXTRA_PORTS

    def validate(
        self,
        component: gf.Component,
        problem_spec: Optional[Dict] = None
    ) -> Tuple[bool, Dict]:
        """
        Validate port declarations.

        Args:
            component: GDSFactory component to validate
            problem_spec: Optional problem specification with expected ports

        Returns:
            (is_valid, validation_report)
        """
        declared_ports = get_port_names(component.ports)
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "declared_ports": declared_ports,
            "expected_ports": [],
            "missing_ports": [],
            "extra_ports": [],
        }
        
        # Extract expected ports from problem spec if provided
        if problem_spec:
            expected_ports = self._extract_expected_ports(problem_spec)
            report["expected_ports"] = expected_ports
            
            # Check for missing ports
            missing = set(expected_ports) - set(declared_ports)
            if missing:
                report["missing_ports"] = list(missing)
                report["errors"].append(f"Missing required ports: {', '.join(missing)}")
                report["passed"] = False
            
            # Check for extra ports
            if not self.allow_extra_ports:
                extra = set(declared_ports) - set(expected_ports)
                if extra:
                    report["extra_ports"] = list(extra)
                    report["warnings"].append(f"Extra ports declared: {', '.join(extra)}")
                    if self.require_exact_port_match:
                        report["errors"].append(f"Extra ports not allowed: {', '.join(extra)}")
                        report["passed"] = False
        
        # Check port naming convention
        naming_issues = self._check_port_naming(component)
        if naming_issues:
            report["warnings"].extend(naming_issues)
        
        # Check that ports are properly exposed
        exposure_issues = self._check_port_exposure(component)
        if exposure_issues:
            report["warnings"].extend(exposure_issues)
        
        return report["passed"], report

    def _extract_expected_ports(self, problem_spec: Dict) -> List[str]:
        """
        Extract expected ports from problem specification.

        Args:
            problem_spec: Problem specification dictionary

        Returns:
            List of expected port names
        """
        expected = []
        
        # Look for port mentions in problem text
        if isinstance(problem_spec, dict):
            problem_text = problem_spec.get('text', '') or problem_spec.get('description', '')
        else:
            problem_text = str(problem_spec)
        
        # Extract port patterns: "port o1", "output o2", "input o1", etc.
        port_patterns = [
            r'\b(?:port|output|input)\s+([oO]\d+)',
            r'\b([oO]\d+)\s+(?:port|output|input)',
            r'ports?:\s*([oO]\d+(?:\s*,\s*[oO]\d+)*)',
        ]
        
        for pattern in port_patterns:
            matches = re.findall(pattern, problem_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                # Split comma-separated ports
                ports = [p.strip().lower() for p in match.split(',')]
                expected.extend(ports)
        
        # Remove duplicates and normalize
        expected = list(set([p.lower() for p in expected]))
        
        return expected

    def _check_port_naming(self, component: gf.Component) -> List[str]:
        """Check port naming convention."""
        issues = []
        
        # Check for non-standard port names
        standard_pattern = re.compile(r'^o\d+$')
        for port_name in get_port_names(component.ports):
            if not standard_pattern.match(port_name.lower()):
                issues.append(
                    f"Non-standard port name: '{port_name}'. "
                    "Expected format: o1, o2, o3, etc."
                )
        
        return issues

    def _check_port_exposure(self, component: gf.Component) -> List[str]:
        """Check that ports are properly exposed."""
        issues = []
        
        # Check if component has any ports
        if get_port_count(component.ports) == 0:
            issues.append("No external ports exposed on component")
        
        # Check port orientations (should be cardinal directions)
        for port_name, port in get_port_items(component.ports):
            if hasattr(port, 'orientation'):
                angle = port.orientation % 360
                cardinal_angles = [0, 90, 180, 270]
                if angle not in cardinal_angles:
                    min_diff = min(abs(angle - ca) for ca in cardinal_angles)
                    if min_diff > 5:  # More than 5 degrees off
                        issues.append(
                            f"Port '{port_name}' has non-cardinal orientation: {angle}°"
                        )
        
        return issues

    def validate_from_code(self, code: str, problem_spec: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """
        Validate port declarations from code string.

        Args:
            code: Generated Python code
            problem_spec: Optional problem specification

        Returns:
            (is_valid, validation_report)
        """
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "declared_ports": [],
            "expected_ports": [],
            "missing_ports": [],
            "extra_ports": [],
        }
        
        # Extract port declarations from code
        declared_ports = self._extract_ports_from_code(code)
        report["declared_ports"] = declared_ports
        
        # Extract expected ports if problem spec provided
        if problem_spec:
            expected_ports = self._extract_expected_ports(problem_spec)
            report["expected_ports"] = expected_ports
            
            # Check for missing ports
            missing = set(expected_ports) - set([p.lower() for p in declared_ports])
            if missing:
                report["missing_ports"] = list(missing)
                report["errors"].append(f"Missing required ports: {', '.join(missing)}")
                report["passed"] = False
            
            # Check for extra ports
            if not self.allow_extra_ports:
                extra = set([p.lower() for p in declared_ports]) - set(expected_ports)
                if extra:
                    report["extra_ports"] = list(extra)
                    report["warnings"].append(f"Extra ports declared: {', '.join(extra)}")
                    if self.require_exact_port_match:
                        report["errors"].append(f"Extra ports not allowed: {', '.join(extra)}")
                        report["passed"] = False
        
        return report["passed"], report

    def _extract_ports_from_code(self, code: str) -> List[str]:
        """
        Extract port declarations from code.

        Args:
            code: Python code string

        Returns:
            List of declared port names
        """
        ports = []
        
        # Pattern: r.add_port('o1', ...) or component.add_port('o1', ...)
        port_pattern = r'\.add_port\(["\']([^"\']+)["\']'
        matches = re.findall(port_pattern, code)
        ports.extend(matches)
        
        return ports

