"""
PICasso Pilot Validator (SPICEPilot-inspired)

Pre-execution code validation to prevent recurring errors.
Learns from error patterns and creates persistent rules.
"""

import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class PilotValidator:
    """Pre-execution validator that learns from errors."""

    # Error thresholds
    LEARNING_THRESHOLD = 3  # Create rule after 3 occurrences
    MIN_SPACING_UM = 100.0   # Minimum component spacing (increased for complex circuits)
    MIN_SPACING_VERTICAL_UM = 60.0  # Minimum vertical spacing for stacked components (8-QAM)
    MIN_BEND_RADIUS_UM = 15.0  # Minimum bend radius

    def __init__(self, rules_path: Optional[str] = None):
        """
        Initialize pilot validator.

        Args:
            rules_path: Path to persistent rules database (pilot_rules.json)
        """
        self.rules_path = rules_path or str(
            Path(__file__).parent.parent / "pilot_rules.json"
        )
        self.error_history = defaultdict(int)
        self.learned_rules = self._load_rules()

    def _load_rules(self) -> Dict:
        """Load persistent rules from JSON."""
        default_rules = {
            "mirror_error_count": 0,
            "spacing_error_count": 0,
            "port_error_count": 0,
            "routing_error_count": 0,
            "routing_method_error_count": 0,
            "orientation_error_count": 0,
            "custom_patterns": []
        }
        
        if Path(self.rules_path).exists():
            with open(self.rules_path, 'r') as f:
                loaded_rules = json.load(f)
                # Ensure all required keys exist (for backward compatibility)
                for key, default_value in default_rules.items():
                    if key not in loaded_rules:
                        loaded_rules[key] = default_value
                return loaded_rules
        return default_rules

    def _save_rules(self):
        """Save learned rules to JSON."""
        with open(self.rules_path, 'w') as f:
            json.dump(self.learned_rules, f, indent=2)

    def validate(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Pre-execution validation of generated code.

        Args:
            code: Generated Python code

        Returns:
            (is_valid, error_message)
        """
        # CRITICAL: Check for incomplete method calls BEFORE AST parsing
        # This must run first because ast.parse() will fail with generic SyntaxError
        incomplete_check = self._check_incomplete_method_calls(code)
        if not incomplete_check[0]:
            # Return specific error message for incomplete method calls
            return False, incomplete_check[2]  # Return the error message
        
        # Parse AST (only if no incomplete method calls found)
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Check all other patterns
        checks = [
            self._check_mirror_on_cell(tree),
            self._check_nonexistent_components(code, tree),  # NEW: Check for non-existent components
            self._check_spacing_violations(code),
            self._check_port_errors(code),
            self._check_routing_errors(code),
            self._check_routing_method(code),
            self._check_combiner_orientation(code),
        ]

        for passed, error_type, message in checks:
            if not passed:
                # Record error
                self.error_history[error_type] += 1
                self.learned_rules[f"{error_type}_count"] += 1

                # Learn if threshold reached
                if self.learned_rules[f"{error_type}_count"] >= self.LEARNING_THRESHOLD:
                    self._create_rule(error_type)

                self._save_rules()
                return False, message

        return True, None

    def _check_incomplete_method_calls(self, code: str) -> Tuple[bool, str, str]:
        """
        Check for incomplete method calls like obj.0), obj.1), etc.
        
        This is a common LLM error where it generates incomplete method calls.
        Example errors:
        - mmi2.0)  # Missing method name
        - component.1)  # Missing method name
        
        These should be complete method calls like:
        - mmi2.move((250, 0))
        - component.mirror()
        """
        # Pattern: word. followed by digit and closing paren (obj.0), obj.1), etc.)
        incomplete_pattern = re.compile(r'\b\w+\.\d+\)')
        matches = incomplete_pattern.findall(code)
        
        if matches:
            # Find the line number for better feedback
            lines = code.split('\n')
            error_lines = []
            for i, line in enumerate(lines, 1):
                if incomplete_pattern.search(line):
                    error_lines.append(f"Line {i}: {line.strip()}")
            
            error_msg = (
                f"INCOMPLETE_METHOD_CALL: Found incomplete method calls like '{matches[0]}'. "
                f"This is missing the method name. "
                f"Example errors: {', '.join(matches[:3])}. "
                f"Fix: Complete the method call (e.g., 'mmi2.move((250, 0))' not 'mmi2.0)')."
            )
            if error_lines:
                error_msg += f"\nFound at: {error_lines[0]}"
            
            return False, "incomplete_method_call", error_msg
        
        return True, "", ""

    def _check_mirror_on_cell(self, tree: ast.AST) -> Tuple[bool, str, str]:
        """
        Detect pattern: gf.components.xxx().mirror()

        Correct usage:
            ref = c.add_ref(gf.components.mmi1x2())
            ref.mirror()

        Incorrect usage:
            gf.components.mmi1x2().mirror()  # ❌
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if calling .mirror()
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'mirror':
                    # Check if called on gf.components.xxx()
                    if self._is_component_call(node.func.value):
                        return (
                            False,
                            "mirror_error",
                            "MIRROR_ERROR: .mirror() called on Cell instead of ComponentReference. "
                            "Use: ref = c.add_ref(component); ref.mirror()"
                        )
        return True, "", ""

    def _is_component_call(self, node: ast.AST) -> bool:
        """Check if node is gf.components.xxx() call."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # Check for gf.components.xxx pattern
                if isinstance(node.func.value, ast.Attribute):
                    if (isinstance(node.func.value.value, ast.Name) and
                        node.func.value.value.id == 'gf' and
                        node.func.value.attr == 'components'):
                        return True
        return False

    def _check_nonexistent_components(self, code: str, tree: ast.AST) -> Tuple[bool, str, str]:
        """
        Check for non-existent component names (e.g., mmi2x1).
        
        Known non-existent components that LLM might try to use:
        - mmi2x1 (doesn't exist, use mmi1x2 and mirror it)
        """
        # List of known non-existent components
        nonexistent_components = [
            'mmi2x1',  # Common mistake - doesn't exist
        ]
        
        # Check for component calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if self._is_component_call(node):
                    # Extract component name
                    if isinstance(node.func, ast.Attribute):
                        comp_name = node.func.attr
                        
                        # Check if it's a known non-existent component
                        if comp_name in nonexistent_components:
                            return (
                                False,
                                "component_error",
                                f"COMPONENT_ERROR: '{comp_name}' does NOT exist in gf.components. "
                                f"Use 'mmi1x2()' and call .mirror() on the ComponentReference instead. "
                                f"Example: ref = r.add_ref(gf.components.mmi1x2()); ref.mirror()"
                            )
        
        # Also check in code string for common patterns
        for comp_name in nonexistent_components:
            pattern = rf'gf\.components\.{comp_name}\('
            if re.search(pattern, code):
                return (
                    False,
                    "component_error",
                    f"COMPONENT_ERROR: '{comp_name}' does NOT exist in gf.components. "
                    f"Use 'mmi1x2()' and call .mirror() on the ComponentReference instead. "
                    f"Example: ref = r.add_ref(gf.components.mmi1x2()); ref.mirror()"
                )
        
        return True, "", ""

    def _check_spacing_violations(self, code: str) -> Tuple[bool, str, str]:
        """
        Check component spacing using .move() coordinates.

        Parse patterns like:
            mmi1_ref.move((100, 0))
            mmi2_ref.move((150, 0))

        And verify pairwise distances ≥ MIN_SPACING_UM.
        """
        # Extract move() calls with coordinates
        move_pattern = r'(\w+)\.move\(\(([^)]+)\)\)'
        moves = re.findall(move_pattern, code)

        if len(moves) < 2:
            return True, "", ""  # Not enough components to check spacing

        # Parse coordinates
        coords = {}
        for ref_name, coord_str in moves:
            try:
                # Parse (x, y) tuple
                parts = coord_str.split(',')
                if len(parts) >= 2:
                    x = float(parts[0].strip())
                    y = float(parts[1].strip())
                    coords[ref_name] = (x, y)
            except ValueError:
                continue

        # Check pairwise distances
        refs = list(coords.keys())
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                ref1, ref2 = refs[i], refs[j]
                x1, y1 = coords[ref1]
                x2, y2 = coords[ref2]

                distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5

                if distance < self.MIN_SPACING_UM:
                    return (
                        False,
                        "spacing_error",
                        f"SPACING_VIOLATION: Components '{ref1}' and '{ref2}' are {distance:.1f}µm apart "
                        f"(minimum: {self.MIN_SPACING_UM}µm). Increase spacing to avoid collisions."
                    )

        return True, "", ""

    def _check_port_errors(self, code: str) -> Tuple[bool, str, str]:
        """
        Check for common port name errors.

        Common mistakes:
            - .connect('e1', ...) when port is 'o1'
            - .connect('out1', ...) when port is 'o1'
        """
        # Common invalid port names
        invalid_ports = [
            (r'\.connect\(["\']e1["\']', 'e1', 'o1 or o2'),
            (r'\.connect\(["\']out1["\']', 'out1', 'o1 or o2'),
            (r'\.connect\(["\']in1["\']', 'in1', 'o1 or o2'),
        ]

        for pattern, invalid, correct in invalid_ports:
            if re.search(pattern, code):
                return (
                    False,
                    "port_error",
                    f"PORT_ERROR: Port name '{invalid}' is likely incorrect. "
                    f"GDSFactory MMI ports are typically named '{correct}'. "
                    f"Check component API with component.ports for correct names."
                )

        return True, "", ""

    def _check_routing_errors(self, code: str) -> Tuple[bool, str, str]:
        """
        Check routing parameters (bend radius, etc.).

        Parse route_bundle() or route_single() with radius parameter.
        Also check for API parameter mismatches (e.g., route_single with separation).
        """
        # Check for route_single() with separation parameter (WRONG - only route_bundle accepts separation)
        route_single_with_separation = re.search(
            r'route_single\([^)]*separation\s*=',
            code
        )
        if route_single_with_separation:
            return (
                False,
                "api_parameter_error",
                "API_PARAMETER_ERROR: route_single() does NOT accept 'separation' parameter. "
                "Only route_bundle() accepts 'separation'. "
                "Use route_single() for single connections, or route_bundle() for multiple connections with separation."
            )
        
        # Extract radius from routing calls
        radius_pattern = r'route(?:_bundle|_single)\([^)]*radius\s*=\s*([0-9.]+)'
        matches = re.findall(radius_pattern, code)

        for radius_str in matches:
            try:
                radius = float(radius_str)
                if radius < self.MIN_BEND_RADIUS_UM:
                    return (
                        False,
                        "routing_error",
                        f"ROUTING_ERROR: Bend radius {radius}µm is too small "
                        f"(minimum: {self.MIN_BEND_RADIUS_UM}µm). Increase to avoid high loss."
                    )
            except ValueError:
                continue

        return True, "", ""

    def _check_routing_method(self, code: str) -> Tuple[bool, str, str]:
        """
        Detect route_single when route_bundle should be used.
        
        For circuits with many connections (>3), route_bundle is preferred
        for cleaner routing and better layout quality.
        """
        # Count route_single usage
        route_single_count = code.count('route_single')
        
        if route_single_count > 3:
            return (
                False,
                "routing_method_error",
                f"ROUTING_METHOD_ERROR: Found {route_single_count} route_single calls. "
                f"Use route_bundle instead for circuits with multiple connections. "
                f"route_bundle provides cleaner routing and automatic separation."
            )
        
        return True, "", ""

    def _check_combiner_orientation(self, code: str) -> Tuple[bool, str, str]:
        """
        Ensure MMI combiners are mirrored after add_ref.
        
        Common pattern for combiners:
            combiner = r.add_ref(gf.components.mmi1x2())
            combiner.mirror()  # Required for proper port orientation
        """
        # Look for combiner variable names (case-insensitive)
        combiner_pattern = r'(combiner\w*)\s*=\s*\w+\.add_ref\(gf\.components\.mmi'
        matches = re.findall(combiner_pattern, code, re.IGNORECASE)
        
        for combiner_name in matches:
            # Check if this combiner has .mirror() called on it
            mirror_pattern = rf'{combiner_name}\s*\.mirror\(\)'
            if not re.search(mirror_pattern, code):
                return (
                    False,
                    "orientation_error",
                    f"COMBINER_ORIENTATION_ERROR: MMI combiner '{combiner_name}' must call .mirror() "
                    f"after add_ref() for proper port alignment. Add: {combiner_name}.mirror()"
                )
        
        return True, "", ""

    def _create_rule(self, error_type: str):
        """Create persistent rule after learning threshold reached."""
        if error_type not in [p["type"] for p in self.learned_rules["custom_patterns"]]:
            self.learned_rules["custom_patterns"].append({
                "type": error_type,
                "occurrences": self.learned_rules[f"{error_type}_count"],
                "action": "block",
                "created_at": str(Path(self.rules_path).stat().st_mtime if Path(self.rules_path).exists() else 0)
            })

    def get_feedback(self, error_message: str) -> str:
        """
        Generate LLM feedback for pilot errors.

        Args:
            error_message: Error message from validate()

        Returns:
            Actionable feedback for LLM retry
        """
        # Add context to error message
        if "MIRROR_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "Example fix:\n"
                "```python\n"
                "# Instead of:\n"
                "# gf.components.mmi1x2().mirror()  # ❌\n\n"
                "# Use:\n"
                "ref = c.add_ref(gf.components.mmi1x2())\n"
                "ref.mirror()  # ✅\n"
                "```"
            )
        elif "SPACING_VIOLATION" in error_message:
            return (
                f"{error_message}\n\n"
                "Fix: Increase spacing in .move() coordinates by at least 100µm for complex circuits."
            )
        elif "PORT_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "Fix: Use component.ports to check available port names before connecting."
            )
        elif "ROUTING_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "Fix: Increase bend radius in route() call to ≥15µm."
            )
        elif "API_PARAMETER_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "Example fix:\n"
                "```python\n"
                "# WRONG:\n"
                "gf.routing.route_single(r, port1, port2, cross_section='strip', separation=15)  # ❌\n\n"
                "# CORRECT (single connection):\n"
                "gf.routing.route_single(r, port1, port2, cross_section='strip', radius=15)  # ✅\n\n"
                "# CORRECT (multiple connections with separation):\n"
                "gf.routing.route_bundle(r, [port1, port2], [port3, port4], cross_section='strip', radius=15, separation=15)  # ✅\n"
                "```"
            )
        elif "INCOMPLETE_METHOD_CALL" in error_message:
            return (
                f"{error_message}\n\n"
                "CRITICAL: You generated an incomplete method call!\n\n"
                "Example fix:\n"
                "```python\n"
                "# ❌ WRONG (incomplete method call):\n"
                "mmi2 = r.add_ref(gf.components.mmi1x2())\n"
                "mmi2.0)  # Missing method name!\n\n"
                "# ✅ CORRECT (complete method call):\n"
                "mmi2 = r.add_ref(gf.components.mmi1x2())\n"
                "mmi2.move((250, 0))  # Complete method call\n\n"
                "# Or if you need to mirror:\n"
                "mmi2 = r.add_ref(gf.components.mmi1x2())\n"
                "mmi2.mirror()  # Complete method call\n"
                "```\n\n"
                "💡 TIP: Always include the method name after the dot (e.g., .move(), .mirror(), etc.)"
            )
        elif "ROUTING_METHOD_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "Example fix:\n"
                "```python\n"
                "# Instead of multiple route_single calls:\n"
                "# route_single(r, port1, port2)\n"
                "# route_single(r, port3, port4)\n\n"
                "# Use route_bundle:\n"
                "route_bundle(r, [port1, port3], [port2, port4], separation=20)\n"
                "```"
            )
        elif "COMBINER_ORIENTATION_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "Example fix:\n"
                "```python\n"
                "combiner = r.add_ref(gf.components.mmi1x2())\n"
                "combiner.mirror()  # Add this line\n"
                "combiner.move((x, y))\n"
                "```"
            )
        elif "COMPONENT_ERROR" in error_message:
            return (
                f"{error_message}\n\n"
                "CRITICAL: This component does not exist in GDSFactory. "
                "Check the component reference in the prompt for available components. "
                "For 2x1 combiners, use mmi1x2() and mirror it."
            )
        else:
            return error_message

    def get_statistics(self) -> Dict:
        """Get error statistics for debugging."""
        return {
            "error_history": dict(self.error_history),
            "learned_rules": self.learned_rules,
            "total_errors_caught": sum(self.error_history.values()),
            "rules_created": len(self.learned_rules["custom_patterns"])
        }
