#!/usr/bin/env python3
"""
Create comprehensive plots comparing Vanilla vs Picasso phases:
- Spec@k for k=1,2,3,4,5
- Initial loss values (before optimization)
- Device-level and circuit-level comparisons
- Optimization improvements
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import glob
import seaborn as sns
from typing import Dict, List, Tuple

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 10

OUTPUT_DIR = Path(__file__).parent / "output"
RESULTS_DIR = OUTPUT_DIR / "optimization_analysis"

def load_merged_metrics():
    """Load the most recent merged metrics JSON file."""
    merged_files = list(OUTPUT_DIR.glob("merged_finished_metrics_*.json"))
    if not merged_files:
        raise FileNotFoundError("No merged metrics JSON file found")
    
    latest_file = max(merged_files, key=lambda p: p.stat().st_mtime)
    print(f"Loading merged metrics from: {latest_file.name}")
    
    with open(latest_file) as f:
        return json.load(f)

def compute_spec_at_k_for_k_values(results: List[Dict], k_values: List[int] = [1,2,3,4,5]) -> Dict[int, float]:
    """Compute Spec@k for multiple k values."""
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from gd_picasso.metrics import estimate_pass_at_k
    
    # Count structurally valid samples (structural_pass = True)
    num_samples = len(results)
    num_correct = sum(1 for r in results if r.get('structural_pass', False))
    
    spec_at_k_dict = {}
    for k in k_values:
        spec_at_k_dict[k] = estimate_pass_at_k(num_samples, num_correct, k)
    
    return spec_at_k_dict

def extract_initial_loss_values(merged_data: Dict) -> pd.DataFrame:
    """Extract initial loss values from optimization results."""
    rows = []
    
    # Load optimization results if available
    opt_csv_files = list(RESULTS_DIR.glob("optimization_results_*.csv"))
    opt_data = None
    if opt_csv_files:
        latest_opt = max(opt_csv_files, key=lambda p: p.stat().st_mtime)
        opt_data = pd.read_csv(latest_opt)
        print(f"Loaded optimization data from: {latest_opt.name}")
    
    for model_name, model_data in merged_data.items():
        for phase in ['vanilla', 'picasso']:
            if phase not in model_data:
                continue
            
            problems = model_data[phase]
            for problem_id, problem_data in problems.items():
                if problem_id.endswith('_summary'):
                    continue
                
                summary = problem_data.get('summary', {})
                samples = problem_data.get('samples', [])
                
                # Get spec@k for k=1,2,3,4,5
                spec_at_k_dict = compute_spec_at_k_for_k_values(samples, k_values=[1,2,3,4,5])
                
                # Get initial loss from optimization data if available
                initial_circuit_loss = None
                initial_device_loss = None
                if opt_data is not None:
                    model_opt = opt_data[(opt_data['model'] == model_name) & 
                                        (opt_data['phase'] == phase) & 
                                        (opt_data['problem_id'] == str(problem_id))]
                    if len(model_opt) > 0:
                        initial_circuit_loss = model_opt['circuit_loss_before_db'].mean()
                        initial_device_loss = model_opt['device_loss_before_db'].mean()
                
                rows.append({
                    'model': model_name,
                    'phase': phase,
                    'problem_id': problem_id,
                    'spec_at_1': spec_at_k_dict.get(1, 0.0),
                    'spec_at_2': spec_at_k_dict.get(2, 0.0),
                    'spec_at_3': spec_at_k_dict.get(3, 0.0),
                    'spec_at_4': spec_at_k_dict.get(4, 0.0),
                    'spec_at_5': spec_at_k_dict.get(5, 0.0),
                    'structural_pass_rate': summary.get('structural_pass_rate', 0.0),
                    'functional_pass_rate': summary.get('functional_pass_rate', 0.0),
                    'drc_passed_rate': summary.get('drc_passed_rate', 0.0),
                    'initial_circuit_loss_db': initial_circuit_loss,
                    'initial_device_loss_db': initial_device_loss,
                    'num_samples': summary.get('num_samples', 0),
                    'structural_pass_count': summary.get('structural_pass_count', 0),
                })
    
    return pd.DataFrame(rows)

def create_vanilla_vs_picasso_plots(df: pd.DataFrame):
    """Create comprehensive vanilla vs picasso comparison plots."""
    
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(4, 3, hspace=0.35, wspace=0.3)
    
    # ========== ROW 1: Spec@k Comparison ==========
    
    # 1. Spec@k for k=1,2,3,4,5 - Vanilla vs Picasso
    ax1 = fig.add_subplot(gs[0, 0])
    k_values = [1, 2, 3, 4, 5]
    
    vanilla_spec = []
    picasso_spec = []
    
    for k in k_values:
        vanilla_k = df[df['phase'] == 'vanilla'][f'spec_at_{k}'].mean()
        picasso_k = df[df['phase'] == 'picasso'][f'spec_at_{k}'].mean()
        vanilla_spec.append(vanilla_k)
        picasso_spec.append(picasso_k)
    
    x = np.arange(len(k_values))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, vanilla_spec, width, label='Vanilla', color='lightcoral', edgecolor='black', linewidth=1.2)
    bars2 = ax1.bar(x + width/2, picasso_spec, width, label='Picasso', color='steelblue', edgecolor='black', linewidth=1.2)
    
    ax1.set_xlabel('k (Number of Samples)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Spec@k', fontsize=12, fontweight='bold')
    ax1.set_title('Spec@k Comparison: Vanilla vs Picasso\n(Structural Specification Satisfaction)', 
                  fontsize=13, fontweight='bold', pad=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f'k={k}' for k in k_values])
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax1.set_ylim([0, 1.1])
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=9)
    
    # 2. Spec@k Improvement (Picasso - Vanilla)
    ax2 = fig.add_subplot(gs[0, 1])
    improvement = [p - v for v, p in zip(vanilla_spec, picasso_spec)]
    colors = ['green' if imp > 0 else 'red' for imp in improvement]
    bars = ax2.bar(x, improvement, width=0.6, color=colors, edgecolor='black', linewidth=1.2, alpha=0.7)
    ax2.axhline(0, color='black', linestyle='-', linewidth=1)
    ax2.set_xlabel('k (Number of Samples)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Improvement (Picasso - Vanilla)', fontsize=12, fontweight='bold')
    ax2.set_title('Spec@k Improvement\n(Picasso vs Vanilla)', fontsize=13, fontweight='bold', pad=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f'k={k}' for k in k_values])
    ax2.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add value labels
    for bar, imp in zip(bars, improvement):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{imp:+.3f}', ha='center', va='bottom' if imp > 0 else 'top', fontsize=9, fontweight='bold')
    
    # 3. Spec@k by Model (k=3)
    ax3 = fig.add_subplot(gs[0, 2])
    model_comparison = df.groupby(['model', 'phase'])['spec_at_3'].mean().unstack(fill_value=0)
    if 'vanilla' in model_comparison.columns and 'picasso' in model_comparison.columns:
        x_pos = np.arange(len(model_comparison))
        width = 0.35
        bars1 = ax3.bar(x_pos - width/2, model_comparison['vanilla'], width, 
                       label='Vanilla', color='lightcoral', edgecolor='black', linewidth=1)
        bars2 = ax3.bar(x_pos + width/2, model_comparison['picasso'], width,
                       label='Picasso', color='steelblue', edgecolor='black', linewidth=1)
        ax3.set_xlabel('Model', fontsize=12, fontweight='bold')
        ax3.set_ylabel('Spec@3', fontsize=12, fontweight='bold')
        ax3.set_title('Spec@3 by Model\n(Vanilla vs Picasso)', fontsize=13, fontweight='bold', pad=10)
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(model_comparison.index, rotation=45, ha='right', fontsize=9)
        ax3.legend(fontsize=10)
        ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax3.set_ylim([0, 1.1])
    
    # ========== ROW 2: Initial Loss Values (Before Optimization) ==========
    
    # 4. Initial Circuit Loss: Vanilla vs Picasso
    ax4 = fig.add_subplot(gs[1, 0])
    vanilla_loss = df[(df['phase'] == 'vanilla') & (df['initial_circuit_loss_db'].notna())]['initial_circuit_loss_db']
    picasso_loss = df[(df['phase'] == 'picasso') & (df['initial_circuit_loss_db'].notna())]['initial_circuit_loss_db']
    
    if len(vanilla_loss) > 0 and len(picasso_loss) > 0:
        # Filter out 150 dB (false calculation)
        vanilla_loss = vanilla_loss[vanilla_loss < 100]
        picasso_loss = picasso_loss[picasso_loss < 100]
        
        ax4.scatter(vanilla_loss, picasso_loss, alpha=0.6, s=60, c='purple', edgecolors='black', linewidth=0.5)
        max_val = max(vanilla_loss.max(), picasso_loss.max()) if len(vanilla_loss) > 0 and len(picasso_loss) > 0 else 10
        ax4.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Equal', alpha=0.7)
        ax4.set_xlabel('Initial Circuit Loss - Vanilla (dB)', fontsize=12, fontweight='bold')
        ax4.set_ylabel('Initial Circuit Loss - Picasso (dB)', fontsize=12, fontweight='bold')
        ax4.set_title('Initial Circuit Loss Comparison\n(Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax4.legend(fontsize=10)
        ax4.grid(True, alpha=0.3, linestyle='--')
        ax4.set_aspect('equal', adjustable='box')
        
        # Add improvement annotation
        if len(vanilla_loss) > 0 and len(picasso_loss) > 0:
            mean_vanilla = vanilla_loss.mean()
            mean_picasso = picasso_loss.mean()
            improvement_pct = ((mean_vanilla - mean_picasso) / mean_vanilla * 100) if mean_vanilla > 0 else 0
            ax4.text(0.05, 0.95, f'Mean Vanilla: {mean_vanilla:.2f} dB\nMean Picasso: {mean_picasso:.2f} dB\nImprovement: {improvement_pct:.1f}%',
                    transform=ax4.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    # 5. Initial Loss Distribution
    ax5 = fig.add_subplot(gs[1, 1])
    if len(vanilla_loss) > 0 and len(picasso_loss) > 0:
        ax5.hist(vanilla_loss, bins=20, alpha=0.6, label='Vanilla', color='lightcoral', edgecolor='black', linewidth=1)
        ax5.hist(picasso_loss, bins=20, alpha=0.6, label='Picasso', color='steelblue', edgecolor='black', linewidth=1)
        ax5.set_xlabel('Initial Circuit Loss (dB)', fontsize=12, fontweight='bold')
        ax5.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax5.set_title('Initial Loss Distribution\n(Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax5.legend(fontsize=10)
        ax5.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 6. Initial Loss by Problem
    ax6 = fig.add_subplot(gs[1, 2])
    problem_loss = df[df['initial_circuit_loss_db'].notna()].groupby(['problem_id', 'phase'])['initial_circuit_loss_db'].mean().unstack(fill_value=0)
    if 'vanilla' in problem_loss.columns and 'picasso' in problem_loss.columns:
        # Filter out 150 dB
        problem_loss = problem_loss[(problem_loss['vanilla'] < 100) & (problem_loss['picasso'] < 100)]
        # Top 15 problems
        problem_loss = problem_loss.head(15)
        
        x_pos = np.arange(len(problem_loss))
        width = 0.35
        bars1 = ax6.bar(x_pos - width/2, problem_loss['vanilla'], width,
                       label='Vanilla', color='lightcoral', edgecolor='black', linewidth=1)
        bars2 = ax6.bar(x_pos + width/2, problem_loss['picasso'], width,
                       label='Picasso', color='steelblue', edgecolor='black', linewidth=1)
        ax6.set_xlabel('Problem ID', fontsize=12, fontweight='bold')
        ax6.set_ylabel('Mean Initial Circuit Loss (dB)', fontsize=12, fontweight='bold')
        ax6.set_title('Initial Loss by Problem\n(Top 15, Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax6.set_xticks(x_pos)
        ax6.set_xticklabels([f'P{p}' for p in problem_loss.index], rotation=45, ha='right', fontsize=9)
        ax6.legend(fontsize=10)
        ax6.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # ========== ROW 3: Structural Pass Rates ==========
    
    # 7. Structural Pass Rate Comparison
    ax7 = fig.add_subplot(gs[2, 0])
    vanilla_pass = df[df['phase'] == 'vanilla']['structural_pass_rate'].mean()
    picasso_pass = df[df['phase'] == 'picasso']['structural_pass_rate'].mean()
    
    bars = ax7.bar(['Vanilla', 'Picasso'], [vanilla_pass, picasso_pass], 
                   color=['lightcoral', 'steelblue'], edgecolor='black', linewidth=1.5, width=0.6)
    ax7.set_ylabel('Structural Pass Rate', fontsize=12, fontweight='bold')
    ax7.set_title('Structural Pass Rate\n(Vanilla vs Picasso)', fontsize=13, fontweight='bold', pad=10)
    ax7.set_ylim([0, 1.1])
    ax7.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax7.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # 8. DRC Pass Rate Comparison
    ax8 = fig.add_subplot(gs[2, 1])
    vanilla_drc = df[df['phase'] == 'vanilla']['drc_passed_rate'].mean()
    picasso_drc = df[df['phase'] == 'picasso']['drc_passed_rate'].mean()
    
    bars = ax8.bar(['Vanilla', 'Picasso'], [vanilla_drc, picasso_drc],
                   color=['lightcoral', 'steelblue'], edgecolor='black', linewidth=1.5, width=0.6)
    ax8.set_ylabel('DRC Pass Rate', fontsize=12, fontweight='bold')
    ax8.set_title('DRC Pass Rate\n(Vanilla vs Picasso)', fontsize=13, fontweight='bold', pad=10)
    ax8.set_ylim([0, 1.1])
    ax8.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax8.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # 9. Functional Pass Rate Comparison
    ax9 = fig.add_subplot(gs[2, 2])
    vanilla_func = df[df['phase'] == 'vanilla']['functional_pass_rate'].mean()
    picasso_func = df[df['phase'] == 'picasso']['functional_pass_rate'].mean()
    
    bars = ax9.bar(['Vanilla', 'Picasso'], [vanilla_func, picasso_func],
                   color=['lightcoral', 'steelblue'], edgecolor='black', linewidth=1.5, width=0.6)
    ax9.set_ylabel('Functional Pass Rate', fontsize=12, fontweight='bold')
    ax9.set_title('Functional Pass Rate\n(Vanilla vs Picasso)', fontsize=13, fontweight='bold', pad=10)
    ax9.set_ylim([0, 1.1])
    ax9.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax9.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # ========== ROW 4: Summary Statistics ==========
    
    # 10. Spec@k Line Plot
    ax10 = fig.add_subplot(gs[3, 0])
    ax10.plot(k_values, vanilla_spec, marker='o', linewidth=2, markersize=8, label='Vanilla', color='lightcoral')
    ax10.plot(k_values, picasso_spec, marker='s', linewidth=2, markersize=8, label='Picasso', color='steelblue')
    ax10.set_xlabel('k (Number of Samples)', fontsize=12, fontweight='bold')
    ax10.set_ylabel('Spec@k', fontsize=12, fontweight='bold')
    ax10.set_title('Spec@k Trend\n(k=1 to k=5)', fontsize=13, fontweight='bold', pad=10)
    ax10.set_xticks(k_values)
    ax10.set_xticklabels([f'k={k}' for k in k_values])
    ax10.legend(fontsize=11)
    ax10.grid(True, alpha=0.3, linestyle='--')
    ax10.set_ylim([0, 1.1])
    
    # 11. Sample Count Comparison
    ax11 = fig.add_subplot(gs[3, 1])
    vanilla_samples = df[df['phase'] == 'vanilla']['num_samples'].sum()
    picasso_samples = df[df['phase'] == 'picasso']['num_samples'].sum()
    vanilla_pass_count = df[df['phase'] == 'vanilla']['structural_pass_count'].sum()
    picasso_pass_count = df[df['phase'] == 'picasso']['structural_pass_count'].sum()
    
    x = ['Vanilla', 'Picasso']
    total = [vanilla_samples, picasso_samples]
    passed = [vanilla_pass_count, picasso_pass_count]
    
    x_pos = np.arange(len(x))
    width = 0.35
    bars1 = ax11.bar(x_pos - width/2, total, width, label='Total Samples', color='lightgray', edgecolor='black', linewidth=1)
    bars2 = ax11.bar(x_pos + width/2, passed, width, label='Structurally Passed', color='green', edgecolor='black', linewidth=1, alpha=0.7)
    ax11.set_ylabel('Count', fontsize=12, fontweight='bold')
    ax11.set_title('Sample Count Comparison', fontsize=13, fontweight='bold', pad=10)
    ax11.set_xticks(x_pos)
    ax11.set_xticklabels(x)
    ax11.legend(fontsize=10)
    ax11.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 12. Summary Statistics Table
    ax12 = fig.add_subplot(gs[3, 2])
    ax12.axis('off')
    
    # Create summary table
    summary_data = []
    summary_data.append(['Metric', 'Vanilla', 'Picasso', 'Improvement'])
    summary_data.append(['Spec@1', f'{vanilla_spec[0]:.3f}', f'{picasso_spec[0]:.3f}', f'{picasso_spec[0]-vanilla_spec[0]:+.3f}'])
    summary_data.append(['Spec@3', f'{vanilla_spec[2]:.3f}', f'{picasso_spec[2]:.3f}', f'{picasso_spec[2]-vanilla_spec[2]:+.3f}'])
    summary_data.append(['Spec@5', f'{vanilla_spec[4]:.3f}', f'{picasso_spec[4]:.3f}', f'{picasso_spec[4]-vanilla_spec[4]:+.3f}'])
    summary_data.append(['Structural Pass', f'{vanilla_pass:.3f}', f'{picasso_pass:.3f}', f'{picasso_pass-vanilla_pass:+.3f}'])
    summary_data.append(['DRC Pass', f'{vanilla_drc:.3f}', f'{picasso_drc:.3f}', f'{picasso_drc-vanilla_drc:+.3f}'])
    
    if len(vanilla_loss) > 0 and len(picasso_loss) > 0:
        mean_v = vanilla_loss.mean()
        mean_p = picasso_loss.mean()
        summary_data.append(['Mean Initial Loss', f'{mean_v:.2f} dB', f'{mean_p:.2f} dB', f'{mean_v-mean_p:+.2f} dB'])
    
    table = ax12.table(cellText=summary_data, cellLoc='center', loc='center',
                      colWidths=[0.4, 0.2, 0.2, 0.2])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Style improvement column
    for i in range(1, len(summary_data)):
        imp_val = summary_data[i][3]
        if '+' in imp_val and float(imp_val.replace('+', '')) > 0:
            table[(i, 3)].set_facecolor('#90EE90')  # Light green
        elif '-' in imp_val:
            table[(i, 3)].set_facecolor('#FFB6C1')  # Light red
    
    ax12.set_title('Summary Statistics', fontsize=13, fontweight='bold', pad=10)
    
    # Overall title
    fig.suptitle('Vanilla vs Picasso Phase Comparison\n(Spec@k, Initial Loss, and Pass Rates)', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    output_path = RESULTS_DIR / "vanilla_vs_picasso_comprehensive.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Saved comprehensive comparison plot to: {output_path}")
    
    return output_path

def create_spec_at_k_plot(df: pd.DataFrame):
    """Create focused Spec@k plot for k=1,2,3,4,5."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('Spec@k Comparison: Vanilla vs Picasso (k=1 to k=5)', fontsize=16, fontweight='bold')
    
    k_values = [1, 2, 3, 4, 5]
    
    # Left: Bar chart
    ax1 = axes[0]
    vanilla_spec = [df[df['phase'] == 'vanilla'][f'spec_at_{k}'].mean() for k in k_values]
    picasso_spec = [df[df['phase'] == 'picasso'][f'spec_at_{k}'].mean() for k in k_values]
    
    x = np.arange(len(k_values))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, vanilla_spec, width, label='Vanilla', color='lightcoral', edgecolor='black', linewidth=1.5)
    bars2 = ax1.bar(x + width/2, picasso_spec, width, label='Picasso', color='steelblue', edgecolor='black', linewidth=1.5)
    
    ax1.set_xlabel('k (Number of Samples)', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Spec@k', fontsize=13, fontweight='bold')
    ax1.set_title('Spec@k: Vanilla vs Picasso', fontsize=14, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f'k={k}' for k in k_values], fontsize=11)
    ax1.legend(fontsize=12, loc='upper left')
    ax1.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax1.set_ylim([0, 1.15])
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Right: Line plot
    ax2 = axes[1]
    ax2.plot(k_values, vanilla_spec, marker='o', linewidth=3, markersize=10, label='Vanilla', color='lightcoral', markerfacecolor='white', markeredgewidth=2)
    ax2.plot(k_values, picasso_spec, marker='s', linewidth=3, markersize=10, label='Picasso', color='steelblue', markerfacecolor='white', markeredgewidth=2)
    ax2.set_xlabel('k (Number of Samples)', fontsize=13, fontweight='bold')
    ax2.set_ylabel('Spec@k', fontsize=13, fontweight='bold')
    ax2.set_title('Spec@k Trend', fontsize=14, fontweight='bold', pad=15)
    ax2.set_xticks(k_values)
    ax2.set_xticklabels([f'k={k}' for k in k_values], fontsize=11)
    ax2.legend(fontsize=12, loc='upper left')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_ylim([0, 1.15])
    
    # Add value labels on points
    for k, v, p in zip(k_values, vanilla_spec, picasso_spec):
        ax2.text(k, v, f' {v:.3f}', va='bottom', ha='left', fontsize=9)
        ax2.text(k, p, f' {p:.3f}', va='bottom', ha='left', fontsize=9)
    
    plt.tight_layout()
    output_path = RESULTS_DIR / "vanilla_vs_picasso_spec_at_k.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Saved Spec@k plot to: {output_path}")
    
    return output_path

if __name__ == "__main__":
    print("=" * 80)
    print("VANILLA VS PICASSO COMPARISON PLOTS")
    print("=" * 80)
    
    # Load data
    merged_data = load_merged_metrics()
    df = extract_initial_loss_values(merged_data)
    
    print(f"\nLoaded data:")
    print(f"  Total rows: {len(df)}")
    print(f"  Models: {df['model'].nunique()}")
    print(f"  Problems: {df['problem_id'].nunique()}")
    print(f"  Vanilla samples: {len(df[df['phase'] == 'vanilla'])}")
    print(f"  Picasso samples: {len(df[df['phase'] == 'picasso'])}")
    
    # Create plots
    print("\n" + "=" * 80)
    print("CREATING PLOTS")
    print("=" * 80)
    
    comprehensive_path = create_vanilla_vs_picasso_plots(df)
    spec_at_k_path = create_spec_at_k_plot(df)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    for k in [1, 2, 3, 4, 5]:
        vanilla_k = df[df['phase'] == 'vanilla'][f'spec_at_{k}'].mean()
        picasso_k = df[df['phase'] == 'picasso'][f'spec_at_{k}'].mean()
        improvement = picasso_k - vanilla_k
        print(f"Spec@{k}: Vanilla={vanilla_k:.3f}, Picasso={picasso_k:.3f}, Improvement={improvement:+.3f}")
    
    print("\n" + "=" * 80)
    print("PLOTS CREATED")
    print("=" * 80)
    print(f"📊 Comprehensive: {comprehensive_path}")
    print(f"📊 Spec@k focused: {spec_at_k_path}")
    print("=" * 80)

