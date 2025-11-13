"""
Enhanced Pilot Validator

Extends existing pilot validator with JSON/YAML netlist validation,
port matching checks, and spacing validation from netlist placements.
"""

import logging
import ast
import json
import yaml
import sys
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Import base pilot validator
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir / "hf_inference_workflow"))
try:
    from validators.pilot_validator import PilotValidator
except ImportError:
    # Fallback: use a simplified base class
    import ast
    import re
    import json
    from typing import Dict, List, Tuple, Optional
    from collections import defaultdict
    
    class PilotValidator:
        """Base pilot validator."""
        LEARNING_THRESHOLD = 3
        MIN_SPACING_UM = 100.0
        MIN_SPACING_VERTICAL_UM = 60.0
        MIN_BEND_RADIUS_UM = 15.0
        
        def __init__(self, rules_path: Optional[str] = None):
            self.rules_path = rules_path or str(Path(__file__).parent / "pilot_rules.json")
            self.error_history = defaultdict(int)
            self.learned_rules = self._load_rules()
        
        def _load_rules(self) -> Dict:
            if Path(self.rules_path).exists():
                try:
                    with open(self.rules_path, 'r') as f:
                        return json.load(f)
                except:
                    pass
            return {"custom_patterns": []}
        
        def validate(self, code: str) -> Tuple[bool, Optional[str]]:
            try:
                ast.parse(code)
                return True, None
            except SyntaxError as e:
                return False, f"Syntax error: {e}"

from ..early_validation.netlist_validator import NetlistValidator
from ..port_matching.port_matcher import PortMatcher
from ..config import PILOT_MIN_SPACING_UM, PILOT_MIN_VERTICAL_SPACING_UM

logger = logging.getLogger(__name__)


class PilotValidatorEnhanced(PilotValidator):
    """Enhanced pilot validator with netlist and port matching support."""

    def __init__(self, rules_path: Optional[str] = None):
        """
        Initialize enhanced pilot validator.

        Args:
            rules_path: Path to pilot rules file
        """
        super().__init__(rules_path)
        self.netlist_validator = NetlistValidator()
        self.port_matcher = PortMatcher()

    def validate(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Enhanced validation including netlist checks.

        Args:
            code: Generated code or netlist

        Returns:
            (is_valid, error_message)
        """
        # First check if it's a netlist (JSON/YAML)
        netlist_result = self._validate_netlist_if_present(code)
        if netlist_result is not None:
            is_valid, error_msg = netlist_result
            if not is_valid:
                return False, error_msg
        
        # Run base pilot validation
        return super().validate(code)

    def get_feedback(self, error_message: str) -> str:
        """
        Generate LLM feedback for pilot errors.
        
        Args:
            error_message: Error message from validate()
            
        Returns:
            Actionable feedback for LLM retry
        """
        # Use base class method if available
        if hasattr(super(), 'get_feedback'):
            return super().get_feedback(error_message)
        
        # Fallback feedback generation
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
        elif "SYNTAX" in error_message.upper():
            return (
                f"{error_message}\n\n"
                "Fix: Check for unterminated strings, missing quotes, or invalid characters."
            )
        else:
            return error_message
    
    def _validate_netlist_if_present(self, text: str) -> Optional[Tuple[bool, Optional[str]]]:
        """
        Validate netlist if text contains JSON/YAML netlist.

        Args:
            text: Text that might contain netlist

        Returns:
            (is_valid, error_message) or None if not a netlist
        """
        # Try to parse as JSON or YAML
        netlist_data = None
        
        # Try JSON first
        try:
            # Remove markdown fences
            cleaned = text.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('```')[1]
                if cleaned.startswith('json'):
                    cleaned = cleaned[4:]
                elif cleaned.startswith('yaml'):
                    cleaned = cleaned[4:]
            
            netlist_data = json.loads(cleaned)
        except:
            pass
        
        # Try YAML if JSON failed
        if netlist_data is None:
            try:
                cleaned = text.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('```')[1]
                    if cleaned.startswith('yaml'):
                        cleaned = cleaned[4:]
                
                netlist_data = yaml.safe_load(cleaned)
            except:
                pass
        
        # If we have a netlist, validate it
        if netlist_data and isinstance(netlist_data, dict):
            # Check if it looks like a netlist
            if 'netlist' in netlist_data or 'instances' in netlist_data:
                is_valid, issues = self.netlist_validator.validate(netlist_data)
                if not is_valid:
                    return False, f"Netlist validation failed: {', '.join(issues)}"
                
                # Check port matching
                port_issues = self._check_netlist_port_matching(netlist_data)
                if port_issues:
                    return False, f"Port matching issues: {', '.join(port_issues)}"
                
                # Check spacing from placements
                spacing_issues = self._check_netlist_spacing(netlist_data)
                if spacing_issues:
                    return False, f"Spacing issues: {', '.join(spacing_issues)}"
                
                return True, None
        
        return None  # Not a netlist

    def _check_netlist_port_matching(self, netlist: Dict) -> List[str]:
        """Check port matching in netlist."""
        issues = []
        
        if 'netlist' in netlist:
            netlist = netlist['netlist']
        
        instances = netlist.get('instances', {})
        connections = netlist.get('connections', {})
        
        # Check that port names in connections are valid
        for conn_key, conn_value in connections.items():
            if ',' in conn_key:
                inst_name, port_name = conn_key.split(',', 1)
                # Map port name
                mapped_port = self.port_matcher.map_port_name(port_name)
                # Check if instance exists
                if inst_name in instances:
                    # Try to validate port (would need component instantiation)
                    # For now, just check naming convention
                    if not port_name.lower().startswith('o'):
                        issues.append(f"Non-standard port name in connection: '{port_name}'")
            
            if isinstance(conn_value, str) and ',' in conn_value:
                inst_name, port_name = conn_value.split(',', 1)
                mapped_port = self.port_matcher.map_port_name(port_name)
                if inst_name in instances:
                    if not port_name.lower().startswith('o'):
                        issues.append(f"Non-standard port name in connection: '{port_name}'")
        
        return issues

    def _check_netlist_spacing(self, netlist: Dict) -> List[str]:
        """Check spacing from netlist placements."""
        issues = []
        
        if 'netlist' in netlist:
            netlist = netlist['netlist']
        
        placements = netlist.get('placements', {})
        if not placements:
            return issues
        
        positions = []
        for inst_name, pos in placements.items():
            if isinstance(pos, dict):
                x = pos.get('x', 0)
                y = pos.get('y', 0)
                positions.append((inst_name, x, y))
        
        # Check pairwise spacing
        for i, (name1, x1, y1) in enumerate(positions):
            for name2, x2, y2 in positions[i+1:]:
                distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                
                # Check horizontal spacing
                if abs(x2 - x1) < PILOT_MIN_SPACING_UM and abs(y2 - y1) < PILOT_MIN_VERTICAL_SPACING_UM:
                    issues.append(
                        f"Spacing violation: '{name1}' and '{name2}' are {distance:.1f}µm apart "
                        f"(minimum horizontal: {PILOT_MIN_SPACING_UM}µm, vertical: {PILOT_MIN_VERTICAL_SPACING_UM}µm)"
                    )
        
        return issues

