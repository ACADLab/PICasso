#!/usr/bin/env python3
"""
Run 9-Problem Validation Test

This script runs a quick validation test on 9 representative problems
before executing the full 36-problem benchmark.

The 9 problems cover all complexity levels:
- Complexity 1 (Simple): Problems 1, 2, 10 (MZI, MZM, 2x2 Switch)
- Complexity 2 (Moderate): Problems 4, 7, 23 (QPSK, WDM, Ring Filter)
- Complexity 3 (Complex): Problems 5, 11, 20 (8-QAM, 4x4 Switch, Clements)

Usage:
    python run_9_problem_test.py
    
Expected runtime: ~15-30 minutes with Pass@3 (9 problems × 3 samples = 27 generations)

Monitor progress with benchmark_monitoring.ipynb
"""

import sys
import os
from pathlib import Path
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import config and override with test settings
from hf_inference_workflow import config

# Override to use test problems
config.PROBLEMS_FILE = PROJECT_ROOT / "test_problems.txt"
config.SAMPLES_PER_PROBLEM = 3  # Pass@3

# Clear previous test results to avoid confusion
RAW_CSV = config.CSV_OUTPUT_DIR / "raw_llm_results.csv"
FRAMEWORK_CSV = config.CSV_OUTPUT_DIR / "framework_results.csv"

if RAW_CSV.exists():
    print(f"Removing previous test results: {RAW_CSV}")
    RAW_CSV.unlink()
if FRAMEWORK_CSV.exists():
    print(f"Removing previous test results: {FRAMEWORK_CSV}")
    FRAMEWORK_CSV.unlink()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.OUTPUT_DIR / "test_9_problems.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print("=" * 70)
print("PICASSO 9-PROBLEM VALIDATION TEST")
print("=" * 70)
print(f"Problems File: {config.PROBLEMS_FILE}")
print(f"Samples per Problem: {config.SAMPLES_PER_PROBLEM}")
print(f"Total Samples: 9 problems × {config.SAMPLES_PER_PROBLEM} samples = {9 * config.SAMPLES_PER_PROBLEM}")
print(f"Max Retries: {config.MAX_RETRY_ATTEMPTS}")
print(f"Auto-Correction: {'✅ Enabled' if config.ENABLE_AUTO_CORRECTION else '❌ Disabled'}")
print(f"Two-Phase Tracking: {'✅ Enabled' if config.ENABLE_TWO_PHASE_TRACKING else '❌ Disabled'}")
print("=" * 70)
print()
print("TEST COVERAGE:")
print("  Complexity 1: MZI, MZM, 2x2 Switch")
print("  Complexity 2: QPSK, WDM Multiplexer, Ring Filter")
print("  Complexity 3: 8-QAM, 4x4 Crossbar, Clements 4x4")
print("=" * 70)
print()
print("💡 TIP: Monitor progress in real-time with benchmark_monitoring.ipynb")
print("=" * 70)
print()

# Verify test problems file exists
if not config.PROBLEMS_FILE.exists():
    logger.error(f"Test problems file not found: {config.PROBLEMS_FILE}")
    logger.error("Run this script from the project root directory.")
    sys.exit(1)

# Count problems in file
with open(config.PROBLEMS_FILE, 'r') as f:
    problem_count = f.read().count("Problem ")

if problem_count != 9:
    logger.warning(f"Expected 9 problems, found {problem_count} in {config.PROBLEMS_FILE}")

print(f"✅ Found {problem_count} problems in test file")
print()
print("Starting test run...")
print("=" * 70)
print()

# Run gen_data_validated with test problems
from hf_inference_workflow.gen_data_validated import main

try:
    exit_code = main()
    
    print()
    print("=" * 70)
    print("TEST COMPLETE!")
    print("=" * 70)
    print()
    print("📊 Results saved to:")
    print(f"  Raw LLM (Phase 1): {RAW_CSV}")
    print(f"  Framework (Phase 2): {FRAMEWORK_CSV}")
    print()
    print("📈 Analyze results with:")
    print("  1. Open benchmark_monitoring.ipynb")
    print("  2. Run: plot_comparison()")
    print("=" * 70)
    
    sys.exit(exit_code)
    
except KeyboardInterrupt:
    print()
    print("=" * 70)
    print("⚠️ Test interrupted by user")
    print("=" * 70)
    print()
    print("Partial results may be available in:")
    print(f"  {config.CSV_OUTPUT_DIR}")
    sys.exit(1)
    
except Exception as e:
    logger.error(f"Test failed with error: {e}", exc_info=True)
    print()
    print("=" * 70)
    print("❌ TEST FAILED")
    print("=" * 70)
    print()
    print(f"Error: {e}")
    print()
    print("Check logs for details:")
    print(f"  {config.OUTPUT_DIR / 'test_9_problems.log'}")
    sys.exit(1)


