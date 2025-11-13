"""
Run Framework Tests

Extracts test cases from notebooks and runs them through the framework.
Validates that framework catches 100% of routing/DRC issues that SAX misses.
"""

import sys
import logging
from pathlib import Path

# Check for required dependencies first
try:
    import gdsfactory as gf
    _gdsfactory_available = True
except ImportError as e:
    _gdsfactory_available = False
    print("=" * 70)
    print("ERROR: gdsfactory is not installed or not accessible!")
    print("=" * 70)
    print(f"Import error: {e}")
    print("Please install gdsfactory to run the framework tests.")
    print("You can install it with: pip install gdsfactory")
    print("Or activate the correct conda environment.")
    print("=" * 70)
    sys.exit(1)

# Add parent directory to path for absolute imports
# This allows the script to be run from either the framework directory or parent directory
framework_dir = Path(__file__).parent
parent_dir = framework_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fin_picasso_framework.testing.test_extractor import TestExtractor
from fin_picasso_framework.testing.test_framework import FrameworkTestSuite
from fin_picasso_framework.testing.test_analyzer import TestResultsAnalyzer
from fin_picasso_framework.config import (
    HF_MODELS_RESULTS_DIR,
    OPENAI_LLMS_DIR,
    TEST_OUTPUT_DIR,
    PARSE_FIRST_PASS,
    IDENTIFY_FALSE_DATA,
    TARGET_CATCH_RATE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run framework tests."""
    logger.info("=" * 70)
    logger.info("PICASSO FRAMEWORK TEST SUITE")
    logger.info("=" * 70)
    
    # Extract test cases
    logger.info("\nStep 1: Extracting test cases from notebooks...")
    extractor = TestExtractor(
        notebooks_dir=HF_MODELS_RESULTS_DIR,
        openai_llms_dir=OPENAI_LLMS_DIR
    )
    
    test_cases = extractor.extract_all(parse_first_pass=PARSE_FIRST_PASS)
    logger.info(f"Extracted {len(test_cases)} test cases")
    
    # Identify false data cases
    if IDENTIFY_FALSE_DATA:
        logger.info("\nStep 2: Identifying false data cases (pass SAX but fail routing/DRC)...")
        false_data_cases = extractor.identify_false_data_cases(test_cases)
        logger.info(f"Found {len(false_data_cases)} false data cases")
        
        # Use false data cases for testing
        test_cases_to_run = false_data_cases
    else:
        test_cases_to_run = test_cases
    
    if not test_cases_to_run:
        logger.warning("No test cases to run!")
        return
    
    # Run framework tests
    logger.info("\nStep 3: Running framework tests...")
    test_suite = FrameworkTestSuite()
    results = test_suite.run_tests(test_cases_to_run)
    
    # Generate report
    logger.info("\nStep 4: Generating test report...")
    report = test_suite.generate_report()
    print("\n" + report)
    
    # Analyze results
    logger.info("\nStep 5: Analyzing results...")
    analyzer = TestResultsAnalyzer()
    analysis = analyzer.analyze(results)
    metrics_report = analyzer.generate_metrics_report()
    print("\n" + metrics_report)
    
    # Save results
    results_file = TEST_OUTPUT_DIR / "test_results.json"
    analyzer.save_results(results_file)
    logger.info(f"\nResults saved to {results_file}")
    
    # Check if meets target
    if results.get("meets_target", False):
        logger.info("\n✅ Framework meets target catch rate!")
        logger.info(f"   Catch rate: {results.get('catch_rate', 0):.1%}")
        logger.info(f"   Target: {TARGET_CATCH_RATE:.1%}")
    else:
        logger.warning("\n⚠️ Framework does not meet target catch rate")
        logger.warning(f"   Catch rate: {results.get('catch_rate', 0):.1%}")
        logger.warning(f"   Target: {TARGET_CATCH_RATE:.1%}")
        logger.warning("   Framework needs refinement before LLM integration")


if __name__ == "__main__":
    main()

