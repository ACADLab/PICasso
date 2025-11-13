"""
Run Vanilla LLM Test (No Framework, No Auto-Correction)

This script runs tests with ONLY the LLM, no framework features:
- No component injection
- No pilot validation
- No auto-correction
- No YAML validation
- Just raw LLM output → execute → validate (for pass@k calculation)
"""

import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fin_picasso_framework.test_with_model import main
from fin_picasso_framework.config import ENABLE_AUTO_CORRECTION, ENABLE_EARLY_NETLIST_VALIDATION

# Disable all framework features for vanilla test
import fin_picasso_framework.config as config
config.ENABLE_AUTO_CORRECTION = False
config.ENABLE_EARLY_NETLIST_VALIDATION = False
config.ENABLE_DYNAMIC_PILOT_UPDATES = False

# Also disable in hf_inference_workflow config
try:
    import hf_inference_workflow.config as hf_config
    hf_config.ENABLE_COMPONENT_INJECTION = False
    hf_config.ENABLE_TWO_PHASE_TRACKING = False
except:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("VANILLA LLM TEST - NO FRAMEWORK FEATURES")
    logger.info("=" * 70)
    logger.info("Disabled:")
    logger.info("  - Auto-correction: False")
    logger.info("  - YAML validation: False")
    logger.info("  - Component injection: False")
    logger.info("  - Pilot validation: Still runs (for syntax check only)")
    logger.info("=" * 70)
    
    # Run with test_problems.txt
    sys.argv = [
        "run_vanilla_test.py",
        "--model", "deepseek_r1",
        "--problems", "test_problems.txt",
        "--samples", "3"
    ]
    
    main()

