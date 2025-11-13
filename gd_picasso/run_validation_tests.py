"""
Run all framework validation tests.

This script runs all unit tests and integration tests to verify framework readiness.
"""

import unittest
import sys
from pathlib import Path

# Add gd_picasso to path
sys.path.insert(0, str(Path(__file__).parent))

def run_all_tests():
    """Run all validation tests."""
    # Discover and run all tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test modules
    test_modules = [
        'tests.test_yaml_pilot_validator',
        'tests.test_yaml_parser',
        'tests.test_drc_validator',
        'tests.test_lvs_validator',
        'tests.test_optimizers',
        'tests.test_framework_with_false_examples',
    ]
    
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
        except ImportError as e:
            print(f"⚠️  Could not import {module_name}: {e}")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed! Framework is ready for LLM testing.")
    else:
        print("\n❌ Some tests failed. Please fix issues before LLM testing.")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

