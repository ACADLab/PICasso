#!/usr/bin/env python3
"""
Run full benchmarking on all 36 problems from Pic_set.txt

This script:
1. Generates k=3 samples for each of 36 circuits (108 total)
2. Tracks Phase 1 (vanilla LLM) vs Phase 2 (framework) separately
3. Uses pilot validator for pre-execution error prevention
4. Includes two-level optimization (device + circuit)
5. Computes novel metrics (Spec@k, Opt-Efficiency, Robustness)
6. Saves comprehensive results with all metrics
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
from tqdm import tqdm

from hf_inference_workflow.gen_data_validated import (
    load_problems,
    generate_with_validation,
    save_two_phase_results,
    RAW_LLM_RESULTS,
    FRAMEWORK_RESULTS
)
from hf_inference_workflow.hf_api_client import HFInferenceAgent
from hf_inference_workflow.validators import PNRValidator, DRCValidator, SAXValidator
from hf_inference_workflow.validators.pilot_validator import PilotValidator
from hf_inference_workflow.retry_handler import AdaptiveRetryHandler
from hf_inference_workflow.optimization_integration import OptimizationStage
from hf_inference_workflow.validators.loss_target_validator import LossTargetValidator
from hf_inference_workflow.config import (
    PYTHON_PROMPT_TEMPLATE,
    MAX_RETRY_ATTEMPTS,
    ENABLE_OPTIMIZATION,
    ENABLE_DEVICE_OPTIMIZATION,
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_RESTARTS,
    SAMPLES_PER_PROBLEM
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("\n" + "=" * 70)
    print("PICASSO FULL BENCHMARK - 36 PROBLEMS")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Problem Set: Pic_set.txt (36 problems)")
    print(f"  Samples per Problem: {SAMPLES_PER_PROBLEM}")
    print(f"  Total Samples: {36 * SAMPLES_PER_PROBLEM}")
    print(f"  Device Optimization (Level 1): {ENABLE_DEVICE_OPTIMIZATION}")
    print(f"  Circuit Optimization (Level 2): {ENABLE_OPTIMIZATION}")
    print(f"  Max Iterations: {OPTIMIZATION_MAX_ITER}")
    print(f"  Random Restarts: {OPTIMIZATION_RESTARTS}")
    print(f"  Max Retries: {MAX_RETRY_ATTEMPTS}")
    print()

    # Load all 36 problems from Pic_set.txt
    pic_set_path = Path(__file__).parent / "Pic_set.txt"
    if not pic_set_path.exists():
        print(f"❌ ERROR: Pic_set.txt not found at {pic_set_path}")
        sys.exit(1)

    problems = load_problems(str(pic_set_path))
    print(f"✅ Loaded {len(problems)} problems from Pic_set.txt")

    # Group by complexity
    complexity_counts = {}
    for idx, title, body in problems:
        # Extract complexity from title
        if "Complexity 1" in body:
            complexity_counts[1] = complexity_counts.get(1, 0) + 1
        elif "Complexity 2" in body:
            complexity_counts[2] = complexity_counts.get(2, 0) + 1
        elif "Complexity 3" in body:
            complexity_counts[3] = complexity_counts.get(3, 0) + 1

    print(f"\nComplexity breakdown:")
    for level in sorted(complexity_counts.keys()):
        print(f"  Complexity {level}: {complexity_counts[level]} problems")

    print(f"\nProblems to benchmark:")
    for idx, title, _ in problems[:10]:
        print(f"  Problem {idx}: {title}")
    if len(problems) > 10:
        print(f"  ... and {len(problems) - 10} more")
    print()

    # Initialize validators and optimizer
    print("Initializing validators...")
    agent = HFInferenceAgent()
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    pilot_validator = PilotValidator()  # NEW: Pre-execution validation
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)

    # Two-level optimization
    optimizer = OptimizationStage(
        enable_optimization=ENABLE_OPTIMIZATION,
        enable_device_optimization=ENABLE_DEVICE_OPTIMIZATION,
        max_iter=OPTIMIZATION_MAX_ITER,
        n_restarts=OPTIMIZATION_RESTARTS
    )
    loss_validator = LossTargetValidator()

    print("✅ All validators initialized (including pilot validator)")
    print()

    # Clear previous results
    RAW_LLM_RESULTS.clear()
    FRAMEWORK_RESULTS.clear()

    # Generate samples for all problems
    total_samples = len(problems) * SAMPLES_PER_PROBLEM
    current_sample = 0

    # Track statistics
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'pilot_violations': 0,
        'by_complexity': {1: {'total': 0, 'success': 0},
                          2: {'total': 0, 'success': 0},
                          3: {'total': 0, 'success': 0}}
    }

    print("=" * 70)
    print("STARTING BENCHMARK")
    print("=" * 70)
    print()

    with tqdm(total=total_samples, desc="Overall Progress") as pbar:
        for idx, title, body in problems:
            # Extract complexity
            complexity = 1
            if "Complexity 2" in body:
                complexity = 2
            elif "Complexity 3" in body:
                complexity = 3

            print("\n" + "=" * 70)
            print(f"PROBLEM {idx}: {title} [Complexity {complexity}]")
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
                        pilot_validator=pilot_validator,  # NEW
                        retry_handler=retry_handler,
                        problem_idx=idx,
                        sample_idx=sample,
                        optimizer=optimizer,
                        loss_validator=loss_validator,
                        circuit_type=title.lower()
                    )

                    # Update statistics
                    stats['total'] += 1
                    stats['by_complexity'][complexity]['total'] += 1

                    if result['success']:
                        stats['success'] += 1
                        stats['by_complexity'][complexity]['success'] += 1
                        status = "✅ SUCCESS"
                    else:
                        stats['failed'] += 1
                        status = "❌ FAILED"

                    # Track pilot violations
                    if 'pilot_violations' in result and len(result['pilot_violations']) > 0:
                        stats['pilot_violations'] += len(result['pilot_violations'])

                    print(f"\nResult: {status} (retries: {result['retry_attempts']})")

                    # Show metrics if available
                    if result.get('device_loss_db') is not None:
                        print(f"  Device Loss: {result['device_loss_db']:.2f} dB")
                    if result.get('total_loss_db') is not None:
                        print(f"  Total Loss:  {result['total_loss_db']:.2f} dB")

                    # Show pilot violations
                    if 'pilot_violations' in result and len(result['pilot_violations']) > 0:
                        print(f"  Pilot Violations: {len(result['pilot_violations'])}")

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"\n❌ ERROR: {e}")
                    logger.error(f"Problem {idx}, Sample {sample} failed", exc_info=True)
                    stats['failed'] += 1
                    stats['by_complexity'][complexity]['total'] += 1

                pbar.update(1)

                # Periodic save every 10 samples
                if current_sample % 10 == 0:
                    print(f"\n💾 Auto-saving results (sample {current_sample}/{total_samples})...")
                    save_two_phase_results()

    # Final save
    print("\n" + "=" * 70)
    print("SAVING FINAL RESULTS")
    print("=" * 70)
    save_two_phase_results()

    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"\nTotal Samples: {stats['total']}")
    if stats['total'] > 0:
        print(f"  ✅ Success: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
        print(f"  ❌ Failed:  {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
        print(f"  ⚠️  Pilot Violations Caught: {stats['pilot_violations']}")
    else:
        print("  ⚠️  No samples were processed!")

    print(f"\nBy Complexity:")
    for level in sorted(stats['by_complexity'].keys()):
        data = stats['by_complexity'][level]
        if data['total'] > 0:
            success_rate = data['success'] / data['total'] * 100
            print(f"  Level {level}: {data['success']}/{data['total']} ({success_rate:.1f}%)")

    print("\n📊 Results saved in:")
    print("   hf_inference_workflow/output/results/raw_llm_results.csv")
    print("   hf_inference_workflow/output/results/framework_results.csv (with NEW metric columns)")
    print("   hf_inference_workflow/output/results/comparison_metrics.json (with Spec@k, Opt-Efficiency, Robustness)")

    print("\n📈 View results:")
    print("   jupyter notebook python_csv_checks.ipynb")

    # Pilot statistics
    pilot_stats = pilot_validator.get_statistics()
    print("\n🛡️  Pilot Validator Statistics:")
    print(f"   Total errors caught: {pilot_stats['total_errors_caught']}")
    print(f"   Rules created: {pilot_stats['rules_created']}")
    if pilot_stats['error_history']:
        print("   Error breakdown:")
        for error_type, count in pilot_stats['error_history'].items():
            print(f"     {error_type}: {count}")

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
