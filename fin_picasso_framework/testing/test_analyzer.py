"""
Test Results Analyzer

Analyzes test results comparing SAX-only vs enhanced validation.
Generates metrics on framework effectiveness.
"""

import logging
from typing import Dict, List
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class TestResultsAnalyzer:
    """Analyzes test results."""

    def __init__(self):
        """Initialize test analyzer."""
        self.analysis_results = {}

    def analyze(self, test_results: Dict) -> Dict:
        """
        Analyze test results.

        Args:
            test_results: Test results dictionary

        Returns:
            Analysis dictionary
        """
        analysis = {
            "total_tests": test_results.get("total_tests", 0),
            "sax_pass_rate": 0.0,
            "enhanced_pass_rate": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "catch_rate": test_results.get("catch_rate", 0.0),
            "effectiveness_metrics": {},
        }
        
        total = analysis["total_tests"]
        if total > 0:
            analysis["sax_pass_rate"] = test_results.get("sax_only_passed", 0) / total
            analysis["enhanced_pass_rate"] = test_results.get("enhanced_passed", 0) / total
        
        # Calculate false positive/negative rates
        false_data_total = (
            test_results.get("routing_drc_caught", 0) +
            test_results.get("routing_drc_missed", 0)
        )
        
        if false_data_total > 0:
            analysis["false_negative_rate"] = (
                test_results.get("routing_drc_missed", 0) / false_data_total
            )
        
        # Effectiveness metrics
        analysis["effectiveness_metrics"] = {
            "routing_issues_caught": test_results.get("routing_drc_caught", 0),
            "routing_issues_missed": test_results.get("routing_drc_missed", 0),
            "improvement_over_sax": (
                analysis["enhanced_pass_rate"] - analysis["sax_pass_rate"]
            ),
        }
        
        self.analysis_results = analysis
        return analysis

    def generate_metrics_report(self) -> str:
        """
        Generate metrics report.

        Returns:
            Formatted metrics report
        """
        if not self.analysis_results:
            return "No analysis results available"
        
        analysis = self.analysis_results
        
        lines = []
        lines.append("=" * 70)
        lines.append("FRAMEWORK EFFECTIVENESS METRICS")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Total tests: {analysis['total_tests']}")
        lines.append(f"SAX pass rate: {analysis['sax_pass_rate']:.1%}")
        lines.append(f"Enhanced pass rate: {analysis['enhanced_pass_rate']:.1%}")
        lines.append(f"Improvement over SAX: {analysis['effectiveness_metrics']['improvement_over_sax']:.1%}")
        lines.append("")
        lines.append(f"Catch rate: {analysis['catch_rate']:.1%}")
        lines.append(f"False negative rate: {analysis['false_negative_rate']:.1%}")
        lines.append("")
        lines.append("Routing/DRC Issues:")
        lines.append(f"  Caught: {analysis['effectiveness_metrics']['routing_issues_caught']}")
        lines.append(f"  Missed: {analysis['effectiveness_metrics']['routing_issues_missed']}")
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)

    def save_results(self, output_path: Path):
        """
        Save analysis results to file.

        Args:
            output_path: Path to save results
        """
        try:
            with open(output_path, 'w') as f:
                json.dump(self.analysis_results, f, indent=2)
            logger.info(f"Saved analysis results to {output_path}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")


