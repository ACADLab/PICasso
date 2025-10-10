"""
Run validation test with real LLM and show results in real-time

This script:
1. Tests HF API connection
2. Generates designs for challenging problems
3. Shows validation flow for each design
4. Displays final results table
"""

import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*70)
print("PICASSO VALIDATION WORKFLOW - LIVE TEST")
print("="*70)
print()

# Test 1: Check configuration
print("Step 1: Checking configuration...")
try:
    from hf_inference_workflow.config import HF_API_TOKEN, DEFAULT_MODEL, SAMPLES_PER_PROBLEM

    if "ENTER_YOUR" in HF_API_TOKEN:
        print("  ❌ HF_API_TOKEN not configured!")
        print("  Please edit config.py or set environment variable")
        sys.exit(1)

    print(f"  ✅ HF_API_TOKEN configured (length: {len(HF_API_TOKEN)})")
    print(f"  ✅ Model: {DEFAULT_MODEL}")
    print(f"  ✅ Samples per problem: {SAMPLES_PER_PROBLEM}")
except Exception as e:
    print(f"  ❌ Configuration error: {e}")
    sys.exit(1)

# Test 2: Test API connection
print("\nStep 2: Testing HuggingFace API connection...")
try:
    from hf_inference_workflow.hf_api_client import HFInferenceAgent

    agent = HFInferenceAgent()
    print("  ✅ API client initialized")

    # Quick test
    print("  Testing with simple query...")
    response = agent.ASK_LLM(
        "You are a helpful assistant.",
        "Respond with exactly: 'API connection successful'"
    )

    if response:
        print(f"  ✅ API response received!")
        print(f"     Response: {response[:100]}...")
    else:
        print("  ⚠️  Empty response (but no error)")

except Exception as e:
    print(f"  ❌ API connection failed: {e}")
    print("\n  Troubleshooting:")
    print("  1. Check HF_API_TOKEN is valid")
    print("  2. Check internet connection")
    print("  3. Verify you have access to the model")
    sys.exit(1)

# Test 3: Load problems
print("\nStep 3: Loading test problems...")
try:
    from hf_inference_workflow.gen_data_validated import load_problems

    problems = load_problems("test_challenging_problems.txt")
    print(f"  ✅ Loaded {len(problems)} problems:")
    for idx, title, body in problems:
        print(f"     {idx}. {title}")
except Exception as e:
    print(f"  ❌ Failed to load problems: {e}")
    sys.exit(1)

# Test 4: Run generation for first problem only (quick test)
print("\n" + "="*70)
print("Step 4: Running validation workflow (Problem 1 only)")
print("="*70)
print()

try:
    from hf_inference_workflow.gen_data_validated import (
        generate_with_validation,
        PNRValidator,
        DRCValidator,
        SAXValidator,
        AdaptiveRetryHandler
    )
    from hf_inference_workflow.config import PYTHON_PROMPT_TEMPLATE

    # Initialize validators
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    retry_handler = AdaptiveRetryHandler(max_retries=3)

    # Run for first problem only
    idx, title, body = problems[0]

    print(f"Problem: {title}")
    print(f"Description: {body[:200]}...")
    print()

    # Generate 1 sample
    print("Generating design with validation...")
    print("-" * 70)

    result = generate_with_validation(
        agent=agent,
        prompt=PYTHON_PROMPT_TEMPLATE,
        problem_desc=body,
        pnr_validator=pnr_validator,
        drc_validator=drc_validator,
        sax_validator=sax_validator,
        retry_handler=retry_handler,
        problem_idx=idx,
        sample_idx=0
    )

    # Display results
    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)

    print(f"\n✅ Success: {result['success']}")
    print(f"🔄 Retry Attempts: {result['retry_attempts']}")

    if result['failed_stage']:
        print(f"❌ Failed Stage: {result['failed_stage'].value}")

    print(f"\nValidation Stages:")
    print(f"  P&R: {'✅ PASS' if result['pnr_passed'] else '❌ FAIL'}")
    print(f"  DRC: {'✅ PASS' if result['drc_passed'] else '❌ FAIL'}")
    print(f"  SAX: {'✅ PASS' if result['sax_passed'] else '❌ FAIL'}")

    if result['gds_path']:
        print(f"\n📁 GDS File: {result['gds_path']}")

    print(f"\n📝 Generated Code Preview:")
    print("-" * 70)
    code_preview = result['code'][:500] if result['code'] else "No code generated"
    print(code_preview)
    if len(result['code']) > 500:
        print("...")
    print("-" * 70)

    # Show detailed validation reports
    if 'validation_reports' in result:
        reports = result['validation_reports']

        if 'pnr' in reports:
            print(f"\nP&R Validation Details:")
            pnr = reports['pnr']
            if 'metrics' in pnr:
                for key, val in pnr['metrics'].items():
                    if isinstance(val, float):
                        print(f"  • {key}: {val:.2f}")
                    else:
                        print(f"  • {key}: {val}")

            if pnr.get('errors'):
                print(f"  Errors:")
                for err in pnr['errors']:
                    print(f"    ❌ {err}")

            if pnr.get('warnings'):
                print(f"  Warnings:")
                for warn in pnr['warnings'][:3]:  # Show first 3
                    print(f"    ⚠️  {warn}")

    print("\n" + "="*70)
    if result['success']:
        print("🎉 TEST SUCCESSFUL!")
        print("   The workflow generated a validated design that passes:")
        print("   ✅ P&R (no overlap, proper spacing)")
        print("   ✅ DRC (fabrication rules)")
        print("   ✅ SAX (functional correctness)")
    else:
        print("⚠️  TEST FAILED")
        print(f"   Failed at stage: {result.get('failed_stage', 'unknown')}")
        print("   This shows the validation is working - rejecting bad designs!")
    print("="*70)

except Exception as e:
    print(f"\n❌ Error during generation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("NEXT STEPS")
print("="*70)
print("\nTo run the full test with all problems:")
print("  1. Double-click: RUN_VALIDATION_TEST.bat")
print("  2. Or run: python gen_data_validated.py --problems test_challenging_problems.txt")
print("\nThis will generate 6 designs (3 problems × 2 samples each)")
print("Estimated time: 10-15 minutes")
print("Results saved to: output/results/test_results_challenging.csv")
print("="*70)
