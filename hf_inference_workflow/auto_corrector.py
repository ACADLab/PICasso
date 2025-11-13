"""
Auto-Corrector Module - PhIDO-inspired fallback corrections

When LLM retries are exhausted, applies rule-based corrections to rescue failed designs.
Inspired by PhIDO's automatic component matching and routing correction approach.
"""

import re
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class AutoCorrector:
    """
    Fallback corrections when LLM retries are exhausted.
    
    Applies rule-based transformations to fix common code errors:
    - mirror() on Cell -> proper ComponentReference pattern
    - Spacing violations -> increase spacing by 1.5x
    - Port name errors -> common substitutions
    - route_single overuse -> convert to route_bundle
    """
    
    def __init__(self):
        """Initialize auto-corrector with correction rules."""
        self.correction_history = []
        
    def attempt_correction(
        self, 
        code: str, 
        error_type: str, 
        validation_reports: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Apply rule-based corrections based on error patterns.
        
        Args:
            code: Generated Python code that failed validation
            error_type: Type of error (mirror_error, spacing_error, etc.)
            validation_reports: Optional validation reports for context
            
        Returns:
            Corrected code if successful, None if no correction possible
        """
        logger.info(f"Attempting auto-correction for error type: {error_type}")
        
        original_code = code
        
        # ALWAYS fix Unicode characters first (common issue)
        code = self._fix_common_syntax_errors(code)
        unicode_fixed = (code != original_code)
        
        # Apply corrections based on error type
        if "mirror" in error_type.lower():
            code = self._fix_mirror_on_cell(code)
            
        elif "spacing" in error_type.lower() or "routing" in error_type.lower():
            code = self._increase_spacing(code, error_type)
            
        elif "port" in error_type.lower():
            code = self._fix_port_names(code)
            
        elif "routing_method" in error_type.lower():
            code = self._convert_to_route_bundle(code)
            
        elif "routing" in error_type.lower():
            # For routing errors, try fixing bend radius and Unicode
            code = self._fix_routing_bend_radius(code)
            code = self._fix_common_syntax_errors(code)
            
        elif "orientation" in error_type.lower():
            code = self._fix_combiner_orientation(code)
            
        elif "parsing" in error_type.lower() or "syntax" in error_type.lower():
            # For syntax/parsing errors, try to fix common issues:
            # 1. Unterminated strings (already handled by Unicode fix)
            # 2. Missing parentheses
            # 3. Invalid decimal literals
            code = self._fix_unterminated_strings(code)
            code = self._fix_missing_parentheses(code)
        
        elif "sax" in error_type.lower():
            # SAX errors often relate to port connections or component issues
            # Try port name fixes and spacing increases
            code = self._fix_port_names(code)
            code = self._increase_spacing(code, "routing_error")  # Use routing multiplier for SAX issues
        
        # Check if any corrections were applied
        corrected = (code != original_code)
        
        if corrected:
            logger.info(f"Auto-correction applied for {error_type} (Unicode fixed: {unicode_fixed})")
            self.correction_history.append({
                'error_type': error_type,
                'correction_applied': True
            })
            return code
        else:
            logger.warning(f"No auto-correction available for {error_type}")
            return None
    
    def _fix_mirror_on_cell(self, code: str) -> str:
        """
        Convert gf.components.xxx().mirror() to proper pattern.
        
        Transforms:
            gf.components.mmi1x2().mirror()
        To:
            ref = r.add_ref(gf.components.mmi1x2())
            ref.mirror()
        """
        # Pattern: component().mirror()
        pattern = r'(gf\.components\.\w+\([^)]*\))\.mirror\(\)'
        
        def replace_fn(match):
            component_call = match.group(1)
            # Generate unique variable name
            comp_name = re.search(r'\.(\w+)\(', component_call).group(1)
            ref_name = f"{comp_name}_ref_corrected"
            
            return (
                f"# Auto-corrected mirror pattern\n"
                f"{ref_name} = r.add_ref({component_call})\n"
                f"{ref_name}.mirror()"
            )
        
        corrected = re.sub(pattern, replace_fn, code)
        
        if corrected != code:
            logger.info("Applied mirror() correction")
        
        return corrected
    
    def _increase_spacing(self, code: str, error_type: str = "spacing_error") -> str:
        """
        Increase spacing in .move() calls by 1.5x to fix violations.
        For routing collisions, uses 2.0x multiplier for more aggressive spacing.
        
        Transforms:
            component.move((100, 0))
        To:
            component.move((150.0, 0))  # 1.5x for general spacing
            component.move((200.0, 0))  # 2.0x for routing collisions
        """
        def adjust_coord(match):
            try:
                x = float(match.group(1))
                y = float(match.group(2))
                # For routing collisions, use 2.0x multiplier (more aggressive)
                # For general spacing errors, use 1.5x
                multiplier = 2.0 if "routing" in error_type.lower() else 1.5
                new_x = x * multiplier
                new_y = y * multiplier
                return f"move(({new_x:.1f}, {new_y:.1f}))"
            except (ValueError, IndexError):
                return match.group(0)  # Return original if parsing fails
        
        pattern = r'move\(\(([0-9.-]+),\s*([0-9.-]+)\)\)'
        corrected = re.sub(pattern, adjust_coord, code)
        
        if corrected != code:
            multiplier_used = 2.0 if "routing" in error_type.lower() else 1.5
            logger.info(f"Applied spacing increase ({multiplier_used}x)")
        
        return corrected
    
    def _fix_port_names(self, code: str) -> str:
        """
        Fix common port name errors.
        
        Substitutions:
            'e1' -> 'o1'
            'e2' -> 'o2'
            'out1' -> 'o1'
            'in1' -> 'o1'
        """
        # Common port name substitutions
        substitutions = [
            (r'\.ports\[["\']e1["\']\]', ".ports['o1']"),
            (r'\.ports\[["\']e2["\']\]', ".ports['o2']"),
            (r'\.ports\[["\']e3["\']\]', ".ports['o3']"),
            (r'\.ports\[["\']out1["\']\]', ".ports['o1']"),
            (r'\.ports\[["\']out2["\']\]', ".ports['o2']"),
            (r'\.ports\[["\']in1["\']\]', ".ports['o1']"),
            (r'\.ports\[["\']in2["\']\]', ".ports['o2']"),
        ]
        
        corrected = code
        for pattern, replacement in substitutions:
            new_code = re.sub(pattern, replacement, corrected)
            if new_code != corrected:
                logger.info(f"Fixed port name: {pattern} -> {replacement}")
                corrected = new_code
        
        return corrected
    
    def _convert_to_route_bundle(self, code: str) -> str:
        """
        Convert multiple route_single calls to route_bundle.
        
        This is a complex transformation, so we apply a heuristic approach:
        Add a comment suggesting route_bundle usage.
        """
        # Check if route_single is used many times
        route_single_count = code.count('route_single')
        
        if route_single_count > 3:
            # Add a comment at the top suggesting route_bundle
            suggestion = (
                "# AUTO-CORRECTION: Consider converting multiple route_single calls to route_bundle\n"
                "# Example: gf.routing.route_bundle(r, [port1, port2], [port3, port4], separation=20)\n\n"
            )
            
            # Insert after imports
            import_end = code.find('\n\n')
            if import_end > 0:
                code = code[:import_end] + '\n\n' + suggestion + code[import_end+2:]
                logger.info("Added route_bundle suggestion comment")
        
        return code
    
    def _fix_combiner_orientation(self, code: str) -> str:
        """
        Add .mirror() calls to MMI combiners.
        
        Finds:
            combiner = r.add_ref(gf.components.mmi1x2())
        
        Adds after it:
            combiner.mirror()
        """
        # Pattern: combiner variable assignment
        combiner_pattern = r'(combiner\w*)\s*=\s*\w+\.add_ref\(gf\.components\.mmi[^)]*\)\s*\n'
        
        def add_mirror(match):
            original = match.group(0)
            combiner_name = match.group(1)
            # Check if .mirror() already exists nearby
            if f'{combiner_name}.mirror()' not in code[match.start():match.end()+50]:
                return f"{original}{combiner_name}.mirror()  # Auto-corrected\n"
            return original
        
        corrected = re.sub(combiner_pattern, add_mirror, code, flags=re.IGNORECASE)
        
        if corrected != code:
            logger.info("Added .mirror() call to combiner")
        
        return corrected
    
    def _fix_routing_bend_radius(self, code: str) -> str:
        """
        Fix routing bend radius violations by increasing radius to minimum (15µm).
        
        Finds patterns like:
            route_single(..., radius=10)
            route_bundle(..., radius=10.0)
        And changes to:
            route_single(..., radius=15.0)
            route_bundle(..., radius=15.0)
        """
        def fix_radius(match):
            try:
                radius_str = match.group(1)
                # Handle cases like "10.0µm" or "10µm" - extract just the number
                radius_clean = re.sub(r'[^\d.]', '', radius_str)
                if radius_clean:
                    radius = float(radius_clean)
                    if radius < 15.0:
                        return f"radius={15.0}"
                return match.group(0)
            except (ValueError, IndexError):
                return match.group(0)
        
        # Pattern: radius=N or radius=N.0 or radius=Nµm (with optional units)
        radius_pattern = r'radius\s*=\s*([0-9.]+[^\s,\)]*)'
        corrected = re.sub(radius_pattern, fix_radius, code)
        
        if corrected != code:
            logger.info("Fixed routing bend radius (increased to 15µm minimum)")
        
        return corrected
    
    def _fix_unterminated_strings(self, code: str) -> str:
        """
        Fix unterminated string literals by checking for unmatched quotes.
        
        This is a simple heuristic - looks for lines with odd number of quotes.
        """
        lines = code.split('\n')
        fixed_lines = []
        for line in lines:
            # Count single and double quotes
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')
            
            # If odd number of quotes, might be unterminated
            # Try to fix by adding a closing quote at the end
            if (single_quotes % 2 == 1) and not line.strip().endswith("'"):
                # Check if it's a string assignment
                if "=" in line and ("'" in line or '"' in line):
                    line = line.rstrip() + "'"
                    logger.info("Fixed unterminated string by adding closing quote")
            elif (double_quotes % 2 == 1) and not line.strip().endswith('"'):
                if "=" in line:
                    line = line.rstrip() + '"'
                    logger.info("Fixed unterminated string by adding closing double quote")
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_missing_parentheses(self, code: str) -> str:
        """
        Fix missing parentheses in function calls.
        
        Looks for patterns like: function_name(  without closing )
        """
        # Count opening and closing parentheses
        open_parens = code.count('(')
        close_parens = code.count(')')
        
        if open_parens > close_parens:
            missing = open_parens - close_parens
            # Add missing closing parentheses at the end
            code = code.rstrip() + ')' * missing
            logger.info(f"Fixed {missing} missing closing parentheses")
        
        return code
    
    def _fix_common_syntax_errors(self, code: str) -> str:
        """
        Fix common syntax errors in generated code.
        
        Uses the same cleaning logic as _clean_generated_code for consistency.
        """
        # Import and use the centralized cleaning function
        from hf_inference_workflow.gen_data_validated import _clean_generated_code
        return _clean_generated_code(code)
    
    def get_statistics(self) -> Dict:
        """Get correction statistics for analysis."""
        return {
            'total_corrections': len(self.correction_history),
            'corrections_by_type': {
                error_type: sum(1 for c in self.correction_history if c['error_type'] == error_type)
                for error_type in set(c['error_type'] for c in self.correction_history)
            }
        }

