"""
Dynamic Pilot Prompt Updater

After pass@3 failures, analyzes error patterns and updates pilot validator rules
dynamically. Adds learned patterns to pilot prompt and verifies robustness of
input template, pilot, and component injection.
"""

import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from collections import defaultdict

from ..error_handling.error_extractor import ErrorExtractor, ErrorCategory

logger = logging.getLogger(__name__)


class PilotPromptUpdater:
    """
    Dynamically updates pilot validator rules based on error patterns.
    
    After pass@3 failures, analyzes errors and:
    1. Updates pilot validator rules
    2. Adds learned patterns to pilot prompt
    3. Verifies robustness of templates and prompts
    """
    
    def __init__(self, rules_path: Optional[str] = None):
        """
        Initialize pilot prompt updater.
        
        Args:
            rules_path: Path to pilot rules JSON file
        """
        self.rules_path = rules_path or str(
            Path(__file__).parent.parent / "pilot_rules.json"
        )
        self.error_extractor = ErrorExtractor()
        self.error_patterns = defaultdict(int)  # Track error frequency
        self.learned_rules = self._load_rules()
    
    def _load_rules(self) -> Dict:
        """Load existing pilot rules (persistent across runs)."""
        if Path(self.rules_path).exists():
            try:
                with open(self.rules_path, 'r') as f:
                    loaded = json.load(f)
                    
                    # Handle old format migration: convert dict-based patterns to string-based
                    if 'custom_patterns' in loaded:
                        old_patterns = loaded['custom_patterns']
                        if old_patterns and isinstance(old_patterns[0], dict):
                            # Old format: list of dicts with 'type', 'occurrences', etc.
                            # Migrate to new format: list of rule strings
                            logger.info(f"Migrating {len(old_patterns)} old-format rules to new format")
                            migrated = []
                            for old_pattern in old_patterns:
                                if isinstance(old_pattern, dict):
                                    rule_type = old_pattern.get('type', 'unknown')
                                    migrated.append(f"CRITICAL: Avoid {rule_type} errors (learned from previous runs)")
                            loaded['custom_patterns'] = migrated
                            logger.info(f"✅ Migrated {len(migrated)} rules to new format")
                    
                    # Ensure required keys exist
                    if 'custom_patterns' not in loaded:
                        loaded['custom_patterns'] = []
                    if 'error_patterns' not in loaded:
                        loaded['error_patterns'] = {}
                    if 'prevention_rules' not in loaded:
                        loaded['prevention_rules'] = []
                    if 'template_suggestions' not in loaded:
                        loaded['template_suggestions'] = []
                    
                    logger.info(f"✅ Loaded {len(loaded.get('custom_patterns', []))} existing pilot rules from {self.rules_path}")
                    return loaded
            except Exception as e:
                logger.warning(f"Failed to load pilot rules: {e}")
        
        # Return empty structure if file doesn't exist
        return {
            "custom_patterns": [],
            "error_patterns": {},
            "prevention_rules": [],
            "template_suggestions": []
        }
    
    def _save_rules(self):
        """Save updated rules to file (permanent storage - accumulates across runs)."""
        try:
            Path(self.rules_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.rules_path, 'w') as f:
                json.dump(self.learned_rules, f, indent=2)
            num_rules = len(self.learned_rules.get('custom_patterns', []))
            logger.info(f"✅ Saved {num_rules} pilot rules to {self.rules_path} (permanent - will persist across runs)")
        except Exception as e:
            logger.error(f"Failed to save pilot rules: {e}")
    
    def analyze_failures(
        self,
        failed_cases: List[Dict],
        max_retries: int = 3
    ) -> Dict:
        """
        Analyze failed cases after pass@3 to identify patterns.
        
        Args:
            failed_cases: List of failed case dictionaries with:
                - error_message: str
                - code: str
                - validation_report: Dict
                - failed_stage: str
            max_retries: Maximum retries attempted (default: 3)
            
        Returns:
            Analysis report with:
                - common_errors: List of most common error types
                - missing_patterns: Patterns not caught by pilot
                - template_gaps: Gaps in input template
                - injection_gaps: Gaps in component injection
                - suggested_updates: Suggested rule updates
        """
        logger.info(f"Analyzing {len(failed_cases)} failed cases after pass@{max_retries}")
        
        # Extract errors from all failed cases
        error_infos = []
        for case in failed_cases:
            error_info = self.error_extractor.extract_error(
                error_message=case.get('error_message', ''),
                code=case.get('code'),
                validation_report=case.get('validation_report'),
                failed_stage=case.get('failed_stage')
            )
            error_infos.append(error_info)
            
            # Track error patterns
            category = error_info['category']
            self.error_patterns[category] += 1
        
        # Analyze patterns
        analysis = {
            'error_infos': error_infos,  # Include error_infos for detailed analysis
            'common_errors': self._identify_common_errors(error_infos),
            'missing_patterns': self._identify_missing_patterns(error_infos),
            'template_gaps': self._identify_template_gaps(error_infos),
            'injection_gaps': self._identify_injection_gaps(error_infos),
            'suggested_updates': []
        }
        
        # Generate suggested updates (uses error_infos for specific fixes)
        analysis['suggested_updates'] = self._generate_suggested_updates(analysis)
        
        return analysis
    
    def _identify_common_errors(self, error_infos: List[Dict]) -> List[Dict]:
        """Identify most common error types."""
        category_counts = defaultdict(int)
        category_examples = defaultdict(list)
        
        for error_info in error_infos:
            category = error_info['category']
            category_counts[category] += 1
            if len(category_examples[category]) < 3:  # Keep up to 3 examples
                category_examples[category].append({
                    'error_type': error_info['error_type'],
                    'error_message': error_info['error_message'][:200],  # Truncate
                    'severity': error_info['severity']
                })
        
        # Sort by frequency
        sorted_categories = sorted(
            category_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        common_errors = []
        for category, count in sorted_categories[:10]:  # Top 10
            common_errors.append({
                'category': category,
                'count': count,
                'percentage': (count / len(error_infos)) * 100,
                'examples': category_examples[category]
            })
        
        return common_errors
    
    def _identify_missing_patterns(self, error_infos: List[Dict]) -> List[str]:
        """Identify error patterns not caught by pilot validator."""
        missing_patterns = []
        
        # Errors that should have been caught by pilot but weren't
        pilot_catchable = [
            ErrorCategory.SYNTAX_ERROR,
            ErrorCategory.MIRROR_ERROR,
            ErrorCategory.SPACING_VIOLATION,
            ErrorCategory.PORT_MISMATCH,
            ErrorCategory.MISSING_ROUTE,
            ErrorCategory.WRONG_API,
        ]
        
        for error_info in error_infos:
            category_str = error_info['category']
            try:
                category = ErrorCategory(category_str)
                if category in pilot_catchable:
                    # This should have been caught by pilot
                    missing_patterns.append(
                        f"{error_info['error_type']}: {error_info['prevention_rule']}"
                    )
            except ValueError:
                pass
        
        # Remove duplicates
        return list(set(missing_patterns))
    
    def _identify_template_gaps(self, error_infos: List[Dict]) -> List[str]:
        """Identify gaps in input template."""
        gaps = []
        
        # Check for errors that suggest template issues
        for error_info in error_infos:
            category_str = error_info['category']
            
            if category_str == 'port_mismatch':
                gaps.append(
                    "Template should emphasize checking component.ports before using port names"
                )
            elif category_str == 'sax_component_not_found':
                gaps.append(
                    "Template should list available SAX-supported components"
                )
            elif category_str == 'missing_route':
                gaps.append(
                    "Template should emphasize that components must be routed, not just placed"
                )
            elif category_str == 'spacing_violation':
                gaps.append(
                    "Template should provide specific spacing examples (100µm for complex circuits)"
                )
        
        return list(set(gaps))
    
    def _identify_injection_gaps(self, error_infos: List[Dict]) -> List[str]:
        """Identify gaps in component injection."""
        gaps = []
        
        # Check for errors that suggest injection issues
        for error_info in error_infos:
            category_str = error_info['category']
            
            if category_str == 'port_mismatch':
                gaps.append(
                    "Component injection should include port names for each component"
                )
            elif category_str == 'sax_component_not_found':
                gaps.append(
                    "Component injection should indicate which components have SAX models"
                )
            elif category_str == 'wrong_api':
                gaps.append(
                    "Component injection should include correct API usage examples"
                )
        
        return list(set(gaps))
    
    def _generate_suggested_updates(self, analysis: Dict) -> List[Dict]:
        """Generate suggested updates for pilot rules and prompts."""
        suggestions = []
        
        # Extract specific error patterns from failed cases
        error_infos = analysis.get('error_infos', [])
        
        # Generate specific pilot rules for syntax errors
        for error_info in error_infos:
            category = error_info.get('category', '')
            error_msg = error_info.get('error_message', '')
            
            # Syntax errors - generate specific fix rules
            if 'syntax' in category.lower() or 'syntax' in error_msg.lower() or 'incomplete' in error_msg.lower():
                if 'incomplete_method_call' in error_msg.lower() or 'obj.' in error_msg.lower() or '.0)' in error_msg.lower():
                    suggestions.append({
                        'type': 'pilot_rule',
                        'priority': 'critical',
                        'suggestion': "CRITICAL: NEVER generate incomplete method calls like 'obj.0)' or 'mmi2.0)'. Always include the complete method name. Example: 'mmi2.move((250, 0))' not 'mmi2.0)'. Every method call must have: object.method_name(arguments).",
                        'category': 'syntax_error',
                        'fix_example': "❌ WRONG: mmi2.0) | ✅ CORRECT: mmi2.move((250, 0)) or mmi2.mirror()"
                    })
                elif 'unterminated' in error_msg.lower() or 'missing' in error_msg.lower():
                    if '}' in error_msg or 'missing }' in error_msg.lower():
                        suggestions.append({
                            'type': 'pilot_rule',
                            'priority': 'high',
                            'suggestion': "CRITICAL: Always close all brackets and braces. Check for missing '}' or ')' in function calls and code blocks. Example: r.area() not r.area(",
                            'category': 'syntax_error',
                            'fix_example': "If you see 'r.area(' add closing ')' to make 'r.area()'"
                        })
                    elif ')' in error_msg or 'missing )' in error_msg.lower():
                        suggestions.append({
                            'type': 'pilot_rule',
                            'priority': 'high',
                            'suggestion': "CRITICAL: Always close all parentheses. Check function calls like r.area() not r.area(. Example fix: r.area( → r.area()",
                            'category': 'syntax_error',
                            'fix_example': "If you see 'r.area(' add closing ')' to make 'r.area()'"
                        })
                    elif '"' in error_msg or "'" in error_msg:
                        suggestions.append({
                            'type': 'pilot_rule',
                            'priority': 'high',
                            'suggestion': "CRITICAL: Always close all string quotes. Check for missing closing quotes in strings.",
                            'category': 'syntax_error'
                        })
                elif 'unmatched' in error_msg.lower():
                    suggestions.append({
                        'type': 'pilot_rule',
                        'priority': 'high',
                        'suggestion': f"CRITICAL: Fix unmatched brackets/parentheses. Error: {error_msg[:100]}. Always ensure every opening bracket/parenthesis has a matching closing one.",
                        'category': 'syntax_error'
                    })
                elif 'invalid decimal' in error_msg.lower():
                    suggestions.append({
                        'type': 'pilot_rule',
                        'priority': 'high',
                        'suggestion': "CRITICAL: Use valid Python float literals. Use 10.0 not 10.0.5 or 10 microns. Never attach units to numbers.",
                        'category': 'syntax_error'
                    })
            
            # Component errors
            elif 'component' in category.lower() or 'component' in error_msg.lower():
                if 'not defined' in error_msg.lower() or 'has no attribute' in error_msg.lower():
                    suggestions.append({
                        'type': 'pilot_rule',
                        'priority': 'high',
                        'suggestion': f"CRITICAL: Component not found. Check component reference. Error: {error_msg[:100]}. Use only components listed in the component reference.",
                        'category': 'component_error'
                    })
            
            # Routing errors
            elif 'routing' in category.lower() or 'route' in error_msg.lower():
                if 'ports1' in error_msg and 'ports2' in error_msg:
                    suggestions.append({
                        'type': 'pilot_rule',
                        'priority': 'high',
                        'suggestion': "CRITICAL: route_bundle() requires equal number of ports in ports1 and ports2 lists. Count ports carefully before routing.",
                        'category': 'routing_error'
                    })
                elif 'angle' in error_msg.lower():
                    suggestions.append({
                        'type': 'pilot_rule',
                        'priority': 'high',
                        'suggestion': "CRITICAL: All ports at routing target must have the same angle. Check port orientations before routing.",
                        'category': 'routing_error'
                    })
        
        # Suggest pilot rule updates for missing patterns
        for pattern in analysis['missing_patterns'][:3]:  # Top 3
            suggestions.append({
                'type': 'pilot_rule',
                'priority': 'high',
                'suggestion': f"Add pilot check: {pattern}",
                'category': 'missing_pattern'
            })
        
        # Suggest template updates
        for gap in analysis['template_gaps'][:3]:  # Top 3
            suggestions.append({
                'type': 'template_update',
                'priority': 'medium',
                'suggestion': gap,
                'category': 'template_gap'
            })
        
        # Suggest injection updates
        for gap in analysis['injection_gaps'][:3]:  # Top 3
            suggestions.append({
                'type': 'injection_update',
                'priority': 'medium',
                'suggestion': gap,
                'category': 'injection_gap'
            })
        
        return suggestions
    
    def update_pilot_rules(self, analysis: Dict, auto_apply: bool = False) -> Dict:
        """
        Update pilot rules based on analysis.
        
        Args:
            analysis: Analysis report from analyze_failures()
            auto_apply: If True, automatically apply updates (default: False)
            
        Returns:
            Update report with applied changes
        """
        updates_applied = []
        updates_pending = []
        
        # Process suggested updates
        for suggestion in analysis['suggested_updates']:
            if suggestion['type'] == 'pilot_rule':
                rule_text = suggestion['suggestion']
                
                # Add fix example if available
                if 'fix_example' in suggestion:
                    rule_text = f"{rule_text}\n   Fix example: {suggestion['fix_example']}"
                
                # Add to learned rules
                if 'custom_patterns' not in self.learned_rules:
                    self.learned_rules['custom_patterns'] = []
                
                # Check if similar rule already exists (avoid duplicates)
                # Handle both string rules (new format) and dict rules (old format)
                rule_exists = False
                for existing_rule in self.learned_rules['custom_patterns']:
                    if isinstance(existing_rule, str):
                        # New format: compare strings
                        if rule_text[:50] in existing_rule or existing_rule[:50] in rule_text:
                            rule_exists = True
                            break
                    elif isinstance(existing_rule, dict):
                        # Old format: compare with rule text
                        if rule_text[:50] in str(existing_rule.get('type', '')):
                            rule_exists = True
                            break
                
                if not rule_exists:
                    if auto_apply:
                        self.learned_rules['custom_patterns'].append(rule_text)
                        updates_applied.append({
                            'type': 'pilot_rule',
                            'update': rule_text,
                            'priority': suggestion['priority'],
                            'category': suggestion.get('category', 'unknown')
                        })
                        logger.info(f"✅ Applied pilot rule: {rule_text[:100]}...")
                    else:
                        updates_pending.append({
                            'type': 'pilot_rule',
                            'update': rule_text,
                            'priority': suggestion['priority']
                        })
        
        # Save rules if updates were applied
        if auto_apply and updates_applied:
            self._save_rules()
        
        return {
            'applied': updates_applied,
            'pending': updates_pending,
            'total_suggestions': len(analysis['suggested_updates'])
        }
    
    def verify_robustness(
        self,
        input_template: str,
        pilot_prompt: str,
        component_injection: str
    ) -> Dict:
        """
        Verify robustness of input template, pilot prompt, and component injection.
        
        Args:
            input_template: Current input template text
            pilot_prompt: Current pilot prompt text
            component_injection: Current component injection text
            
        Returns:
            Robustness report with:
                - template_coverage: Coverage of common errors
                - pilot_coverage: Coverage of pilot-catchable errors
                - injection_coverage: Coverage of component-related errors
                - gaps: Identified gaps
                - recommendations: Recommendations for improvement
        """
        # Common error keywords to check for
        common_errors = [
            'port', 'routing', 'spacing', 'mirror', 'syntax',
            'component', 'route_single', 'route_bundle'
        ]
        
        template_coverage = {}
        pilot_coverage = {}
        injection_coverage = {}
        
        # Check template coverage
        template_lower = input_template.lower()
        for error_keyword in common_errors:
            template_coverage[error_keyword] = error_keyword in template_lower
        
        # Check pilot coverage
        pilot_lower = pilot_prompt.lower()
        pilot_catchable = ['syntax', 'mirror', 'spacing', 'port', 'routing']
        for error_keyword in pilot_catchable:
            pilot_coverage[error_keyword] = error_keyword in pilot_lower
        
        # Check injection coverage
        injection_lower = component_injection.lower()
        injection_relevant = ['port', 'component', 'api', 'method']
        for error_keyword in injection_relevant:
            injection_coverage[error_keyword] = error_keyword in injection_lower
        
        # Identify gaps
        gaps = []
        if not template_coverage.get('route_single', False):
            gaps.append("Template doesn't mention route_single() requirement")
        if not template_coverage.get('spacing', False):
            gaps.append("Template doesn't emphasize spacing requirements")
        if not pilot_coverage.get('mirror', False):
            gaps.append("Pilot doesn't check for mirror() errors")
        if not injection_coverage.get('port', False):
            gaps.append("Component injection doesn't include port names")
        
        # Generate recommendations
        recommendations = []
        if gaps:
            for gap in gaps:
                recommendations.append({
                    'gap': gap,
                    'priority': 'high' if 'route' in gap or 'spacing' in gap else 'medium',
                    'suggestion': self._get_recommendation_for_gap(gap)
                })
        
        return {
            'template_coverage': template_coverage,
            'pilot_coverage': pilot_coverage,
            'injection_coverage': injection_coverage,
            'gaps': gaps,
            'recommendations': recommendations,
            'overall_robustness': 'good' if len(gaps) < 3 else 'needs_improvement'
        }
    
    def _get_recommendation_for_gap(self, gap: str) -> str:
        """Get recommendation for identified gap."""
        recommendations = {
            "Template doesn't mention route_single() requirement": (
                "Add explicit instruction: 'All component connections must use "
                "route_single() or route_bundle() to create physical waveguides.'"
            ),
            "Template doesn't emphasize spacing requirements": (
                "Add spacing guidelines: 'Minimum spacing 20µm (100µm for complex circuits). "
                "Use .move() to position components with adequate separation.'"
            ),
            "Pilot doesn't check for mirror() errors": (
                "Add pilot check: 'Detect gf.components.xxx().mirror() pattern and flag as error.'"
            ),
            "Component injection doesn't include port names": (
                "Add port information: 'For each component, list available port names "
                "(e.g., mmi1x2: o1, o2, o3).'"
            ),
        }
        
        return recommendations.get(gap, "Review and add appropriate guidance.")
    
    def get_base_pilot_restrictions(self) -> str:
        """
        Get base pilot restrictions that should always be included.
        These are permanent rules about GDSFactory limitations and best practices.
        """
        base_rules = """CRITICAL GDSFACTORY LIMITATIONS AND RESTRICTIONS:

⚠️⚠️⚠️ RULE #0 - MOST CRITICAL: ASCII ONLY - NO UNICODE! ⚠️⚠️⚠️
   - Use ONLY ASCII characters. NEVER use Unicode: 'um' not 'µm', 'x' not '×', '->' not '→'
   - Unicode causes syntax errors - this is MANDATORY and checked first!
   - All numbers must be valid Python floats: 10.0 not 10µm, not 10.0.5

1. Port Connection Limitations:
   - ⚠️  GDSFactory's get_netlist() fails for "More than two connected optical ports"
   - ⚠️  Avoid connecting external ports to multiple internal ports simultaneously
   - ✅ Solution: Connect ports one-to-one, use intermediate routing if needed
   - ✅ Example: Instead of connecting 'o1' to both 'mmi1,o1' and 'straight,o2', 
     connect them sequentially: 'o1' -> 'mmi1,o1', then route 'mmi1,o2' -> 'straight,o1'

2. Routing and Placement (CRITICAL - PhIDO-inspired):
   - MINIMUM 200um spacing between components (MANDATORY)
   - For simple designs (≤5 components): 200um minimum
   - For complex designs (>5 components): 250um+ spacing required
   - Vertical stacking: Use +/-100um or more vertical offset
   - Horizontal placement: 250-300um separation
   - Framework will automatically fix routing collisions using:
     * Iterative spacing fixes (1.5x → 2.0x → 2.5x multipliers)
     * Brute-force rotation algorithm (4 orientations per component, PhIDO-style)
   - If routing collision persists, increase spacing to 300um+ between components

3. Component Limitations:
   - mmi2x1 does NOT exist - use mmi1x2() and call .mirror() on ComponentReference
   - Always verify component names exist in gf.components before using
   - Check component.ports to see available port names

4. Syntax Requirements:
   - Use ONLY ASCII characters (no Unicode: 'um' not 'µm')
   - All numbers must be valid Python floats (10.0 not 10 microns)
   - Complete all method calls (obj.method() not obj.0))
   - Close all parentheses and quotes"""
        return base_rules.strip()
    
    def get_updated_pilot_prompt(self, base_prompt: str = "") -> str:
        """
        Get updated pilot prompt with learned rules.
        
        Args:
            base_prompt: Base pilot prompt (can be empty string)
            
        Returns:
            Updated prompt with learned rules (standalone if base_prompt is empty)
        """
        # Combine base restrictions with learned rules
        prompt = "=== PILOT RESTRICTIONS (Pre-execution Validation Rules) ===\n\n"
        
        # Add base permanent restrictions first
        base_restrictions = self.get_base_pilot_restrictions()
        prompt += base_restrictions + "\n\n"
        
        prompt += "=== LEARNED RULES (Dynamically Updated from Failures) ===\n\n"
        prompt += "These rules are learned from previous failures and help prevent common errors:\n\n"
        
        if not self.learned_rules.get('custom_patterns'):
            prompt += "   (No rules learned yet - will accumulate as errors are detected)\n"
        else:
            additional_rules = ""
            additional_rules += "⚠️ CRITICAL: The following errors were detected in previous attempts. AVOID these mistakes:\n"
            additional_rules += "💡 These rules accumulate across ALL runs - the framework learns from every error!\n\n"
        
            # Filter out old-format dict rules, keep only string rules
            string_rules = [
                rule for rule in self.learned_rules['custom_patterns']
                if isinstance(rule, str)
            ]
            
            if string_rules:
                for i, pattern in enumerate(string_rules, 1):
                    additional_rules += f"{i}. {pattern}\n"
                prompt += additional_rules
        
        prompt += "\n💡 TIP: Review your code carefully before submitting. Check for:\n"
        prompt += "   - All brackets/parentheses are closed (r.area() not r.area()\n"
        prompt += "   - All strings have closing quotes\n"
        prompt += "   - All function calls are complete\n"
        prompt += "   - Component names match the reference exactly\n"
        prompt += "   - Port counts match for route_bundle()\n"
        
        if base_prompt:
            return base_prompt + "\n\n" + prompt
        else:
            return prompt

