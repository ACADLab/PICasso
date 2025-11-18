#!/usr/bin/env python3
"""
Script to analyze and compare vanilla vs picasso phases in metrics CSV files.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

def analyze_csv(csv_path: Path):
    """Analyze a metrics CSV file and show vanilla vs picasso comparison."""
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return
    
    print(f"\n{'='*70}")
    print(f"Analyzing: {csv_path.name}")
    print(f"{'='*70}\n")
    
    phase_data = defaultdict(lambda: {
        'samples': 0,
        'problems': set(),
        'passed': 0,
        'structural_pass': 0,
        'functional_pass': 0,
        'drc_passed': 0,
        'spec_at_k_structural': [],
        'spec_at_k_full': [],
    })
    
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            phase = row['phase']
            problem_id = row['problem_id']
            
            phase_data[phase]['samples'] += 1
            phase_data[phase]['problems'].add(problem_id)
            
            if row.get('structural_pass', 'False').lower() == 'true':
                phase_data[phase]['structural_pass'] += 1
            if row.get('functional_pass', 'False').lower() == 'true':
                phase_data[phase]['functional_pass'] += 1
            if row.get('drc_passed', 'False').lower() == 'true':
                phase_data[phase]['drc_passed'] += 1
            if row.get('passed', 'False').lower() == 'true':
                phase_data[phase]['passed'] += 1
            
            # Collect spec@k values (problem-level, so we'll get duplicates)
            try:
                spec_k_struct = float(row.get('spec_at_k_structural', 0))
                spec_k_full = float(row.get('spec_at_k_full', 0))
                if spec_k_struct > 0:
                    phase_data[phase]['spec_at_k_structural'].append(spec_k_struct)
                if spec_k_full > 0:
                    phase_data[phase]['spec_at_k_full'].append(spec_k_full)
            except:
                pass
    
    # Print results
    for phase in ['vanilla', 'picasso']:
        if phase not in phase_data:
            print(f"⚠️  {phase.upper()} phase: NOT FOUND")
            continue
        
        data = phase_data[phase]
        num_problems = len(data['problems'])
        num_samples = data['samples']
        
        print(f"📊 {phase.upper()} Phase:")
        print(f"   Problems: {num_problems}")
        print(f"   Samples: {num_samples}")
        print(f"   Passed: {data['passed']}/{num_samples} ({data['passed']/num_samples*100:.1f}%)" if num_samples > 0 else "   Passed: 0")
        print(f"   Structural Pass: {data['structural_pass']}/{num_samples} ({data['structural_pass']/num_samples*100:.1f}%)" if num_samples > 0 else "   Structural Pass: 0")
        print(f"   Functional Pass: {data['functional_pass']}/{num_samples} ({data['functional_pass']/num_samples*100:.1f}%)" if num_samples > 0 else "   Functional Pass: 0")
        print(f"   DRC Pass: {data['drc_passed']}/{num_samples} ({data['drc_passed']/num_samples*100:.1f}%)" if num_samples > 0 else "   DRC Pass: 0")
        
        if data['spec_at_k_structural']:
            avg_spec_k_struct = sum(set(data['spec_at_k_structural'])) / len(set(data['spec_at_k_structural']))
            print(f"   Avg Spec@k Structural: {avg_spec_k_struct:.3f}")
        if data['spec_at_k_full']:
            avg_spec_k_full = sum(set(data['spec_at_k_full'])) / len(set(data['spec_at_k_full']))
            print(f"   Avg Spec@k Full: {avg_spec_k_full:.3f}")
        print()
    
    # Comparison if both phases exist
    if 'vanilla' in phase_data and 'picasso' in phase_data:
        print(f"{'='*70}")
        print("📈 COMPARISON (PICasso - Vanilla):")
        print(f"{'='*70}\n")
        
        v = phase_data['vanilla']
        p = phase_data['picasso']
        
        v_samples = v['samples']
        p_samples = p['samples']
        
        if v_samples > 0 and p_samples > 0:
            v_pass_rate = v['passed'] / v_samples * 100
            p_pass_rate = p['passed'] / p_samples * 100
            print(f"Pass Rate: {p_pass_rate:.1f}% - {v_pass_rate:.1f}% = {p_pass_rate - v_pass_rate:+.1f}%")
            
            v_struct_rate = v['structural_pass'] / v_samples * 100
            p_struct_rate = p['structural_pass'] / p_samples * 100
            print(f"Structural Pass Rate: {p_struct_rate:.1f}% - {v_struct_rate:.1f}% = {p_struct_rate - v_struct_rate:+.1f}%")
            
            v_func_rate = v['functional_pass'] / v_samples * 100
            p_func_rate = p['functional_pass'] / p_samples * 100
            print(f"Functional Pass Rate: {p_func_rate:.1f}% - {v_func_rate:.1f}% = {p_func_rate - v_func_rate:+.1f}%")
        print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_metrics_csv.py <path_to_metrics.csv>")
        print("\nExample:")
        print("  python analyze_metrics_csv.py gd_picasso/output/deepseek-v3-api_results/metrics.csv")
        sys.exit(1)
    
    csv_path = Path(sys.argv[1])
    analyze_csv(csv_path)


