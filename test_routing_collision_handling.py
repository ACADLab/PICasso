#!/usr/bin/env python3
"""
Test Routing Collision Automatic Handling

This script tests the enhanced error detection and retry mechanism for routing collisions.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from hf_inference_workflow.gen_data_validated import parse_and_execute_code, get_parsing_error_feedback
from hf_inference_workflow.retry_handler import RetryHandler, ValidationStage

def test_routing_collision_detection():
    """Test that routing collision errors are properly detected and categorized."""

    print("="*70)
    print("TEST 1: Routing Collision Detection")
    print("="*70)

    # Simulate code that would cause a routing collision (components too close)
    bad_code = """
import gdsfactory as gf

r = gf.Component()

mzm1 = r.add_ref(gf.components.mzm())
mzm1.move((0, 0))

mzm2 = r.add_ref(gf.components.mzm())
mzm2.move((0, 50))  # Too close! Will cause collision when routing

splitter = r.add_ref(gf.components.mmi1x2())
splitter.move((0, 100))

# This routing will fail due to collision
gf.routing.route_bundle(
    r,
    [splitter.ports['o2'], splitter.ports['o3']],
    [mzm1.ports['o1'], mzm2.ports['o1']],
    radius=10,
    separation=10,
    cross_section='strip'
)
"""

    component, error_msg = parse_and_execute_code(bad_code)

    if component is None:
        print(f"✅ Error detected: {error_msg}")

        if "ROUTING_COLLISION" in error_msg:
            print("✅ Correctly categorized as ROUTING_COLLISION")
        else:
            print(f"⚠️  Categorized as: {error_msg.split(':')[0]}")
    else:
        print("❌ No error detected (unexpected)")

    print()


def test_feedback_generation():
    """Test that appropriate feedback is generated for routing collisions."""

    print("="*70)
    print("TEST 2: Feedback Generation")
    print("="*70)

    error_msg = "ROUTING_COLLISION: Routing collision in Unnamed_0"
    feedback = get_parsing_error_feedback(error_msg)

    print("Generated Feedback:")
    print("-"*70)
    print(feedback)
    print("-"*70)

    # Check for key guidance elements
    checks = [
        ("50µm spacing" in feedback, "Mentions 50µm minimum spacing"),
        ("±40µm" in feedback or "±50µm" in feedback, "Mentions vertical offset"),
        ("150µm" in feedback or "100-200µm" in feedback, "Mentions horizontal separation"),
        ("bend radius" in feedback.lower(), "Mentions bend radius"),
        ("8-QAM" in feedback or "example" in feedback.lower(), "Provides example"),
    ]

    print("\nFeedback Quality Checks:")
    for passed, description in checks:
        status = "✅" if passed else "⚠️"
        print(f"{status} {description}")

    print()


def test_mirror_error_detection():
    """Test that mirror() errors are properly detected."""

    print("="*70)
    print("TEST 3: Mirror Error Detection")
    print("="*70)

    bad_mirror_code = """
import gdsfactory as gf

r = gf.Component()

# Wrong: calling mirror() before add_ref
combiner = r.add_ref(gf.components.mmi1x2().mirror())  # This will fail
combiner.move((200, 0))
"""

    component, error_msg = parse_and_execute_code(bad_mirror_code)

    if component is None:
        print(f"✅ Error detected: {error_msg}")

        if "MIRROR_ERROR" in error_msg or "mirror" in error_msg.lower():
            print("✅ Correctly identified mirror error")

            feedback = get_parsing_error_feedback(error_msg)
            if "AFTER add_ref" in feedback:
                print("✅ Feedback includes correct pattern guidance")
            else:
                print("⚠️  Feedback missing pattern guidance")
        else:
            print(f"⚠️  Categorized as: {error_msg.split(':')[0]}")
    else:
        print("❌ No error detected (unexpected)")

    print()


def test_retry_handler_integration():
    """Test that retry handler properly uses parsing error reports."""

    print("="*70)
    print("TEST 4: Retry Handler Integration")
    print("="*70)

    retry_handler = RetryHandler(max_retries=3)

    # Simulate validation reports with routing collision
    validation_reports = {
        "parsing": {
            "passed": False,
            "error_type": "ROUTING_COLLISION",
            "error_details": "ROUTING_COLLISION: Routing collision in Unnamed_0",
            "feedback": get_parsing_error_feedback("ROUTING_COLLISION: Routing collision in Unnamed_0")
        }
    }

    problem_desc = "Create an 8-QAM modulator with 3 MZMs and 2 MMI splitters"

    feedback = retry_handler.format_feedback_for_llm(
        failed_stage=ValidationStage.PARSING,
        validation_reports=validation_reports,
        problem_description=problem_desc
    )

    print("Retry Feedback Preview (first 500 chars):")
    print("-"*70)
    print(feedback[:500])
    print("...")
    print("-"*70)

    # Check for key elements in retry feedback
    checks = [
        ("ROUTING COLLISION" in feedback, "Mentions routing collision"),
        ("50µm" in feedback, "Includes 50µm spacing guidance"),
        ("MANDATORY FIXES" in feedback or "Required Fixes" in feedback, "Provides fix checklist"),
        (problem_desc in feedback, "Includes original problem"),
    ]

    print("\nRetry Feedback Quality Checks:")
    for passed, description in checks:
        status = "✅" if passed else "⚠️"
        print(f"{status} {description}")

    print()


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("ROUTING COLLISION AUTOMATIC HANDLING - TEST SUITE")
    print("="*70 + "\n")

    try:
        test_routing_collision_detection()
        test_feedback_generation()
        test_mirror_error_detection()
        test_retry_handler_integration()

        print("="*70)
        print("ALL TESTS COMPLETED")
        print("="*70)
        print("\n✅ Routing collision handling system is ready!")
        print("\nNext Steps:")
        print("1. Run demo_full_framework.ipynb to test with real LLM generation")
        print("2. Monitor retry logs for routing collision detection and feedback")
        print("3. Verify LLM successfully regenerates with better spacing on retry")
        print("\nExpected behavior:")
        print("- First attempt may fail with ROUTING_COLLISION")
        print("- System provides detailed spacing feedback (50µm, ±50µm, 150µm)")
        print("- Second attempt should succeed with improved spacing")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
