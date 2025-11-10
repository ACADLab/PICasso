"""
Test script for two-level optimization (device + circuit).

This script tests the complete two-level optimization pipeline:
  Level 1 (Device): Optimize component geometries to match target losses
  Level 2 (Circuit): Optimize phase shifters and couplings for minimum insertion loss

Expected output:
  - Device-level loss breakdown by component type
  - Circuit-level optimization (if tunable parameters exist)
  - Total loss = device loss + circuit loss
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from hf_inference_workflow.gen_data_validated import (
    load_problems,
    generate_with_validation
)
from hf_inference_workflow.hf_api_client import HFInferenceAgent
from hf_inference_workflow.validators import PNRValidator, DRCValidator, SAXValidator
from hf_inference_workflow.validators.loss_target_validator import LossTargetValidator
from hf_inference_workflow.optimization_integration import OptimizationStage
from hf_inference_workflow.retry_handler import AdaptiveRetryHandler
from hf_inference_workflow.config import (
    DEFAULT_MODEL,
    PYTHON_PROMPT_TEMPLATE,
    MAX_RETRY_ATTEMPTS,
    ENABLE_OPTIMIZATION,
    ENABLE_DEVICE_OPTIMIZATION,
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_RESTARTS,
    PROBLEMS_FILE
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Test two-level optimization on Problem 4 (MZM)."""

    print("=" * 70)
    print("TWO-LEVEL OPTIMIZATION TEST")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Device Optimization (Level 1): {ENABLE_DEVICE_OPTIMIZATION}")
    print(f"  Circuit Optimization (Level 2): {ENABLE_OPTIMIZATION}")
    print(f"  Optimization Iterations: {OPTIMIZATION_MAX_ITER}")
    print(f"  Random Restarts: {OPTIMIZATION_RESTARTS}")
    print()

    # Load problems
    problems = load_problems(PROBLEMS_FILE)

    # Use Problem 4 (Mach-Zehnder Modulator)
    problem_idx = 4
    problem = next((p for p in problems if p[0] == problem_idx), None)

    if not problem:
        logger.error(f"Problem {problem_idx} not found!")
        return

    idx, circuit_type, description = problem
    logger.info(f"Testing Problem {idx}: {circuit_type}")
    logger.info(f"Description: {description[:100]}...")

    # Initialize components
    agent = HFInferenceAgent(model_name=DEFAULT_MODEL)
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)

    # Initialize optimizer with two-level optimization
    optimizer = OptimizationStage(
        enable_optimization=ENABLE_OPTIMIZATION,
        enable_device_optimization=ENABLE_DEVICE_OPTIMIZATION,
        max_iter=OPTIMIZATION_MAX_ITER,
        n_restarts=OPTIMIZATION_RESTARTS
    )
    loss_validator = LossTargetValidator()

    # Generate one sample
    print("\n" + "=" * 70)
    print("GENERATING SAMPLE")
    print("=" * 70)

    result = generate_with_validation(
        agent=agent,
        prompt=PYTHON_PROMPT_TEMPLATE,
        problem_desc=description,
        pnr_validator=pnr_validator,
        drc_validator=drc_validator,
        sax_validator=sax_validator,
        retry_handler=retry_handler,
        problem_idx=idx,
        sample_idx=0,
        optimizer=optimizer,
        loss_validator=loss_validator,
        circuit_type=circuit_type
    )

    # Check results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    if result["success"]:
        print("✅ Generation successful!")
        print(f"  Retries used: {result['retry_attempts']}")

        if result.get("validation_reports", {}).get("optimization"):
            opt_result = result["validation_reports"]["optimization"]

            print("\n" + "-" * 70)
            print("OPTIMIZATION RESULTS")
            print("-" * 70)

            # Device-level results
            device_loss = result.get("device_loss_db")
            if device_loss is not None:
                print(f"\n✅ Level 1 (Device Geometries): {device_loss:.2f} dB")

                # Show component breakdown
                if opt_result.get("device_breakdown"):
                    print("  Component breakdown:")
                    for comp_type, count, loss_per_unit, total_loss in opt_result["device_breakdown"]:
                        print(f"    {count}× {comp_type}: {loss_per_unit:.3f} dB each = {total_loss:.3f} dB")

            # Circuit-level results
            circuit_before = result.get("circuit_loss_before_db")
            circuit_after = result.get("circuit_loss_after_db")
            circuit_improvement = result.get("circuit_improvement_db", 0.0)

            if circuit_after is not None:
                print(f"\n✅ Level 2 (Circuit Parameters):")
                if circuit_before is not None:
                    print(f"  Before: {circuit_before:.2f} dB")
                    print(f"  After:  {circuit_after:.2f} dB")
                    print(f"  Improvement: {circuit_improvement:+.2f} dB")
                else:
                    print(f"  Final: {circuit_after:.2f} dB")

            # Total loss
            total_loss = result.get("total_loss_db")
            if total_loss is not None:
                print(f"\n{'=' * 70}")
                print(f"TOTAL INSERTION LOSS: {total_loss:.2f} dB")
                if device_loss is not None:
                    print(f"  Device:  {device_loss:.2f} dB")
                if circuit_after is not None:
                    print(f"  Circuit: {circuit_after:.2f} dB")
                print(f"{'=' * 70}")
            else:
                print("\n⚠️  Total loss not calculated")
        else:
            print("\n⚠️  No optimization results available")
            if opt_result := result.get("validation_reports", {}).get("optimization"):
                print(f"  Error: {opt_result.get('error', 'Unknown error')}")
    else:
        print("❌ Generation failed!")
        print(f"  Failed stage: {result.get('failed_stage', 'Unknown')}")
        if result.get("parsing_error"):
            print(f"  Parsing error: {result['parsing_error']}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
