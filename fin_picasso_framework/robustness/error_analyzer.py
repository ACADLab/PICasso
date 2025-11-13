"""
Error Pattern Analyzer

Analyzes failed cases to identify:
- Missing patterns in pilot
- Gaps in component injection
- Template weaknesses
- Common error categories
"""

import logging
from typing import Dict, List, Optional
from collections import Counter, defaultdict

from ..error_handling.error_extractor import ErrorExtractor, ErrorCategory

logger = logging.getLogger(__name__)


class ErrorAnalyzer:
    """
    Analyzes error patterns from failed cases.
    
    Identifies:
    - Missing patterns in pilot validator
    - Gaps in component injection
    - Template weaknesses
    - Common error categories and trends
    """
    
    def __init__(self):
        """Initialize error analyzer."""
        self.error_extractor = ErrorExtractor()
    
    def analyze_failed_cases(
        self,
        failed_cases: List[Dict]
    ) -> Dict:
        """
        Analyze failed cases to identify patterns and gaps.
        
        Args:
            failed_cases: List of failed case dictionaries with:
                - error_message: str
                - code: str
                - validation_report: Dict
                - failed_stage: str
                - problem_idx: int
                - sample_idx: int
                
        Returns:
            Analysis report with:
                - error_distribution: Distribution of error categories
                - stage_distribution: Distribution by failed stage
                - common_patterns: Most common error patterns
                - missing_pilot_patterns: Patterns not caught by pilot
                - injection_gaps: Gaps in component injection
                - template_weaknesses: Template weaknesses identified
                - recommendations: Recommendations for improvement
        """
        logger.info(f"Analyzing {len(failed_cases)} failed cases")
        
        # Extract error information
        error_infos = []
        for case in failed_cases:
            error_info = self.error_extractor.extract_error(
                error_message=case.get('error_message', ''),
                code=case.get('code'),
                validation_report=case.get('validation_report'),
                failed_stage=case.get('failed_stage')
            )
            error_infos.append(error_info)
        
        # Analyze distributions
        error_distribution = self._analyze_error_distribution(error_infos)
        stage_distribution = self._analyze_stage_distribution(failed_cases)
        common_patterns = self._identify_common_patterns(error_infos)
        
        # Identify gaps
        missing_pilot_patterns = self._identify_missing_pilot_patterns(error_infos)
        injection_gaps = self._identify_injection_gaps(error_infos)
        template_weaknesses = self._identify_template_weaknesses(error_infos)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            error_distribution,
            missing_pilot_patterns,
            injection_gaps,
            template_weaknesses
        )
        
        return {
            'error_distribution': error_distribution,
            'stage_distribution': stage_distribution,
            'common_patterns': common_patterns,
            'missing_pilot_patterns': missing_pilot_patterns,
            'injection_gaps': injection_gaps,
            'template_weaknesses': template_weaknesses,
            'recommendations': recommendations,
            'total_cases': len(failed_cases)
        }
    
    def _analyze_error_distribution(self, error_infos: List[Dict]) -> Dict:
        """Analyze distribution of error categories."""
        categories = [e['category'] for e in error_infos]
        category_counts = Counter(categories)
        
        total = len(error_infos)
        
        distribution = {}
        for category, count in category_counts.most_common():
            distribution[category] = {
                'count': count,
                'percentage': (count / total) * 100 if total > 0 else 0
            }
        
        return distribution
    
    def _analyze_stage_distribution(self, failed_cases: List[Dict]) -> Dict:
        """Analyze distribution by failed stage."""
        stages = [case.get('failed_stage', 'unknown') for case in failed_cases]
        stage_counts = Counter(stages)
        
        total = len(failed_cases)
        
        distribution = {}
        for stage, count in stage_counts.most_common():
            distribution[stage] = {
                'count': count,
                'percentage': (count / total) * 100 if total > 0 else 0
            }
        
        return distribution
    
    def _identify_common_patterns(self, error_infos: List[Dict]) -> List[Dict]:
        """Identify most common error patterns."""
        # Group by category and extract patterns
        patterns_by_category = defaultdict(list)
        
        for error_info in error_infos:
            category = error_info['category']
            pattern = {
                'error_type': error_info['error_type'],
                'error_message': error_info['error_message'][:200],  # Truncate
                'code_snippet': error_info['code_snippet'][:200] if error_info['code_snippet'] else '',
                'severity': error_info['severity']
            }
            patterns_by_category[category].append(pattern)
        
        # Get most common patterns
        common_patterns = []
        for category, patterns in patterns_by_category.items():
            if patterns:
                common_patterns.append({
                    'category': category,
                    'frequency': len(patterns),
                    'examples': patterns[:3]  # Top 3 examples
                })
        
        # Sort by frequency
        common_patterns.sort(key=lambda x: x['frequency'], reverse=True)
        
        return common_patterns[:10]  # Top 10
    
    def _identify_missing_pilot_patterns(self, error_infos: List[Dict]) -> List[Dict]:
        """Identify error patterns that should be caught by pilot but aren't."""
        pilot_catchable = [
            ErrorCategory.SYNTAX_ERROR,
            ErrorCategory.MIRROR_ERROR,
            ErrorCategory.SPACING_VIOLATION,
            ErrorCategory.PORT_MISMATCH,
            ErrorCategory.MISSING_ROUTE,
            ErrorCategory.WRONG_API,
        ]
        
        missing_patterns = []
        for error_info in error_infos:
            try:
                category = ErrorCategory(error_info['category'])
                if category in pilot_catchable:
                    missing_patterns.append({
                        'category': error_info['category'],
                        'error_type': error_info['error_type'],
                        'prevention_rule': error_info['prevention_rule'],
                        'severity': error_info['severity']
                    })
            except ValueError:
                pass
        
        # Remove duplicates
        seen = set()
        unique_patterns = []
        for pattern in missing_patterns:
            key = (pattern['category'], pattern['error_type'])
            if key not in seen:
                seen.add(key)
                unique_patterns.append(pattern)
        
        return unique_patterns
    
    def _identify_injection_gaps(self, error_infos: List[Dict]) -> List[Dict]:
        """Identify gaps in component injection."""
        injection_relevant = [
            ErrorCategory.PORT_MISMATCH,
            ErrorCategory.SAX_COMPONENT_NOT_FOUND,
            ErrorCategory.PACKAGE_ERROR,
            ErrorCategory.WRONG_API,
        ]
        
        gaps = []
        for error_info in error_infos:
            try:
                category = ErrorCategory(error_info['category'])
                if category in injection_relevant:
                    gaps.append({
                        'category': error_info['category'],
                        'error_type': error_info['error_type'],
                        'suggestion': self._get_injection_suggestion_for_category(category),
                        'severity': error_info['severity']
                    })
            except ValueError:
                pass
        
        # Remove duplicates
        seen = set()
        unique_gaps = []
        for gap in gaps:
            key = gap['category']
            if key not in seen:
                seen.add(key)
                unique_gaps.append(gap)
        
        return unique_gaps
    
    def _identify_template_weaknesses(self, error_infos: List[Dict]) -> List[Dict]:
        """Identify template weaknesses."""
        weaknesses = []
        
        # Group by category
        category_errors = defaultdict(list)
        for error_info in error_infos:
            category_errors[error_info['category']].append(error_info)
        
        # Identify weaknesses
        for category, errors in category_errors.items():
            if len(errors) > 2:  # If category appears multiple times
                weaknesses.append({
                    'category': category,
                    'frequency': len(errors),
                    'suggestion': self._get_template_suggestion_for_category(category),
                    'severity': 'high' if len(errors) > 5 else 'medium'
                })
        
        return weaknesses
    
    def _get_injection_suggestion_for_category(self, category: ErrorCategory) -> str:
        """Get injection suggestion for error category."""
        suggestions = {
            ErrorCategory.PORT_MISMATCH: (
                "Add port names for each component in injection. "
                "Example: 'mmi1x2 has ports: o1 (input), o2, o3 (outputs)'"
            ),
            ErrorCategory.SAX_COMPONENT_NOT_FOUND: (
                "Indicate which components have SAX models. "
                "Example: 'mmi1x2: Has SAX model ✓'"
            ),
            ErrorCategory.PACKAGE_ERROR: (
                "Include correct component paths and API usage. "
                "Example: 'Use gf.components.mzis.mzm(), not mzm_bit1()'"
            ),
            ErrorCategory.WRONG_API: (
                "Include routing API examples. "
                "Example: 'Use gf.routing.route_single(r, port1, port2, ...)'"
            ),
        }
        
        return suggestions.get(category, "Review component injection for this error category.")
    
    def _get_template_suggestion_for_category(self, category: str) -> str:
        """Get template suggestion for error category."""
        suggestions = {
            'port_mismatch': (
                "Add explicit instruction: 'Always verify port names using component.ports.keys() "
                "before accessing ports.'"
            ),
            'missing_route': (
                "Add explicit instruction: 'All component connections MUST use route_single() or "
                "route_bundle(). Components placed but not routed will fail validation.'"
            ),
            'spacing_violation': (
                "Add spacing guidelines: 'Minimum spacing 20µm (100µm for complex circuits). "
                "Check all .move() coordinates for adequate separation.'"
            ),
            'mirror_error': (
                "Add mirror instruction: 'Call mirror() on ComponentReference (after add_ref), "
                "never on Component directly.'"
            ),
            'syntax_error': (
                "Add syntax guidelines: 'Use only ASCII characters. No Unicode (µm, ×, Δ). "
                "Use valid Python float literals.'"
            ),
        }
        
        return suggestions.get(category, "Review template for this error category.")
    
    def _generate_recommendations(
        self,
        error_distribution: Dict,
        missing_pilot_patterns: List[Dict],
        injection_gaps: List[Dict],
        template_weaknesses: List[Dict]
    ) -> List[Dict]:
        """Generate recommendations for improvement."""
        recommendations = []
        
        # Top error categories
        top_errors = sorted(
            error_distribution.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:5]
        
        if top_errors:
            recommendations.append({
                'type': 'priority_fix',
                'priority': 'high',
                'description': 'Focus on top error categories',
                'details': [
                    {
                        'category': cat,
                        'count': info['count'],
                        'percentage': info['percentage']
                    }
                    for cat, info in top_errors
                ]
            })
        
        # Missing pilot patterns
        if missing_pilot_patterns:
            recommendations.append({
                'type': 'pilot_enhancement',
                'priority': 'high',
                'description': 'Add pilot checks for missing patterns',
                'details': missing_pilot_patterns[:5]  # Top 5
            })
        
        # Injection gaps
        if injection_gaps:
            recommendations.append({
                'type': 'injection_enhancement',
                'priority': 'medium',
                'description': 'Enhance component injection',
                'details': injection_gaps[:5]  # Top 5
            })
        
        # Template weaknesses
        if template_weaknesses:
            recommendations.append({
                'type': 'template_enhancement',
                'priority': 'medium',
                'description': 'Strengthen template guidance',
                'details': template_weaknesses[:5]  # Top 5
            })
        
        return recommendations


