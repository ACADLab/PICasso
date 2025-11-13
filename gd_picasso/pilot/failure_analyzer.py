"""
Analyze failed examples to extract error patterns.

Purpose: Analyze all failed examples (PhIDO + converted Python) to extract error patterns,
categorize errors, and generate statistics for base pilot prompt creation.
"""

import yaml
import logging
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class FailureAnalyzer:
    """Analyze failed examples to extract error patterns."""

    def __init__(self):
        """Initialize analyzer."""
        self.error_patterns = defaultdict(int)
        self.error_examples = defaultdict(list)
        self.error_categories = {
            'syntax': [],
            'component': [],
            'port': [],
            'routing': [],
            'spacing': [],
            'drc': [],
        }

    def analyze_yaml_file(self, yaml_path: str, error_type: Optional[str] = None):
        """
        Analyze a YAML file for errors.

        Args:
            yaml_path: Path to YAML file
            error_type: Known error type (if available)
        """
        try:
            with open(yaml_path, 'r') as f:
                content = f.read()
                yaml_data = yaml.safe_load(content)

            # Check for syntax errors
            if '_error' in yaml_data:
                error_msg = yaml_data['_error']
                self._categorize_error('syntax', error_msg, yaml_path)

            # Check for missing required fields
            required_fields = ['instances', 'placements']
            for field in required_fields:
                if field not in yaml_data:
                    self._categorize_error('syntax', f'Missing required field: {field}', yaml_path)

            # Check for component errors
            if 'instances' in yaml_data:
                for inst_name, inst_data in yaml_data['instances'].items():
                    if 'component' not in inst_data:
                        self._categorize_error('component', f'Missing component name in {inst_name}', yaml_path)

            # Check for routing errors
            if 'routes' not in yaml_data or 'optical' not in yaml_data.get('routes', {}):
                # Missing routes - this is a common error
                if 'instances' in yaml_data and len(yaml_data['instances']) > 1:
                    self._categorize_error('routing', 'Missing routes section', yaml_path)

            # Check for spacing errors
            if 'placements' in yaml_data:
                placements = yaml_data['placements']
                positions = []
                for inst_name, placement in placements.items():
                    if isinstance(placement, dict):
                        x = placement.get('x', 0)
                        y = placement.get('y', 0)
                        positions.append((inst_name, x, y))

                # Check spacing between components
                for i, (name1, x1, y1) in enumerate(positions):
                    for name2, x2, y2 in positions[i+1:]:
                        distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                        if 0 < distance < 200:  # Less than 200um spacing
                            self._categorize_error('spacing', f'Components {name1} and {name2} too close ({distance:.1f}um)', yaml_path)

        except yaml.YAMLError as e:
            self._categorize_error('syntax', f'YAML syntax error: {str(e)}', yaml_path)
        except Exception as e:
            logger.error(f"Error analyzing {yaml_path}: {e}")

    def analyze_python_code(self, python_code: str, error_type: Optional[str] = None):
        """
        Analyze Python code for errors.

        Args:
            python_code: Python code string
            error_type: Known error type (if available)
        """
        # Check for common Python errors
        if error_type:
            self._categorize_error(error_type, error_type, 'python_code')

        # Check for missing routes
        if 'route_single' not in python_code and 'route_bundle' not in python_code:
            if 'add_ref' in python_code or '<<' in python_code:
                # Components are created but not routed
                self._categorize_error('routing', 'Missing route_single() or route_bundle() calls', 'python_code')

        # Check for Unicode characters
        unicode_chars = re.findall(r'[^\x00-\x7F]', python_code)
        if unicode_chars:
            self._categorize_error('syntax', f'Unicode characters found: {set(unicode_chars)}', 'python_code')

        # Check for wrong routing method
        if 'add_route(' in python_code:
            self._categorize_error('routing', 'Using add_route() instead of route_single() or route_bundle()', 'python_code')

    def _categorize_error(self, category: str, error_msg: str, source: str):
        """
        Categorize an error.

        Args:
            category: Error category (syntax, component, port, routing, spacing, drc)
            error_msg: Error message
            source: Source file or identifier
        """
        self.error_patterns[error_msg] += 1
        self.error_examples[error_msg].append(source)
        
        if category in self.error_categories:
            self.error_categories[category].append({
                'error': error_msg,
                'source': source
            })

    def get_error_statistics(self) -> Dict:
        """
        Get error statistics.

        Returns:
            Dictionary with error statistics
        """
        return {
            'total_errors': sum(self.error_patterns.values()),
            'unique_errors': len(self.error_patterns),
            'error_frequencies': dict(sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True)),
            'error_categories': {
                cat: len(errors) for cat, errors in self.error_categories.items()
            },
            'top_errors': dict(list(sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True))[:10])
        }

    def get_error_examples(self, error_msg: str) -> List[str]:
        """
        Get examples of a specific error.

        Args:
            error_msg: Error message

        Returns:
            List of source files/examples with this error
        """
        return self.error_examples.get(error_msg, [])


if __name__ == "__main__":
    # Example usage
    analyzer = FailureAnalyzer()
    
    # Analyze a YAML file
    # analyzer.analyze_yaml_file("example.yaml")
    
    # Get statistics
    stats = analyzer.get_error_statistics()
    print(f"Total errors: {stats['total_errors']}")
    print(f"Unique errors: {stats['unique_errors']}")
    print(f"Top errors: {stats['top_errors']}")

