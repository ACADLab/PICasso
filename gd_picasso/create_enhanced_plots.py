#!/usr/bin/env python3
"""
Create enhanced plots with nice labeling for device-level, circuit-level, and total loss.
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
plt.rcParams['font.size'] = 10

OUTPUT_DIR = Path(__file__).parent / "output" / "optimization_analysis"

def load_latest_data():
    """Load the most recent CSV file."""
    csv_files = glob.glob(str(OUTPUT_DIR / "optimization_results_*.csv"))
    if not csv_files:
        raise FileNotFoundError("No CSV files found in optimization_analysis directory")
    
    latest = max(csv_files)
    print(f"Loading data from: {Path(latest).name}")
    df = pd.read_csv(latest)
    return df, latest

def create_comprehensive_plots(df, output_path):
    """Create comprehensive plots with device-level, circuit-level, and total loss."""
    
    # Filter out invalid data (150 dB is the false calculation)
    df_clean = df[df['circuit_loss_before_db'] < 100].copy()
    
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # ========== ROW 1: Before vs After Comparisons ==========
    
    # 1. Circuit-Level Loss: Before vs After
    ax1 = fig.add_subplot(gs[0, 0])
    before = df_clean['circuit_loss_before_db'].dropna()
    after = df_clean['circuit_loss_after_db'].dropna()
    
    ax1.scatter(before, after, alpha=0.6, s=60, c='steelblue', edgecolors='black', linewidth=0.5)
    max_val = max(before.max(), after.max()) if len(before) > 0 and len(after) > 0 else 10
    ax1.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No improvement', alpha=0.7)
    ax1.set_xlabel('Circuit Loss Before Optimization (dB)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Circuit Loss After Optimization (dB)', fontsize=12, fontweight='bold')
    ax1.set_title('Circuit-Level Optimization\n(Phase Shifters & Couplers)', fontsize=13, fontweight='bold', pad=10)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_aspect('equal', adjustable='box')
    
    # Add improvement count
    improved = (after < before).sum()
    ax1.text(0.05, 0.95, f'Improved: {improved}/{len(before)} ({improved/len(before)*100:.1f}%)',
             transform=ax1.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 2. Total Loss: Before vs After
    ax2 = fig.add_subplot(gs[0, 1])
    total_before = df_clean['total_loss_before_db'].dropna()
    total_after = df_clean['total_loss_after_db'].dropna()
    
    ax2.scatter(total_before, total_after, alpha=0.6, s=60, c='forestgreen', edgecolors='black', linewidth=0.5)
    max_val = max(total_before.max(), total_after.max()) if len(total_before) > 0 and len(total_after) > 0 else 10
    ax2.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No improvement', alpha=0.7)
    ax2.set_xlabel('Total Loss Before Optimization (dB)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Total Loss After Optimization (dB)', fontsize=12, fontweight='bold')
    ax2.set_title('Total Loss Optimization\n(Device + Circuit Level)', fontsize=13, fontweight='bold', pad=10)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_aspect('equal', adjustable='box')
    
    improved_total = (total_after < total_before).sum()
    ax2.text(0.05, 0.95, f'Improved: {improved_total}/{len(total_before)} ({improved_total/len(total_before)*100:.1f}%)',
             transform=ax2.transAxes, fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 3. Device-Level Loss (should be same before/after)
    ax3 = fig.add_subplot(gs[0, 2])
    device_before = df_clean['device_loss_before_db'].dropna()
    device_after = df_clean['device_loss_after_db'].dropna()
    
    ax3.scatter(device_before, device_after, alpha=0.6, s=60, c='purple', edgecolors='black', linewidth=0.5)
    if len(device_before) > 0:
        max_val = max(device_before.max(), device_after.max()) if len(device_after) > 0 else 1
        ax3.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No change expected', alpha=0.7)
    ax3.set_xlabel('Device Loss Before (dB)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Device Loss After (dB)', fontsize=12, fontweight='bold')
    ax3.set_title('Device-Level Loss\n(Component Geometries)', fontsize=13, fontweight='bold', pad=10)
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3, linestyle='--')
    ax3.set_aspect('equal', adjustable='box')
    
    # ========== ROW 2: Improvement Analysis ==========
    
    # 4. Improvement Distribution
    ax4 = fig.add_subplot(gs[1, 0])
    improvement = df_clean['improvement_db'].dropna()
    if len(improvement) > 0:
        ax4.hist(improvement, bins=30, alpha=0.7, color='coral', edgecolor='black', linewidth=1.2)
        ax4.axvline(0, color='red', linestyle='--', linewidth=2, label='No improvement')
        ax4.axvline(improvement.mean(), color='blue', linestyle='-', linewidth=2, label=f'Mean: {improvement.mean():.3f} dB')
        ax4.set_xlabel('Improvement (dB)', fontsize=12, fontweight='bold')
        ax4.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax4.set_title('Improvement Distribution\n(Circuit-Level Optimization)', fontsize=13, fontweight='bold', pad=10)
        ax4.legend(fontsize=10)
        ax4.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 5. Optimization Efficiency Distribution
    ax5 = fig.add_subplot(gs[1, 1])
    opt_eff = df_clean['opt_efficiency'].dropna()
    if len(opt_eff) > 0:
        ax5.hist(opt_eff, bins=30, alpha=0.7, color='gold', edgecolor='black', linewidth=1.2)
        ax5.axvline(opt_eff.mean(), color='blue', linestyle='-', linewidth=2, label=f'Mean: {opt_eff.mean():.4f}')
        ax5.axvline(opt_eff.median(), color='green', linestyle='--', linewidth=2, label=f'Median: {opt_eff.median():.4f}')
        ax5.set_xlabel('Optimization Efficiency', fontsize=12, fontweight='bold')
        ax5.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax5.set_title('Optimization Efficiency Distribution\n(Normalized 0-1)', fontsize=13, fontweight='bold', pad=10)
        ax5.legend(fontsize=10)
        ax5.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 6. Loss Breakdown: Device vs Circuit
    ax6 = fig.add_subplot(gs[1, 2])
    device_loss = df_clean['device_loss_after_db'].dropna()
    circuit_loss = df_clean['circuit_loss_after_db'].dropna()
    
    # Create stacked bar or scatter
    if len(device_loss) > 0 and len(circuit_loss) > 0:
        # Sample for visualization if too many points
        n_sample = min(50, len(df_clean))
        df_sample = df_clean.sample(n=n_sample) if len(df_clean) > n_sample else df_clean
        
        x_pos = np.arange(len(df_sample))
        width = 0.6
        
        device_vals = df_sample['device_loss_after_db'].values
        circuit_vals = df_sample['circuit_loss_after_db'].values
        
        ax6.bar(x_pos, device_vals, width, label='Device-Level Loss', color='purple', alpha=0.7)
        ax6.bar(x_pos, circuit_vals, width, bottom=device_vals, label='Circuit-Level Loss', color='steelblue', alpha=0.7)
        
        ax6.set_xlabel('Sample Index', fontsize=12, fontweight='bold')
        ax6.set_ylabel('Loss (dB)', fontsize=12, fontweight='bold')
        ax6.set_title('Loss Breakdown by Sample\n(Device + Circuit = Total)', fontsize=13, fontweight='bold', pad=10)
        ax6.legend(fontsize=10)
        ax6.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax6.set_xticks([])  # Hide x-axis labels for clarity
    
    # ========== ROW 3: Model and Problem Analysis ==========
    
    # 7. Improvement by Model
    ax7 = fig.add_subplot(gs[2, 0])
    model_improvement = df_clean.groupby('model')['improvement_db'].mean().sort_values(ascending=False)
    colors = plt.cm.viridis(np.linspace(0, 1, len(model_improvement)))
    bars = ax7.barh(range(len(model_improvement)), model_improvement.values, color=colors, edgecolor='black', linewidth=1)
    ax7.set_yticks(range(len(model_improvement)))
    ax7.set_yticklabels(model_improvement.index, fontsize=9)
    ax7.set_xlabel('Mean Improvement (dB)', fontsize=12, fontweight='bold')
    ax7.set_title('Mean Improvement by Model', fontsize=13, fontweight='bold', pad=10)
    ax7.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax7.grid(True, alpha=0.3, linestyle='--', axis='x')
    
    # Add value labels on bars
    for i, (idx, val) in enumerate(model_improvement.items()):
        ax7.text(val, i, f' {val:.3f}', va='center', fontsize=8)
    
    # 8. Loss Comparison: Before vs After (Box Plot)
    ax8 = fig.add_subplot(gs[2, 1])
    loss_data = pd.DataFrame({
        'Before': df_clean['circuit_loss_before_db'].dropna(),
        'After': df_clean['circuit_loss_after_db'].dropna()
    })
    bp = ax8.boxplot([loss_data['Before'], loss_data['After']], 
                     tick_labels=['Before\nOptimization', 'After\nOptimization'],
                     patch_artist=True, widths=0.6)
    bp['boxes'][0].set_facecolor('lightcoral')
    bp['boxes'][1].set_facecolor('lightblue')
    ax8.set_ylabel('Circuit Loss (dB)', fontsize=12, fontweight='bold')
    ax8.set_title('Loss Distribution Comparison', fontsize=13, fontweight='bold', pad=10)
    ax8.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 9. Improvement by Problem
    ax9 = fig.add_subplot(gs[2, 2])
    problem_improvement = df_clean.groupby('problem_id')['improvement_db'].mean().sort_values(ascending=False).head(15)
    colors = plt.cm.plasma(np.linspace(0, 1, len(problem_improvement)))
    bars = ax9.barh(range(len(problem_improvement)), problem_improvement.values, color=colors, edgecolor='black', linewidth=1)
    ax9.set_yticks(range(len(problem_improvement)))
    ax9.set_yticklabels([f'Problem {p}' for p in problem_improvement.index], fontsize=9)
    ax9.set_xlabel('Mean Improvement (dB)', fontsize=12, fontweight='bold')
    ax9.set_title('Top 15 Problems by Improvement', fontsize=13, fontweight='bold', pad=10)
    ax9.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax9.grid(True, alpha=0.3, linestyle='--', axis='x')
    
    # Add value labels
    for i, (idx, val) in enumerate(problem_improvement.items()):
        ax9.text(val, i, f' {val:.3f}', va='center', fontsize=8)
    
    # Overall title
    fig.suptitle('Optimization Analysis: Device-Level vs Circuit-Level Performance', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Saved enhanced plot to: {output_path}")
    
    return output_path

def create_simple_comparison_plot(df, output_path):
    """Create a simple 3-panel comparison plot."""
    df_clean = df[df['circuit_loss_before_db'] < 100].copy()
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle('Optimization Results: Before vs After Comparison', fontsize=16, fontweight='bold')
    
    # Device-Level
    ax = axes[0]
    device_before = df_clean['device_loss_before_db'].dropna()
    device_after = df_clean['device_loss_after_db'].dropna()
    ax.scatter(device_before, device_after, alpha=0.7, s=80, c='purple', edgecolors='black', linewidth=0.5)
    if len(device_before) > 0:
        max_val = max(device_before.max(), device_after.max()) if len(device_after) > 0 else 1
        ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No change')
    ax.set_xlabel('Device Loss Before (dB)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Device Loss After (dB)', fontsize=12, fontweight='bold')
    ax.set_title('Device-Level Loss\n(Component Geometries)', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    # Circuit-Level
    ax = axes[1]
    before = df_clean['circuit_loss_before_db'].dropna()
    after = df_clean['circuit_loss_after_db'].dropna()
    ax.scatter(before, after, alpha=0.7, s=80, c='steelblue', edgecolors='black', linewidth=0.5)
    max_val = max(before.max(), after.max()) if len(before) > 0 and len(after) > 0 else 10
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No improvement')
    ax.set_xlabel('Circuit Loss Before (dB)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Circuit Loss After (dB)', fontsize=12, fontweight='bold')
    ax.set_title('Circuit-Level Loss\n(Phase Shifters & Couplers)', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    improved = (after < before).sum()
    ax.text(0.05, 0.95, f'Improved: {improved}/{len(before)}\n({improved/len(before)*100:.1f}%)',
            transform=ax.transAxes, fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    # Total Loss
    ax = axes[2]
    total_before = df_clean['total_loss_before_db'].dropna()
    total_after = df_clean['total_loss_after_db'].dropna()
    ax.scatter(total_before, total_after, alpha=0.7, s=80, c='forestgreen', edgecolors='black', linewidth=0.5)
    max_val = max(total_before.max(), total_after.max()) if len(total_before) > 0 and len(total_after) > 0 else 10
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='No improvement')
    ax.set_xlabel('Total Loss Before (dB)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Total Loss After (dB)', fontsize=12, fontweight='bold')
    ax.set_title('Total Loss\n(Device + Circuit)', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    improved_total = (total_after < total_before).sum()
    ax.text(0.05, 0.95, f'Improved: {improved_total}/{len(total_before)}\n({improved_total/len(total_before)*100:.1f}%)',
            transform=ax.transAxes, fontsize=11, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✅ Saved simple comparison plot to: {output_path}")
    
    return output_path

if __name__ == "__main__":
    print("=" * 80)
    print("CREATING ENHANCED PLOTS")
    print("=" * 80)
    
    df, csv_path = load_latest_data()
    print(f"\nLoaded {len(df)} samples")
    print(f"Models: {df['model'].nunique()}")
    print(f"Problems: {df['problem_id'].nunique()}")
    
    # Create comprehensive plot
    comprehensive_path = OUTPUT_DIR / "optimization_comprehensive_plot.png"
    create_comprehensive_plots(df, comprehensive_path)
    
    # Create simple comparison plot
    simple_path = OUTPUT_DIR / "optimization_simple_comparison.png"
    create_simple_comparison_plot(df, simple_path)
    
    print("\n" + "=" * 80)
    print("PLOTS CREATED")
    print("=" * 80)
    print(f"📊 Comprehensive plot: {comprehensive_path}")
    print(f"📊 Simple comparison: {simple_path}")
    print("=" * 80)

