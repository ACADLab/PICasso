#!/usr/bin/env python3
"""
Run full two-phase benchmarking on all 5 circuits.

This script:
1. Generates k=3 samples for each of 5 circuits (15 total)
2. Tracks Phase 1 (vanilla LLM) vs Phase 2 (framework) separately
3. Includes two-level optimization (device + circuit)
4. Calculates pass@3 for each circuit type
5. Saves comprehensive results with loss breakdown
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from hf_inference_workflow.gen_data_validated import (
    load_problems,
    generate_with_validation,
    save_two_phase_results,
    RAW_LLM_RESULTS,
    FRAMEWORK_RESULTS
)
from hf_inference_workflow.hf_api_client import HFInferenceAgent
from hf_inference_workflow.validators import PNRValidator, DRCValidator, SAXValidator
from hf_inference_workflow.retry_handler import AdaptiveRetryHandler
from hf_inference_workflow.optimization_integration import OptimizationStage
from hf_inference_workflow.validators.loss_target_validator import LossTargetValidator
from hf_inference_workflow.config import (
    PYTHON_PROMPT_TEMPLATE,
    PROBLEMS_FILE,
    MAX_RETRY_ATTEMPTS,
    ENABLE_OPTIMIZATION,
    ENABLE_DEVICE_OPTIMIZATION,
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_RESTARTS,
    SAMPLES_PER_PROBLEM
)

def main():
    print("=" * 70)
    print("PICASSO FULL BENCHMARKING TEST")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Samples per Problem: {SAMPLES_PER_PROBLEM}")
    print(f"  Device Optimization (Level 1): {ENABLE_DEVICE_OPTIMIZATION}")
    print(f"  Circuit Optimization (Level 2): {ENABLE_OPTIMIZATION}")
    print(f"  Max Iterations: {OPTIMIZATION_MAX_ITER}")
    print(f"  Random Restarts: {OPTIMIZATION_RESTARTS}")
    print()

    # Load all problems
    problems = load_problems(str(PROBLEMS_FILE))
    print(f"Loaded {len(problems)} problems:")
    for idx, title, _ in problems:
        print(f"  Problem {idx}: {title}")
    print()

    # Initialize validators and optimizer
    agent = HFInferenceAgent()
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)

    # Two-level optimization
    optimizer = OptimizationStage(
        enable_optimization=ENABLE_OPTIMIZATION,
        enable_device_optimization=ENABLE_DEVICE_OPTIMIZATION,
        max_iter=OPTIMIZATION_MAX_ITER,
        n_restarts=OPTIMIZATION_RESTARTS
    )
    loss_validator = LossTargetValidator()

    # Clear previous results
    RAW_LLM_RESULTS.clear()
    FRAMEWORK_RESULTS.clear()

    # Generate samples for all problems
    total_samples = len(problems) * SAMPLES_PER_PROBLEM
    current_sample = 0

    for idx, title, body in problems:
        print("\n" + "=" * 70)
        print(f"PROBLEM {idx}: {title}")
        print("=" * 70)

        for sample in range(SAMPLES_PER_PROBLEM):
            current_sample += 1
            print(f"\n[{current_sample}/{total_samples}] Sample {sample + 1}/{SAMPLES_PER_PROBLEM}")
            print("-" * 70)

            try:
                result = generate_with_validation(
                    agent=agent,
                    prompt=PYTHON_PROMPT_TEMPLATE,
                    problem_desc=body,
                    pnr_validator=pnr_validator,
                    drc_validator=drc_validator,
                    sax_validator=sax_validator,
                    retry_handler=retry_handler,
                    problem_idx=idx,
                    sample_idx=sample,
                    optimizer=optimizer,
                    loss_validator=loss_validator,
                    circuit_type=title.lower()
                )

                status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
                print(f"\nResult: {status} (retries: {result['retry_attempts']})")

                # Show loss breakdown if available
                if result.get('device_loss_db') is not None:
                    print(f"  Device Loss: {result['device_loss_db']:.2f} dB")
                if result.get('total_loss_db') is not None:
                    print(f"  Total Loss:  {result['total_loss_db']:.2f} dB")

            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                import traceback
                traceback.print_exc()

    # Save results
    print("\n" + "=" * 70)
    print("SAVING RESULTS")
    print("=" * 70)
    save_two_phase_results()

    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARKING COMPLETE")
    print("=" * 70)
    print(f"\nGenerated {total_samples} total samples across {len(problems)} problems")
    print("\n📊 Results saved in:")
    print("   hf_inference_workflow/output/results/raw_llm_results.csv")
    print("   hf_inference_workflow/output/results/framework_results.csv")
    print("   hf_inference_workflow/output/results/comparison_metrics.json")
    print("\n📈 View results:")
    print("   jupyter notebook demo_pass_at_k_benchmarking.ipynb")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmarking interrupted by user")
        print("Saving partial results...")
        save_two_phase_results()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Benchmarking failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
