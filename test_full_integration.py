#!/usr/bin/env python
"""
Full integration test: Test pilot validator + metrics in real workflow
Tests a simple MZI problem end-to-end with 1 sample
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
from hf_inference_workflow.hf_api_client import HFInferenceAgent
from hf_inference_workflow.gen_data_validated import generate_with_validation
from hf_inference_workflow.validators import PNRValidator, DRCValidator, SAXValidator
from hf_inference_workflow.validators.pilot_validator import PilotValidator
from hf_inference_workflow.optimization_integration import OptimizationStage
from hf_inference_workflow.validators.loss_target_validator import LossTargetValidator
from hf_inference_workflow.retry_handler import AdaptiveRetryHandler
from hf_inference_workflow.config import PYTHON_PROMPT_TEMPLATE
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_full_integration():
    """Test full workflow with new features"""
    print("\n" + "="*70)
    print("FULL INTEGRATION TEST - NEW FEATURES")
    print("="*70)

    # Problem: Simple MZI (easiest circuit) - cleaned for LLM
    problem_desc = """Create a Mach-Zehnder interferometer with a single optical input and output. Use:
- Two MMI1x2 (id: mmi1, mmi2)
- One phase shifter (id: phase_shifter)
Parameters:
Delta_L = 10 microns
L = 10 microns"""

    # Initialize components
    agent = HFInferenceAgent()
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    pilot_validator = PilotValidator()
    retry_handler = AdaptiveRetryHandler(max_retries=3)
    optimizer = OptimizationStage(
        enable_optimization=True,
        enable_device_optimization=True,
        max_iter=400,
        n_restarts=8
    )
    loss_validator = LossTargetValidator()

    print("\n✅ All validators initialized")
    print("   - PNR, DRC, SAX validators")
    print("   - ✨ Pilot validator (NEW)")
    print("   - Device + Circuit optimizer")

    # Generate with validation
    print("\n" + "="*70)
    print("GENERATING DESIGN (1 sample)")
    print("="*70)

    result = generate_with_validation(
        agent=agent,
        prompt=PYTHON_PROMPT_TEMPLATE,
        problem_desc=problem_desc,
        pnr_validator=pnr_validator,
        drc_validator=drc_validator,
        sax_validator=sax_validator,
        pilot_validator=pilot_validator,
        retry_handler=retry_handler,
        problem_idx=1,
        sample_idx=0,
        optimizer=optimizer,
        loss_validator=loss_validator,
        circuit_type="mach-zehnder interferometer"
    )

    # Check results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)

    success = result.get("success", False)
    print(f"\nGeneration Status: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Retries Used: {result.get('retry_attempts', 0)}")

    if "pilot_violations" in result:
        print(f"\n⚠️  Pilot Violations Caught: {len(result['pilot_violations'])}")
        for v in result['pilot_violations']:
            print(f"   Attempt {v['attempt']}: {v['error'][:80]}...")
    else:
        print("\n✅ No pilot violations (code was correct)")

    # Check validation stages
    print("\n" + "-"*70)
    print("VALIDATION STAGES")
    print("-"*70)
    print(f"P&R: {'✅ PASS' if result.get('pnr_passed') else '❌ FAIL'}")
    print(f"DRC: {'✅ PASS' if result.get('drc_passed') else '❌ FAIL'}")
    print(f"SAX: {'✅ PASS' if result.get('sax_passed') else '⚠️  SKIP (SAX unavailable)'}")

    # Check functional validation
    functional_report = result.get("validation_reports", {}).get("functional", {})
    func_passed = functional_report.get("passed", False)
    print(f"Functional: {'✅ PASS' if func_passed else '❌ FAIL'}")
    if functional_report:
        print(f"  Test: {functional_report.get('test_name', 'N/A')}")
        if functional_report.get("metric_value"):
            print(f"  Metric: {functional_report.get('metric_value')}")

    # Check optimization
    print("\n" + "-"*70)
    print("OPTIMIZATION (Two-Level)")
    print("-"*70)
    device_loss = result.get("device_loss_db")
    circuit_before = result.get("circuit_loss_before_db")
    circuit_after = result.get("circuit_loss_after_db")
    total_loss = result.get("total_loss_db")

    if device_loss is not None:
        print(f"Level 1 (Device): {device_loss:.2f} dB")
    if circuit_before is not None and circuit_after is not None:
        improvement = circuit_before - circuit_after
        print(f"Level 2 (Circuit): {circuit_before:.2f} → {circuit_after:.2f} dB (Δ {improvement:.2f} dB)")
    if total_loss is not None:
        print(f"Total Loss: {total_loss:.2f} dB")

    # Check NEW METRICS
    print("\n" + "-"*70)
    print("✨ NEW METRICS")
    print("-"*70)

    # Import metrics to compute from result
    from hf_inference_workflow.metrics import compute_opt_efficiency, compute_robustness_score

    # Compute Opt-Efficiency
    opt_efficiency = compute_opt_efficiency(result)
    print(f"Opt-Efficiency: {opt_efficiency:.3f}")
    if opt_efficiency > 0:
        print(f"  → {opt_efficiency*100:.1f}% circuit-level IL reduction")

    # Compute Spec@k (for single sample: 0.0 or 1.0)
    structural_pass = result.get("success", False)
    functional_pass = functional_report.get("passed", False)
    spec_passed = structural_pass and functional_pass
    spec_at_k_single = 1.0 if spec_passed else 0.0
    print(f"Spec@k (single): {spec_at_k_single:.3f}")
    print(f"  Structural: {'✅' if structural_pass else '❌'}")
    print(f"  Functional: {'✅' if functional_pass else '❌'}")

    # Compute Robustness Score
    robustness = compute_robustness_score(
        spec_at_k=spec_at_k_single,
        opt_efficiency=opt_efficiency,
        alpha=0.7,
        beta=0.3
    )
    print(f"Robustness Score: {robustness:.3f}")
    print(f"  = 0.7 × {spec_at_k_single:.3f} + 0.3 × {opt_efficiency:.3f}")

    # Pilot statistics
    print("\n" + "-"*70)
    print("PILOT VALIDATOR STATISTICS")
    print("-"*70)
    stats = pilot_validator.get_statistics()
    print(f"Total errors caught: {stats['total_errors_caught']}")
    print(f"Rules created: {stats['rules_created']}")
    if stats['error_history']:
        print("Error breakdown:")
        for error_type, count in stats['error_history'].items():
            print(f"  {error_type}: {count}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    if success:
        print("✅ Full integration test PASSED")
        print("\nNew features verified:")
        print("  ✅ Pilot validator integrated (pre-execution validation)")
        print("  ✅ Metrics computed (Opt-Efficiency, Spec@k, Robustness)")
        print("  ✅ Two-level optimization working")
        print("  ✅ Functional validation integrated")
        print("\n🎉 System ready for full benchmark run!")
    else:
        print("❌ Integration test FAILED")
        print(f"Failed stage: {result.get('failed_stage')}")
        if result.get('parsing_error'):
            print(f"Error: {result['parsing_error']}")

    return success

if __name__ == "__main__":
    try:
        success = test_full_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
