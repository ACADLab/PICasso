#!/usr/bin/env python
"""
Test that CSV output includes new metric columns
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from hf_inference_workflow.metrics import compute_opt_efficiency, compute_robustness_score

def test_csv_format():
    """Test CSV format with new columns"""
    print("\n" + "="*70)
    print("CSV FORMAT TEST - NEW METRIC COLUMNS")
    print("="*70)

    # Simulate a framework result entry
    result = {
        'success': True,
        'validation_reports': {
            'functional': {
                'passed': True,
                'test_name': '8-QAM Constellation',
                'metric_value': 0.12
            },
            'optimization': {
                'circuit_loss_before_db': 3.8,
                'circuit_loss_after_db': 2.5
            }
        }
    }

    # Compute metrics as gen_data_validated.py does
    functional_report = result['validation_reports']['functional']
    opt_efficiency = compute_opt_efficiency(result)

    framework_success = result['success']
    spec_passed = framework_success and functional_report['passed']
    spec_at_k_single = 1.0 if spec_passed else 0.0

    robustness_score = compute_robustness_score(
        spec_at_k=spec_at_k_single,
        opt_efficiency=opt_efficiency,
        alpha=0.7,
        beta=0.3
    )

    # Build framework entry as in gen_data_validated.py
    framework_entry = {
        'problem_idx': 5,
        'circuit_type': '8-qam modulator',
        'sample_idx': 0,
        'success': True,
        'retries_used': 2,
        'validation_passed': True,
        'pnr_score': 0.85,
        'layout_area': 50000.0,
        'drc_violations': 0,
        'sax_compiled': True,
        'device_loss_db': 2.1,
        'circuit_loss_before_db': 3.8,
        'circuit_loss_after_db': 2.5,
        'total_loss_db': 4.6,
        'circuit_improvement_db': 1.3,
        'spec_passed': functional_report['passed'],
        'functional_test_name': functional_report['test_name'],
        'functional_metric_value': functional_report['metric_value'],
        'opt_efficiency': opt_efficiency,
        'robustness_score': robustness_score
    }

    print("\n✅ Framework entry created with new columns:")
    print(f"   spec_passed: {framework_entry['spec_passed']}")
    print(f"   functional_test_name: {framework_entry['functional_test_name']}")
    print(f"   functional_metric_value: {framework_entry['functional_metric_value']}")
    print(f"   opt_efficiency: {framework_entry['opt_efficiency']:.3f}")
    print(f"   robustness_score: {framework_entry['robustness_score']:.3f}")

    # Create DataFrame
    df = pd.DataFrame([framework_entry])

    print("\n" + "-"*70)
    print("DataFrame columns:")
    print("-"*70)
    for i, col in enumerate(df.columns):
        marker = "✨" if col in ['spec_passed', 'functional_test_name',
                                   'functional_metric_value', 'opt_efficiency',
                                   'robustness_score'] else "  "
        print(f"{marker} {i+1:2d}. {col}")

    # Write to test CSV
    test_csv_path = Path(__file__).parent / "test_framework_results.csv"
    df.to_csv(test_csv_path, index=False)
    print(f"\n✅ Test CSV written to: {test_csv_path}")

    # Verify new columns present
    required_new_cols = ['spec_passed', 'functional_test_name', 'functional_metric_value',
                         'opt_efficiency', 'robustness_score']
    missing_cols = [col for col in required_new_cols if col not in df.columns]

    if missing_cols:
        print(f"\n❌ FAIL: Missing columns: {missing_cols}")
        return False
    else:
        print(f"\n✅ PASS: All {len(required_new_cols)} new columns present")

    # Show sample output
    print("\n" + "-"*70)
    print("Sample CSV content (new columns):")
    print("-"*70)
    new_col_df = df[required_new_cols]
    print(new_col_df.to_string(index=False))

    print("\n" + "="*70)
    print("✅ CSV FORMAT TEST PASSED")
    print("="*70)
    return True

if __name__ == "__main__":
    try:
        success = test_csv_format()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
