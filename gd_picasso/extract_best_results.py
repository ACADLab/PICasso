#!/usr/bin/env python3
"""
Extract best optimized results for problems 13-20 from merged metrics JSON.
"""

import json
from pathlib import Path

# Load merged metrics
output_file = Path('output/merged_finished_metrics_20251117_011457.json')
with open(output_file) as f:
    data = json.load(f)

# Problems 13-20
problem_ids = [str(i) for i in range(13, 21)]

print('=' * 100)
print('BEST OPTIMIZED RESULTS FOR PROBLEMS 13-20')
print('=' * 100)
print()

results_summary = []

# Find best result for each problem across all models
for problem_id in problem_ids:
    print(f'\nPROBLEM {problem_id}:')
    print('-' * 100)
    
    best_result = None
    best_score = -1
    best_model = None
    best_phase = None
    
    # Check all models and phases
    for model_name in sorted(data.keys()):
        for phase in ['vanilla', 'picasso']:
            if phase in data[model_name] and problem_id in data[model_name][phase]:
                problem = data[model_name][phase][problem_id]
                summary = problem['summary']
                
                # Primary metric: robustness_score (best overall quality after optimization)
                # Fallback to spec_at_k_full if robustness_score is 0
                score = summary.get('robustness_score', 0)
                if score == 0:
                    score = summary.get('spec_at_k_full', 0)
                if score == 0:
                    score = summary.get('spec_at_k_structural', 0)
                
                # Also consider functional pass rate as tiebreaker
                func_rate = summary.get('functional_pass_rate', 0)
                combined_score = score + (func_rate * 0.2)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_result = summary
                    best_model = model_name
                    best_phase = phase
    
    if best_result:
        print(f'Best Model: {best_model} ({best_phase})')
        print(f'  Robustness Score: {best_result.get("robustness_score", 0):.4f}')
        print(f'  Spec@k Structural: {best_result.get("spec_at_k_structural", 0):.4f}')
        print(f'  Spec@k Full: {best_result.get("spec_at_k_full", 0):.4f}')
        print(f'  Spec@k: {best_result.get("spec_at_k", 0):.4f}')
        print(f'  Pass@k: {best_result.get("pass_at_k", 0):.4f}')
        print(f'  Structural Pass Rate: {best_result.get("structural_pass_rate", 0):.2%}')
        print(f'  Functional Pass Rate: {best_result.get("functional_pass_rate", 0):.2%}')
        print(f'  DRC Pass Rate: {best_result.get("drc_passed_rate", 0):.2%}')
        print(f'  LVS Pass Rate: {best_result.get("lvs_passed_rate", 0):.2%}')
        print(f'  Opt Efficiency: {best_result.get("opt_eff", 0):.4f}')
        print(f'  Robust Pass: {best_result.get("robust_pass", 0):.4f}')
        print(f'  Num Samples: {best_result.get("num_samples", 0)}')
        
        results_summary.append({
            'problem_id': problem_id,
            'model': best_model,
            'phase': best_phase,
            'robustness_score': best_result.get("robustness_score", 0),
            'spec_at_k_structural': best_result.get("spec_at_k_structural", 0),
            'spec_at_k_full': best_result.get("spec_at_k_full", 0),
            'structural_pass_rate': best_result.get("structural_pass_rate", 0),
            'functional_pass_rate': best_result.get("functional_pass_rate", 0),
            'opt_eff': best_result.get("opt_eff", 0),
        })
    else:
        print('  No results found')
        results_summary.append({
            'problem_id': problem_id,
            'model': None,
            'phase': None,
            'robustness_score': 0,
            'spec_at_k_structural': 0,
            'spec_at_k_full': 0,
            'structural_pass_rate': 0,
            'functional_pass_rate': 0,
            'opt_eff': 0,
        })

# Print summary table
print('\n' + '=' * 100)
print('SUMMARY TABLE')
print('=' * 100)
print(f'{"Problem":<10} {"Model":<25} {"Phase":<10} {"Robustness":<12} {"Spec@k Full":<12} {"Struct%":<10} {"Func%":<10} {"OptEff":<10}')
print('-' * 100)
for r in results_summary:
    model_str = r['model'] if r['model'] else 'N/A'
    phase_str = r['phase'] if r['phase'] else 'N/A'
    print(f"{r['problem_id']:<10} {model_str:<25} {phase_str:<10} {r['robustness_score']:<12.4f} {r['spec_at_k_full']:<12.4f} {r['structural_pass_rate']:<10.2%} {r['functional_pass_rate']:<10.2%} {r['opt_eff']:<10.4f}")

# Save to JSON
output_json = Path('output/best_results_problems_13-20.json')
with open(output_json, 'w') as f:
    json.dump(results_summary, f, indent=2)
print(f'\n✅ Results saved to: {output_json}')
