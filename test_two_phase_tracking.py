#!/usr/bin/env python3
"""
Quick test of two-phase tracking system.
Tests with just Problem 4 (MZM) with k=3 samples.
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
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_RESTARTS
)

def main():
    print("="*70)
    print("TWO-PHASE TRACKING TEST")
    print("="*70)
    print("\nTesting with Problem 4 (MZM), k=3 samples\n")

    # Load problems
    problems = load_problems(str(PROBLEMS_FILE))

    # Use Problem 4 (MZM)
    idx, title, body = problems[3]  # Problem 4 is index 3

    print(f"Problem {idx}: {title}")
    print(f"Description: {body[:100]}...\n")

    # Initialize components
    agent = HFInferenceAgent()
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)
    optimizer = OptimizationStage(
        enable_optimization=ENABLE_OPTIMIZATION,
        max_iter=OPTIMIZATION_MAX_ITER,
        n_restarts=OPTIMIZATION_RESTARTS
    )
    loss_validator = LossTargetValidator()

    # Clear previous results
    RAW_LLM_RESULTS.clear()
    FRAMEWORK_RESULTS.clear()

    # Generate k=3 samples
    k = 3
    print(f"Generating {k} samples...\n")

    for sample in range(k):
        print(f"\n{'='*70}")
        print(f"SAMPLE {sample + 1}/{k}")
        print(f"{'='*70}")

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

        print(f"\nSample {sample + 1} Result: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
        print(f"Retries used: {result['retry_attempts']}")

    # Save results
    print(f"\n{'='*70}")
    print("SAVING RESULTS")
    print(f"{'='*70}")
    save_two_phase_results()

    # Verify files created
    from pathlib import Path
    output_dir = Path("hf_inference_workflow/output/results")

    files_to_check = [
        "raw_llm_results.csv",
        "framework_results.csv",
        "comparison_metrics.json"
    ]

    print(f"\n{'='*70}")
    print("VERIFICATION")
    print(f"{'='*70}")
    for filename in files_to_check:
        filepath = output_dir / filename
        if filepath.exists():
            print(f"✅ {filename} created ({filepath.stat().st_size} bytes)")
        else:
            print(f"❌ {filename} NOT created")

    print(f"\n{'='*70}")
    print("TEST COMPLETE")
    print(f"{'='*70}")
    print("\n✅ You can now run the notebook:")
    print("   jupyter notebook demo_pass_at_k_benchmarking.ipynb")
    print("\n📊 Results saved in:")
    print(f"   {output_dir}/raw_llm_results.csv")
    print(f"   {output_dir}/framework_results.csv")
    print(f"   {output_dir}/comparison_metrics.json")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
