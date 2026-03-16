#!/usr/bin/env python3
"""
Quick optimization analysis using test_opt_efficiency_single.py results.
Generates CSV, JSON, and plots for before/after optimization comparison.
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from extract_opt_efficiency import run_optimization_on_sample, find_successful_samples, load_merged_metrics
from hf_inference_workflow.optimization_integration import OptimizationStage

OUTPUT_DIR = Path(__file__).parent / "output"
RESULTS_DIR = OUTPUT_DIR / "optimization_analysis"
RESULTS_DIR.mkdir(exist_ok=True)

def process_working_samples(max_samples: int = 20):
    """Process samples that are known to work (problem_1, simple circuits)."""
    print("Loading merged metrics...")
    merged_data = load_merged_metrics()
    
    print("Finding successful samples...")
    all_samples = find_successful_samples(merged_data)
    
    # Filter for problem_1 (MZI - simple, known to work)
    problem_1_samples = [s for s in all_samples if s['problem_id'] == '1']
    
    print(f"Found {len(problem_1_samples)} problem_1 samples")
    print(f"Processing first {max_samples} samples...")
    
    optimizer = OptimizationStage()
    results = []
    
    for idx, sample in enumerate(problem_1_samples[:max_samples], 1):
        model = sample['model']
        phase = sample['phase']
        problem_id = sample['problem_id']
        sample_idx = sample['sample_idx']
        yaml_path = sample.get('yaml_path')
        
        if yaml_path is None or not yaml_path.exists():
            continue
        
        print(f"[{idx}/{min(max_samples, len(problem_1_samples))}] {model}/{phase}/problem_{problem_id}/sample_{sample_idx}")
        
        try:
            sample_info = {
                'yaml_path': yaml_path,
                'gds_path': sample.get('gds_path'),
                'circuit_type': f'problem_{problem_id}',
            }
            result = run_optimization_on_sample(sample_info, optimizer)
            
            if result:
                result.update({
                    'model': model,
                    'phase': phase,
                    'problem_id': problem_id,
                    'sample_idx': sample_idx,
                })
                results.append(result)
                print(f"  ✅ Loss: {result.get('circuit_loss_before_db', 'N/A'):.2f} → {result.get('circuit_loss_after_db', 'N/A'):.2f} dB")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    return results

def save_and_plot(results):
    """Save results and create plots."""
    if not results:
        print("No results to save!")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save CSV
    rows = []
    for r in results:
        rows.append({
            'model': r.get('model'),
            'phase': r.get('phase'),
            'problem_id': r.get('problem_id'),
            'sample_idx': r.get('sample_idx'),
            'device_loss_before_db': r.get('device_loss_db', 0.0),
            'device_loss_after_db': r.get('device_loss_db', 0.0),
            'circuit_loss_before_db': r.get('circuit_loss_before_db'),
            'circuit_loss_after_db': r.get('circuit_loss_after_db'),
            'total_loss_before_db': (r.get('circuit_loss_before_db', 0.0) + r.get('device_loss_db', 0.0)),
            'total_loss_after_db': (r.get('circuit_loss_after_db', 0.0) + r.get('device_loss_db', 0.0)),
            'improvement_db': r.get('improvement_db', 0.0),
            'opt_efficiency': r.get('opt_efficiency', 0.0),
        })
    
    df = pd.DataFrame(rows)
    csv_path = RESULTS_DIR / f"optimization_results_{timestamp}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n✅ Saved CSV: {csv_path}")
    
    # Save JSON
    json_path = RESULTS_DIR / f"optimization_results_{timestamp}.json"
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✅ Saved JSON: {json_path}")
    
    # Create plots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Optimization Results: Before vs After', fontsize=16, fontweight='bold')
    
    # 1. Circuit-level
    ax1 = axes[0, 0]
    before = df['circuit_loss_before_db'].dropna()
    after = df['circuit_loss_after_db'].dropna()
    ax1.scatter(before, after, alpha=0.6, s=50)
    max_val = max(before.max(), after.max()) if len(before) > 0 and len(after) > 0 else 10
    ax1.plot([0, max_val], [0, max_val], 'r--', label='No improvement')
    ax1.set_xlabel('Circuit Loss Before (dB)')
    ax1.set_ylabel('Circuit Loss After (dB)')
    ax1.set_title('Circuit-Level Optimization')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Total loss
    ax2 = axes[0, 1]
    total_before = df['total_loss_before_db'].dropna()
    total_after = df['total_loss_after_db'].dropna()
    ax2.scatter(total_before, total_after, alpha=0.6, s=50, color='green')
    max_val = max(total_before.max(), total_after.max()) if len(total_before) > 0 and len(total_after) > 0 else 10
    ax2.plot([0, max_val], [0, max_val], 'r--', label='No improvement')
    ax2.set_xlabel('Total Loss Before (dB)')
    ax2.set_ylabel('Total Loss After (dB)')
    ax2.set_title('Total Loss Optimization')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Improvement
    ax3 = axes[1, 0]
    improvement = df['improvement_db'].dropna()
    if len(improvement) > 0:
        ax3.hist(improvement, bins=20, alpha=0.7, color='purple', edgecolor='black')
        ax3.axvline(0, color='r', linestyle='--', label='No improvement')
        ax3.set_xlabel('Improvement (dB)')
        ax3.set_ylabel('Frequency')
        ax3.set_title('Improvement Distribution')
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Opt efficiency
    ax4 = axes[1, 1]
    opt_eff = df['opt_efficiency'].dropna()
    if len(opt_eff) > 0:
        ax4.hist(opt_eff, bins=20, alpha=0.7, color='orange', edgecolor='black')
        ax4.set_xlabel('Optimization Efficiency')
        ax4.set_ylabel('Frequency')
        ax4.set_title('Optimization Efficiency Distribution')
        ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plot_path = RESULTS_DIR / f"optimization_plots_{timestamp}.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved plot: {plot_path}")
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total samples: {len(df)}")
    print(f"Mean circuit loss before: {before.mean():.3f} dB")
    print(f"Mean circuit loss after:  {after.mean():.3f} dB")
    print(f"Mean improvement: {improvement.mean():.3f} dB")
    print(f"Samples improved: {(improvement > 0).sum()} / {len(df)}")
    print("="*80)
    
    return csv_path, json_path, plot_path

if __name__ == "__main__":
    results = process_working_samples(max_samples=20)
    if results:
        csv_path, json_path, plot_path = save_and_plot(results)
        print(f"\n📊 Data location: {RESULTS_DIR}")
        print(f"   CSV: {csv_path.name}")
        print(f"   JSON: {json_path.name}")
        print(f"   Plot: {plot_path.name}")

