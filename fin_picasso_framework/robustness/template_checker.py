"""
Template Robustness Checker

After pass@3 failures, verifies that input template, pilot prompt, and component
injection are robust enough to avoid basic errors like port mismatch, SAX component
not found, package errors, etc.
"""

import logging
from typing import Dict, List, Optional
from ..error_handling.error_extractor import ErrorExtractor, ErrorCategory

logger = logging.getLogger(__name__)


class TemplateRobustnessChecker:
    """
    Verifies robustness of templates and prompts.
    
    After pass@3 failures, checks:
    - Input template covers common errors
    - Pilot prompt catches known patterns
    - Component injection prevents port mismatches
    - SAX component knowledge prevents "not found" errors
    """
    
    def __init__(self):
        """Initialize template robustness checker."""
        self.error_extractor = ErrorExtractor()
    
    def check_robustness(
        self,
        input_template: str,
        pilot_prompt: str,
        component_injection: str,
        failed_cases: List[Dict]
    ) -> Dict:
        """
        Check robustness of templates and prompts against failed cases.
        
        Args:
            input_template: Current input template text
            pilot_prompt: Current pilot prompt text
            component_injection: Current component injection text
            failed_cases: List of failed case dictionaries
            
        Returns:
            Robustness report with:
                - template_coverage: Coverage of common errors
                - pilot_coverage: Coverage of pilot-catchable errors
                - injection_coverage: Coverage of component-related errors
                - gaps: Identified gaps
                - recommendations: Recommendations for improvement
                - robustness_score: Overall robustness score (0-1)
        """
        logger.info(f"Checking robustness against {len(failed_cases)} failed cases")
        
        # Extract errors from failed cases
        error_categories = []
        for case in failed_cases:
            error_info = self.error_extractor.extract_error(
                error_message=case.get('error_message', ''),
                code=case.get('code'),
                validation_report=case.get('validation_report'),
                failed_stage=case.get('failed_stage')
            )
            error_categories.append(error_info['category'])
        
        # Check coverage
        template_coverage = self._check_template_coverage(input_template, error_categories)
        pilot_coverage = self._check_pilot_coverage(pilot_prompt, error_categories)
        injection_coverage = self._check_injection_coverage(component_injection, error_categories)
        
        # Identify gaps
        gaps = self._identify_gaps(
            template_coverage,
            pilot_coverage,
            injection_coverage,
            error_categories
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(gaps, error_categories)
        
        # Calculate robustness score
        robustness_score = self._calculate_robustness_score(
            template_coverage,
            pilot_coverage,
            injection_coverage,
            gaps
        )
        
        return {
            'template_coverage': template_coverage,
            'pilot_coverage': pilot_coverage,
            'injection_coverage': injection_coverage,
            'gaps': gaps,
            'recommendations': recommendations,
            'robustness_score': robustness_score,
            'overall_assessment': self._assess_robustness(robustness_score)
        }
    
    def _check_template_coverage(
        self,
        template: str,
        error_categories: List[str]
    ) -> Dict[str, bool]:
        """Check if template covers common error patterns."""
        template_lower = template.lower()
        
        # Keywords that should be in template for each error category
        required_keywords = {
            'port_mismatch': ['port', 'ports', 'o1', 'o2', 'check'],
            'sax_component_not_found': ['component', 'sax', 'model'],
            'package_error': ['import', 'gdsfactory', 'gf.components'],
            'routing_error': ['route', 'routing', 'route_single', 'route_bundle'],
            'spacing_violation': ['spacing', '20', '100', 'minimum', 'move'],
            'mirror_error': ['mirror', 'add_ref', 'componentreference'],
            'syntax_error': ['ascii', 'unicode', 'syntax'],
            'missing_route': ['route', 'route_single', 'route_bundle', 'connect'],
            'incomplete_routing': ['route', 'all', 'connect', 'connection'],
            'wrong_api': ['route_single', 'route_bundle', 'gf.routing'],
            'drc_violation': ['spacing', 'bend', 'radius', 'clearance'],
        }
        
        coverage = {}
        for category in set(error_categories):
            keywords = required_keywords.get(category, [])
            if keywords:
                coverage[category] = all(
                    keyword in template_lower for keyword in keywords
                )
            else:
                coverage[category] = False
        
        return coverage
    
    def _check_pilot_coverage(
        self,
        pilot_prompt: str,
        error_categories: List[str]
    ) -> Dict[str, bool]:
        """Check if pilot prompt catches known patterns."""
        pilot_lower = pilot_prompt.lower()
        
        # Pilot-catchable errors
        pilot_catchable = [
            'syntax_error',
            'mirror_error',
            'spacing_violation',
            'port_mismatch',
            'missing_route',
            'wrong_api',
        ]
        
        # Keywords that should be in pilot for each error
        required_keywords = {
            'syntax_error': ['syntax', 'unicode', 'invalid'],
            'mirror_error': ['mirror', 'reflect', 'add_ref'],
            'spacing_violation': ['spacing', 'minimum', '100'],
            'port_mismatch': ['port', 'ports', 'check'],
            'missing_route': ['route', 'route_single', 'missing'],
            'wrong_api': ['route_single', 'route_bundle', 'api'],
        }
        
        coverage = {}
        for category in set(error_categories):
            if category in pilot_catchable:
                keywords = required_keywords.get(category, [])
                if keywords:
                    coverage[category] = all(
                        keyword in pilot_lower for keyword in keywords
                    )
                else:
                    coverage[category] = False
            else:
                coverage[category] = None  # Not pilot-catchable
        
        return coverage
    
    def _check_injection_coverage(
        self,
        component_injection: str,
        error_categories: List[str]
    ) -> Dict[str, bool]:
        """Check if component injection prevents component-related errors."""
        injection_lower = component_injection.lower()
        
        # Injection-relevant errors
        injection_relevant = [
            'port_mismatch',
            'sax_component_not_found',
            'package_error',
            'wrong_api',
        ]
        
        # Keywords that should be in injection for each error
        required_keywords = {
            'port_mismatch': ['port', 'ports', 'o1', 'o2', 'o3'],
            'sax_component_not_found': ['component', 'sax', 'model', 'available'],
            'package_error': ['gf.components', 'import', 'api'],
            'wrong_api': ['route_single', 'route_bundle', 'method'],
        }
        
        coverage = {}
        for category in set(error_categories):
            if category in injection_relevant:
                keywords = required_keywords.get(category, [])
                if keywords:
                    coverage[category] = all(
                        keyword in injection_lower for keyword in keywords
                    )
                else:
                    coverage[category] = False
            else:
                coverage[category] = None  # Not injection-relevant
        
        return coverage
    
    def _identify_gaps(
        self,
        template_coverage: Dict[str, bool],
        pilot_coverage: Dict[str, bool],
        injection_coverage: Dict[str, bool],
        error_categories: List[str]
    ) -> List[Dict]:
        """Identify gaps in coverage."""
        gaps = []
        
        # Count occurrences of each error category
        from collections import Counter
        category_counts = Counter(error_categories)
        
        for category, count in category_counts.items():
            # Check template coverage
            if not template_coverage.get(category, False):
                gaps.append({
                    'category': category,
                    'type': 'template',
                    'severity': 'high' if count > 2 else 'medium',
                    'count': count,
                    'description': f"Template doesn't cover {category} errors ({count} occurrences)"
                })
            
            # Check pilot coverage (if pilot-catchable)
            pilot_cov = pilot_coverage.get(category)
            if pilot_cov is False:
                gaps.append({
                    'category': category,
                    'type': 'pilot',
                    'severity': 'high' if count > 2 else 'medium',
                    'count': count,
                    'description': f"Pilot doesn't catch {category} errors ({count} occurrences)"
                })
            
            # Check injection coverage (if injection-relevant)
            injection_cov = injection_coverage.get(category)
            if injection_cov is False:
                gaps.append({
                    'category': category,
                    'type': 'injection',
                    'severity': 'high' if count > 2 else 'medium',
                    'count': count,
                    'description': f"Component injection doesn't prevent {category} errors ({count} occurrences)"
                })
        
        return gaps
    
    def _generate_recommendations(
        self,
        gaps: List[Dict],
        error_categories: List[str]
    ) -> List[Dict]:
        """Generate recommendations for improving robustness."""
        recommendations = []
        
        # Group gaps by type
        template_gaps = [g for g in gaps if g['type'] == 'template']
        pilot_gaps = [g for g in gaps if g['type'] == 'pilot']
        injection_gaps = [g for g in gaps if g['type'] == 'injection']
        
        # Template recommendations
        if template_gaps:
            recommendations.append({
                'type': 'template',
                'priority': 'high' if any(g['severity'] == 'high' for g in template_gaps) else 'medium',
                'gaps': template_gaps,
                'suggestion': self._get_template_suggestion(template_gaps)
            })
        
        # Pilot recommendations
        if pilot_gaps:
            recommendations.append({
                'type': 'pilot',
                'priority': 'high' if any(g['severity'] == 'high' for g in pilot_gaps) else 'medium',
                'gaps': pilot_gaps,
                'suggestion': self._get_pilot_suggestion(pilot_gaps)
            })
        
        # Injection recommendations
        if injection_gaps:
            recommendations.append({
                'type': 'injection',
                'priority': 'high' if any(g['severity'] == 'high' for g in injection_gaps) else 'medium',
                'gaps': injection_gaps,
                'suggestion': self._get_injection_suggestion(injection_gaps)
            })
        
        return recommendations
    
    def _get_template_suggestion(self, gaps: List[Dict]) -> str:
        """Get suggestion for template improvements."""
        categories = [g['category'] for g in gaps]
        
        suggestions = []
        if 'port_mismatch' in categories:
            suggestions.append(
                "Add explicit instruction: 'Always check component.ports.keys() before using port names. "
                "Common ports are o1, o2, o3 for outputs.'"
            )
        if 'missing_route' in categories:
            suggestions.append(
                "Add explicit instruction: 'All component connections MUST use route_single() or "
                "route_bundle() to create physical waveguides. Components placed but not routed will fail.'"
            )
        if 'spacing_violation' in categories:
            suggestions.append(
                "Add spacing guidelines: 'Minimum spacing 20µm (100µm for complex circuits). "
                "Use .move() to position components with adequate separation.'"
            )
        if 'mirror_error' in categories:
            suggestions.append(
                "Add mirror instruction: 'Call mirror() on ComponentReference (after add_ref), "
                "never on Component directly.'"
            )
        
        return "\n".join(suggestions) if suggestions else "Review template for missing error prevention guidance."
    
    def _get_pilot_suggestion(self, gaps: List[Dict]) -> str:
        """Get suggestion for pilot improvements."""
        categories = [g['category'] for g in gaps]
        
        suggestions = []
        if 'syntax_error' in categories:
            suggestions.append("Add pilot check: 'Detect Unicode characters and invalid decimal literals.'")
        if 'mirror_error' in categories:
            suggestions.append("Add pilot check: 'Detect gf.components.xxx().mirror() pattern and flag as error.'")
        if 'spacing_violation' in categories:
            suggestions.append("Add pilot check: 'Verify spacing >= 20µm in .move() coordinates.'")
        if 'missing_route' in categories:
            suggestions.append("Add pilot check: 'Verify route_single() or route_bundle() calls exist for all connections.'")
        
        return "\n".join(suggestions) if suggestions else "Review pilot validator for missing pattern checks."
    
    def _get_injection_suggestion(self, gaps: List[Dict]) -> str:
        """Get suggestion for injection improvements."""
        categories = [g['category'] for g in gaps]
        
        suggestions = []
        if 'port_mismatch' in categories:
            suggestions.append(
                "Add port information: 'For each component, list available port names "
                "(e.g., mmi1x2: o1, o2, o3).'"
            )
        if 'sax_component_not_found' in categories:
            suggestions.append(
                "Add SAX indicator: 'Indicate which components have SAX models available.'"
            )
        if 'wrong_api' in categories:
            suggestions.append(
                "Add API examples: 'Include correct API usage examples for routing methods.'"
            )
        
        return "\n".join(suggestions) if suggestions else "Review component injection for missing information."
    
    def _calculate_robustness_score(
        self,
        template_coverage: Dict[str, bool],
        pilot_coverage: Dict[str, bool],
        injection_coverage: Dict[str, bool],
        gaps: List[Dict]
    ) -> float:
        """Calculate overall robustness score (0-1)."""
        # Count total coverage checks
        total_checks = 0
        passed_checks = 0
        
        # Template coverage
        for covered in template_coverage.values():
            total_checks += 1
            if covered:
                passed_checks += 1
        
        # Pilot coverage (only for pilot-catchable)
        for covered in pilot_coverage.values():
            if covered is not None:  # Only count pilot-catchable
                total_checks += 1
                if covered:
                    passed_checks += 1
        
        # Injection coverage (only for injection-relevant)
        for covered in injection_coverage.values():
            if covered is not None:  # Only count injection-relevant
                total_checks += 1
                if covered:
                    passed_checks += 1
        
        # Penalty for gaps
        gap_penalty = len(gaps) * 0.05  # 5% penalty per gap
        
        if total_checks == 0:
            return 0.0
        
        base_score = passed_checks / total_checks
        final_score = max(0.0, base_score - gap_penalty)
        
        return final_score
    
    def _assess_robustness(self, score: float) -> str:
        """Assess robustness level based on score."""
        if score >= 0.9:
            return "excellent"
        elif score >= 0.7:
            return "good"
        elif score >= 0.5:
            return "needs_improvement"
        else:
            return "poor"


