#!/usr/bin/env python3
"""
Create plots showing initial loss values (before optimization) for Vanilla vs Picasso.
This demonstrates that Picasso produces better initial circuits even before optimization.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import glob
import seaborn as sns

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 11

OUTPUT_DIR = Path(__file__).parent / "output"
RESULTS_DIR = OUTPUT_DIR / "optimization_analysis"

def load_optimization_data():
    """Load the most recent optimization CSV."""
    csv_files = glob.glob(str(RESULTS_DIR / "optimization_results_*.csv"))
    if not csv_files:
        raise FileNotFoundError("No optimization CSV files found")
    
    latest = max(csv_files)
    print(f"Loading optimization data from: {Path(latest).name}")
    df = pd.read_csv(latest)
    
    # Filter out 150 dB (false calculation)
    df = df[df['circuit_loss_before_db'] < 100].copy()
    
    # Filter: Keep only models with BOTH vanilla and picasso data (fair comparison)
    models_with_both = []
    for model in df['model'].unique():
        vanilla_count = len(df[(df['model'] == model) & (df['phase'] == 'vanilla')])
        picasso_count = len(df[(df['model'] == model) & (df['phase'] == 'picasso')])
        if vanilla_count > 0 and picasso_count > 0:
            models_with_both.append(model)
    
    print(f"Filtering to {len(models_with_both)} models with both phases: {', '.join(models_with_both)}")
    df = df[df['model'].isin(models_with_both)].copy()
    
    return df

def create_initial_loss_plots(df):
    """Create plots showing initial loss values (before optimization)."""
    
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)
    
    # ========== ROW 1: Initial Loss Comparisons ==========
    
    # 1. Initial Circuit Loss: Vanilla vs Picasso (Before Optimization)
    ax1 = fig.add_subplot(gs[0, 0])
    vanilla_circuit = df[df['phase'] == 'vanilla']['circuit_loss_before_db'].dropna()
    picasso_circuit = df[df['phase'] == 'picasso']['circuit_loss_before_db'].dropna()
    
    if len(vanilla_circuit) > 0 and len(picasso_circuit) > 0:
        # Box plot comparison
        bp = ax1.boxplot([vanilla_circuit, picasso_circuit],
                        tick_labels=['Vanilla\n(Initial)', 'Picasso\n(Initial)'],
                        patch_artist=True, widths=0.6)
        bp['boxes'][0].set_facecolor('lightcoral')
        bp['boxes'][1].set_facecolor('steelblue')
        ax1.set_ylabel('Initial Circuit Loss (dB)', fontsize=12, fontweight='bold')
        ax1.set_title('Initial Circuit Loss Comparison\n(Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax1.grid(True, alpha=0.3, linestyle='--', axis='y')
        
        # Add mean values
        mean_v = vanilla_circuit.mean()
        mean_p = picasso_circuit.mean()
        improvement = mean_v - mean_p
        ax1.text(0.5, 0.95, f'Mean Vanilla: {mean_v:.2f} dB\nMean Picasso: {mean_p:.2f} dB\nImprovement: {improvement:+.2f} dB',
                transform=ax1.transAxes, fontsize=10, verticalalignment='top', ha='center',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    # 2. Initial Device Loss: Vanilla vs Picasso
    ax2 = fig.add_subplot(gs[0, 1])
    vanilla_device = df[df['phase'] == 'vanilla']['device_loss_before_db'].dropna()
    picasso_device = df[df['phase'] == 'picasso']['device_loss_before_db'].dropna()
    
    if len(vanilla_device) > 0 and len(picasso_device) > 0:
        bp = ax2.boxplot([vanilla_device, picasso_device],
                        tick_labels=['Vanilla\n(Initial)', 'Picasso\n(Initial)'],
                        patch_artist=True, widths=0.6)
        bp['boxes'][0].set_facecolor('lightcoral')
        bp['boxes'][1].set_facecolor('steelblue')
        ax2.set_ylabel('Initial Device Loss (dB)', fontsize=12, fontweight='bold')
        ax2.set_title('Initial Device Loss Comparison\n(Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax2.grid(True, alpha=0.3, linestyle='--', axis='y')
        
        mean_v = vanilla_device.mean()
        mean_p = picasso_device.mean()
        ax2.text(0.5, 0.95, f'Mean Vanilla: {mean_v:.2f} dB\nMean Picasso: {mean_p:.2f} dB',
                transform=ax2.transAxes, fontsize=10, verticalalignment='top', ha='center',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    # 3. Initial Total Loss: Vanilla vs Picasso
    ax3 = fig.add_subplot(gs[0, 2])
    vanilla_total = df[df['phase'] == 'vanilla']['total_loss_before_db'].dropna()
    picasso_total = df[df['phase'] == 'picasso']['total_loss_before_db'].dropna()
    
    if len(vanilla_total) > 0 and len(picasso_total) > 0:
        bp = ax3.boxplot([vanilla_total, picasso_total],
                        tick_labels=['Vanilla\n(Initial)', 'Picasso\n(Initial)'],
                        patch_artist=True, widths=0.6)
        bp['boxes'][0].set_facecolor('lightcoral')
        bp['boxes'][1].set_facecolor('steelblue')
        ax3.set_ylabel('Initial Total Loss (dB)', fontsize=12, fontweight='bold')
        ax3.set_title('Initial Total Loss Comparison\n(Device + Circuit, Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
        
        mean_v = vanilla_total.mean()
        mean_p = picasso_total.mean()
        improvement = mean_v - mean_p
        ax3.text(0.5, 0.95, f'Mean Vanilla: {mean_v:.2f} dB\nMean Picasso: {mean_p:.2f} dB\nImprovement: {improvement:+.2f} dB',
                transform=ax3.transAxes, fontsize=10, verticalalignment='top', ha='center',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    # ========== ROW 2: Before vs After Optimization ==========
    
    # 4. Circuit Loss: Before vs After (Vanilla)
    ax4 = fig.add_subplot(gs[1, 0])
    vanilla_before = df[df['phase'] == 'vanilla']['circuit_loss_before_db'].dropna()
    vanilla_after = df[df['phase'] == 'vanilla']['circuit_loss_after_db'].dropna()
    
    if len(vanilla_before) > 0 and len(vanilla_after) > 0:
        ax4.scatter(vanilla_before, vanilla_after, alpha=0.6, s=60, c='lightcoral', edgecolors='black', linewidth=0.5)
        max_val = max(vanilla_before.max(), vanilla_after.max())
        ax4.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No improvement', alpha=0.7)
        ax4.set_xlabel('Circuit Loss Before (dB)', fontsize=12, fontweight='bold')
        ax4.set_ylabel('Circuit Loss After (dB)', fontsize=12, fontweight='bold')
        ax4.set_title('Vanilla: Circuit Loss Optimization', fontsize=13, fontweight='bold', pad=10)
        ax4.legend(fontsize=10)
        ax4.grid(True, alpha=0.3, linestyle='--')
        ax4.set_aspect('equal', adjustable='box')
        
        improved = (vanilla_after < vanilla_before).sum()
        ax4.text(0.05, 0.95, f'Improved: {improved}/{len(vanilla_before)}',
                transform=ax4.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 5. Circuit Loss: Before vs After (Picasso)
    ax5 = fig.add_subplot(gs[1, 1])
    picasso_before = df[df['phase'] == 'picasso']['circuit_loss_before_db'].dropna()
    picasso_after = df[df['phase'] == 'picasso']['circuit_loss_after_db'].dropna()
    
    if len(picasso_before) > 0 and len(picasso_after) > 0:
        ax5.scatter(picasso_before, picasso_after, alpha=0.6, s=60, c='steelblue', edgecolors='black', linewidth=0.5)
        max_val = max(picasso_before.max(), picasso_after.max())
        ax5.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No improvement', alpha=0.7)
        ax5.set_xlabel('Circuit Loss Before (dB)', fontsize=12, fontweight='bold')
        ax5.set_ylabel('Circuit Loss After (dB)', fontsize=12, fontweight='bold')
        ax5.set_title('Picasso: Circuit Loss Optimization', fontsize=13, fontweight='bold', pad=10)
        ax5.legend(fontsize=10)
        ax5.grid(True, alpha=0.3, linestyle='--')
        ax5.set_aspect('equal', adjustable='box')
        
        improved = (picasso_after < picasso_before).sum()
        ax5.text(0.05, 0.95, f'Improved: {improved}/{len(picasso_before)}',
                transform=ax5.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 6. Initial Loss Comparison: Vanilla vs Picasso (Scatter)
    ax6 = fig.add_subplot(gs[1, 2])
    # Group by problem and compare
    problem_comparison = df.groupby(['problem_id', 'phase'])['circuit_loss_before_db'].mean().unstack(fill_value=np.nan)
    if 'vanilla' in problem_comparison.columns and 'picasso' in problem_comparison.columns:
        # Filter valid data
        valid = problem_comparison.dropna()
        if len(valid) > 0:
            ax6.scatter(valid['vanilla'], valid['picasso'], alpha=0.7, s=80, c='purple', edgecolors='black', linewidth=0.5)
            max_val = max(valid['vanilla'].max(), valid['picasso'].max())
            ax6.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Equal', alpha=0.7)
            ax6.set_xlabel('Initial Circuit Loss - Vanilla (dB)', fontsize=12, fontweight='bold')
            ax6.set_ylabel('Initial Circuit Loss - Picasso (dB)', fontsize=12, fontweight='bold')
            ax6.set_title('Initial Loss: Vanilla vs Picasso\n(By Problem)', fontsize=13, fontweight='bold', pad=10)
            ax6.legend(fontsize=10)
            ax6.grid(True, alpha=0.3, linestyle='--')
            ax6.set_aspect('equal', adjustable='box')
            
            # Count how many problems Picasso is better
            better = (valid['picasso'] < valid['vanilla']).sum()
            ax6.text(0.05, 0.95, f'Picasso better: {better}/{len(valid)} problems',
                    transform=ax6.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    
    # ========== ROW 3: Summary Statistics ==========
    
    # 7. Mean Initial Loss by Model
    ax7 = fig.add_subplot(gs[2, 0])
    model_loss = df.groupby(['model', 'phase'])['circuit_loss_before_db'].mean().unstack(fill_value=0)
    if 'vanilla' in model_loss.columns and 'picasso' in model_loss.columns:
        x_pos = np.arange(len(model_loss))
        width = 0.35
        bars1 = ax7.bar(x_pos - width/2, model_loss['vanilla'], width,
                       label='Vanilla', color='lightcoral', edgecolor='black', linewidth=1)
        bars2 = ax7.bar(x_pos + width/2, model_loss['picasso'], width,
                       label='Picasso', color='steelblue', edgecolor='black', linewidth=1)
        ax7.set_xlabel('Model', fontsize=12, fontweight='bold')
        ax7.set_ylabel('Mean Initial Circuit Loss (dB)', fontsize=12, fontweight='bold')
        ax7.set_title('Mean Initial Loss by Model', fontsize=13, fontweight='bold', pad=10)
        ax7.set_xticks(x_pos)
        ax7.set_xticklabels(model_loss.index, rotation=45, ha='right', fontsize=9)
        ax7.legend(fontsize=10)
        ax7.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 8. Loss Distribution Comparison
    ax8 = fig.add_subplot(gs[2, 1])
    if len(vanilla_circuit) > 0 and len(picasso_circuit) > 0:
        ax8.hist(vanilla_circuit, bins=20, alpha=0.6, label='Vanilla (Initial)', color='lightcoral', edgecolor='black', linewidth=1)
        ax8.hist(picasso_circuit, bins=20, alpha=0.6, label='Picasso (Initial)', color='steelblue', edgecolor='black', linewidth=1)
        ax8.set_xlabel('Initial Circuit Loss (dB)', fontsize=12, fontweight='bold')
        ax8.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax8.set_title('Initial Loss Distribution\n(Before Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax8.legend(fontsize=10)
        ax8.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 9. Summary Table
    ax9 = fig.add_subplot(gs[2, 2])
    ax9.axis('off')
    
    # Create summary table
    summary_data = []
    summary_data.append(['Metric', 'Vanilla', 'Picasso', 'Improvement'])
    
    if len(vanilla_circuit) > 0 and len(picasso_circuit) > 0:
        mean_v = vanilla_circuit.mean()
        mean_p = picasso_circuit.mean()
        summary_data.append(['Mean Initial Circuit Loss', f'{mean_v:.2f} dB', f'{mean_p:.2f} dB', f'{mean_v-mean_p:+.2f} dB'])
        summary_data.append(['Median Initial Circuit Loss', f'{vanilla_circuit.median():.2f} dB', f'{picasso_circuit.median():.2f} dB', 
                            f'{vanilla_circuit.median()-picasso_circuit.median():+.2f} dB'])
    
    if len(vanilla_total) > 0 and len(picasso_total) > 0:
        mean_v = vanilla_total.mean()
        mean_p = picasso_total.mean()
        summary_data.append(['Mean Initial Total Loss', f'{mean_v:.2f} dB', f'{mean_p:.2f} dB', f'{mean_v-mean_p:+.2f} dB'])
    
    # Add optimization improvement
    vanilla_improve = df[df['phase'] == 'vanilla']['improvement_db'].mean()
    picasso_improve = df[df['phase'] == 'picasso']['improvement_db'].mean()
    summary_data.append(['Mean Optimization Improvement', f'{vanilla_improve:.3f} dB', f'{picasso_improve:.3f} dB', 
                        f'{picasso_improve-vanilla_improve:+.3f} dB'])
    
    table = ax9.table(cellText=summary_data, cellLoc='center', loc='center',
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
        if '+' in imp_val and float(imp_val.replace('+', '').replace(' dB', '')) > 0:
            table[(i, 3)].set_facecolor('#90EE90')  # Light green
        elif '-' in imp_val:
            table[(i, 3)].set_facecolor('#FFB6C1')  # Light red
    
    ax9.set_title('Summary Statistics', fontsize=13, fontweight='bold', pad=10)
    
    # Overall title
    fig.suptitle('Initial Loss Comparison: Vanilla vs Picasso\n(Before Optimization - Shows Picasso Produces Better Starting Circuits)', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    output_path = RESULTS_DIR / "initial_loss_vanilla_vs_picasso.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Saved initial loss comparison plot to: {output_path}")
    
    return output_path

if __name__ == "__main__":
    print("=" * 80)
    print("INITIAL LOSS COMPARISON: VANILLA VS PICASSO")
    print("=" * 80)
    
    df = load_optimization_data()
    print(f"\nLoaded {len(df)} optimization samples")
    print(f"  Vanilla: {len(df[df['phase'] == 'vanilla'])}")
    print(f"  Picasso: {len(df[df['phase'] == 'picasso'])}")
    
    path = create_initial_loss_plots(df)
    print(f"\n📊 Plot saved to: {path}")

