#!/usr/bin/env python3
"""
Script to plot and compare Vanilla vs PICasso results from JSON results file.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from collections import defaultdict

# Set style for better-looking plots
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10


def load_results(json_path: Path) -> List[Dict]:
    """Load results from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def separate_by_phase(results: List[Dict]) -> tuple[List[Dict], List[Dict]]:
    """Separate results by phase."""
    vanilla_results = [r for r in results if r.get('phase') == 'vanilla']
    picasso_results = [r for r in results if r.get('phase') == 'picasso']
    return vanilla_results, picasso_results


def extract_metrics(results: List[Dict]) -> Dict:
    """Extract aggregated metrics from results."""
    if not results:
        return {}
    
    # Aggregate metrics across all problems
    total_samples = sum(len(r.get('samples', [])) for r in results)
    total_passed = sum(r.get('pass_count', 0) for r in results)
    total_structural_pass = sum(r.get('metrics', {}).get('num_structural_pass', 0) for r in results)
    total_full_pass = sum(r.get('metrics', {}).get('num_full_pass', 0) for r in results)
    
    # Average metrics (weighted by number of samples)
    metrics = {
        'num_problems': len(results),
        'total_samples': total_samples,
        'total_passed': total_passed,
        'total_structural_pass': total_structural_pass,
        'total_full_pass': total_full_pass,
        'pass_rate': (total_passed / total_samples * 100) if total_samples > 0 else 0.0,
        'structural_pass_rate': (total_structural_pass / total_samples * 100) if total_samples > 0 else 0.0,
        'full_pass_rate': (total_full_pass / total_samples * 100) if total_samples > 0 else 0.0,
    }
    
    # Compute weighted averages for metrics
    weighted_metrics = defaultdict(float)
    total_weight = 0
    
    for r in results:
        problem_metrics = r.get('metrics', {})
        num_samples = r.get('metrics', {}).get('num_samples', len(r.get('samples', [])))
        if num_samples > 0:
            weight = num_samples
            total_weight += weight
            
            for key in ['pass_at_k', 'spec_at_k_structural', 'spec_at_k_full', 'spec_at_k',
                       'avg_opt_efficiency', 'robust_pass', 'robustness_score']:
                if key in problem_metrics:
                    weighted_metrics[key] += problem_metrics[key] * weight
    
    # Normalize weighted metrics
    for key in weighted_metrics:
        metrics[key] = weighted_metrics[key] / total_weight if total_weight > 0 else 0.0
    
    return metrics


def plot_comparison_bar_chart(vanilla_metrics: Dict, picasso_metrics: Dict, output_path: Path):
    """Create bar chart comparing key metrics."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Vanilla vs PICasso Framework Comparison', fontsize=16, fontweight='bold')
    
    # 1. Pass Rates
    ax1 = axes[0, 0]
    if vanilla_metrics and picasso_metrics:
        categories = ['Pass Rate', 'Structural\nPass Rate', 'Full Pass\nRate']
        vanilla_values = [
            vanilla_metrics.get('pass_rate', 0),
            vanilla_metrics.get('structural_pass_rate', 0),
            vanilla_metrics.get('full_pass_rate', 0)
        ]
        picasso_values = [
            picasso_metrics.get('pass_rate', 0),
            picasso_metrics.get('structural_pass_rate', 0),
            picasso_metrics.get('full_pass_rate', 0)
        ]
        
        x = np.arange(len(categories))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, vanilla_values, width, label='Vanilla', color='#FF6B6B', alpha=0.8)
        bars2 = ax1.bar(x + width/2, picasso_values, width, label='PICasso', color='#4ECDC4', alpha=0.8)
        
        ax1.set_ylabel('Pass Rate (%)', fontweight='bold')
        ax1.set_title('Pass Rates Comparison', fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(categories)
        ax1.legend()
        ax1.set_ylim(0, 105)
        ax1.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%',
                        ha='center', va='bottom', fontsize=9)
    else:
        ax1.text(0.5, 0.5, 'Insufficient data for comparison', 
                ha='center', va='center', transform=ax1.transAxes, fontsize=12)
        ax1.set_title('Pass Rates Comparison', fontweight='bold')
    
    # 2. Spec@k Metrics
    ax2 = axes[0, 1]
    if vanilla_metrics and picasso_metrics:
        categories = ['Spec@k\nStructural', 'Spec@k Full', 'Spec@k']
        vanilla_values = [
            vanilla_metrics.get('spec_at_k_structural', 0) * 100,
            vanilla_metrics.get('spec_at_k_full', 0) * 100,
            vanilla_metrics.get('spec_at_k', 0) * 100
        ]
        picasso_values = [
            picasso_metrics.get('spec_at_k_structural', 0) * 100,
            picasso_metrics.get('spec_at_k_full', 0) * 100,
            picasso_metrics.get('spec_at_k', 0) * 100
        ]
        
        x = np.arange(len(categories))
        width = 0.35
        
        bars1 = ax2.bar(x - width/2, vanilla_values, width, label='Vanilla', color='#FF6B6B', alpha=0.8)
        bars2 = ax2.bar(x + width/2, picasso_values, width, label='PICasso', color='#4ECDC4', alpha=0.8)
        
        ax2.set_ylabel('Score (%)', fontweight='bold')
        ax2.set_title('Spec@k Metrics Comparison', fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(categories)
        ax2.legend()
        ax2.set_ylim(0, 105)
        ax2.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%',
                        ha='center', va='bottom', fontsize=9)
    else:
        ax2.text(0.5, 0.5, 'Insufficient data for comparison', 
                ha='center', va='center', transform=ax2.transAxes, fontsize=12)
        ax2.set_title('Spec@k Metrics Comparison', fontweight='bold')
    
    # 3. Sample Counts
    ax3 = axes[1, 0]
    if vanilla_metrics and picasso_metrics:
        categories = ['Total\nSamples', 'Passed', 'Structural\nPass', 'Full Pass']
        vanilla_values = [
            vanilla_metrics.get('total_samples', 0),
            vanilla_metrics.get('total_passed', 0),
            vanilla_metrics.get('total_structural_pass', 0),
            vanilla_metrics.get('total_full_pass', 0)
        ]
        picasso_values = [
            picasso_metrics.get('total_samples', 0),
            picasso_metrics.get('total_passed', 0),
            picasso_metrics.get('total_structural_pass', 0),
            picasso_metrics.get('total_full_pass', 0)
        ]
        
        x = np.arange(len(categories))
        width = 0.35
        
        bars1 = ax3.bar(x - width/2, vanilla_values, width, label='Vanilla', color='#FF6B6B', alpha=0.8)
        bars2 = ax3.bar(x + width/2, picasso_values, width, label='PICasso', color='#4ECDC4', alpha=0.8)
        
        ax3.set_ylabel('Count', fontweight='bold')
        ax3.set_title('Sample Counts Comparison', fontweight='bold')
        ax3.set_xticks(x)
        ax3.set_xticklabels(categories)
        ax3.legend()
        ax3.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax3.text(bar.get_x() + bar.get_width()/2., height,
                            f'{int(height)}',
                            ha='center', va='bottom', fontsize=9)
    else:
        ax3.text(0.5, 0.5, 'Insufficient data for comparison', 
                ha='center', va='center', transform=ax3.transAxes, fontsize=12)
        ax3.set_title('Sample Counts Comparison', fontweight='bold')
    
    # 4. PICasso-specific metrics (if available)
    ax4 = axes[1, 1]
    if picasso_metrics:
        picasso_specific = {
            'Avg Opt\nEfficiency': picasso_metrics.get('avg_opt_efficiency', 0) * 100,
            'Robustness\nScore': picasso_metrics.get('robustness_score', 0) * 100,
            'Robust Pass': picasso_metrics.get('robust_pass', 0) * 100
        }
        
        categories = list(picasso_specific.keys())
        values = list(picasso_specific.values())
        
        bars = ax4.bar(categories, values, color='#4ECDC4', alpha=0.8)
        ax4.set_ylabel('Score (%)', fontweight='bold')
        ax4.set_title('PICasso Framework-Specific Metrics', fontweight='bold')
        ax4.set_ylim(0, 105)
        ax4.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%',
                    ha='center', va='bottom', fontsize=9)
    else:
        ax4.text(0.5, 0.5, 'No PICasso metrics available', 
                ha='center', va='center', transform=ax4.transAxes, fontsize=12)
        ax4.set_title('PICasso Framework-Specific Metrics', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved comparison bar chart to: {output_path}")


def plot_problem_by_problem_comparison(vanilla_results: List[Dict], picasso_results: List[Dict], output_path: Path):
    """Create problem-by-problem comparison."""
    # Create a mapping by problem_id
    vanilla_by_id = {r['problem_id']: r for r in vanilla_results}
    picasso_by_id = {r['problem_id']: r for r in picasso_results}
    
    # Get all problem IDs
    all_problem_ids = sorted(set(list(vanilla_by_id.keys()) + list(picasso_by_id.keys())))
    
    if not all_problem_ids:
        print("No problems found for comparison")
        return
    
    # Build consistent problem list for both plots
    problem_data = []
    for pid in all_problem_ids:
        v_result = vanilla_by_id.get(pid, {})
        p_result = picasso_by_id.get(pid, {})
        
        v_spec = v_result.get('metrics', {}).get('spec_at_k_structural', 0)
        p_spec = p_result.get('metrics', {}).get('spec_at_k_structural', 0)
        v_pass = v_result.get('pass_count', 0)
        p_pass = p_result.get('pass_count', 0)
        v_total = len(v_result.get('samples', []))
        p_total = len(p_result.get('samples', []))
        
        # Include if at least one phase has data
        if v_total > 0 or p_total > 0:
            problem_name = v_result.get('problem_name') or p_result.get('problem_name', f'Problem {pid}')
            problem_data.append({
                'id': pid,
                'name': problem_name,
                'vanilla_spec': v_spec * 100,
                'picasso_spec': p_spec * 100,
                'vanilla_pass': v_pass,
                'picasso_pass': p_pass,
                'vanilla_total': v_total,
                'picasso_total': p_total
            })
    
    if not problem_data:
        print("No problem data found for comparison")
        return
    
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    fig.suptitle('Problem-by-Problem Comparison: Vanilla vs PICasso', fontsize=16, fontweight='bold')
    
    # 1. Spec@k Structural by problem
    ax1 = axes[0]
    vanilla_spec = [p['vanilla_spec'] for p in problem_data]
    picasso_spec = [p['picasso_spec'] for p in problem_data]
    problem_labels = [f"P{p['id']}\n{p['name'][:20]}..." for p in problem_data]
    
    x = np.arange(len(problem_labels))
    width = 0.35
    
    has_vanilla = any(v > 0 for v in vanilla_spec)
    has_picasso = any(p > 0 for p in picasso_spec)
    
    if has_vanilla:
        bars1 = ax1.bar(x - width/2, vanilla_spec, width, label='Vanilla', color='#FF6B6B', alpha=0.8)
    if has_picasso:
        bars2 = ax1.bar(x + width/2, picasso_spec, width, label='PICasso', color='#4ECDC4', alpha=0.8)
    
    ax1.set_ylabel('Spec@k Structural (%)', fontweight='bold')
    ax1.set_title('Spec@k Structural by Problem', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(problem_labels, rotation=45, ha='right', fontsize=8)
    if has_vanilla or has_picasso:
        ax1.legend()
    ax1.set_ylim(0, 105)
    ax1.grid(axis='y', alpha=0.3)
    
    # 2. Pass counts by problem
    ax2 = axes[1]
    vanilla_passes = [p['vanilla_pass'] for p in problem_data]
    picasso_passes = [p['picasso_pass'] for p in problem_data]
    vanilla_totals = [p['vanilla_total'] for p in problem_data]
    picasso_totals = [p['picasso_total'] for p in problem_data]
    
    x = np.arange(len(problem_labels))
    width = 0.35
    
    has_vanilla = any(v > 0 for v in vanilla_passes) or any(vt > 0 for vt in vanilla_totals)
    has_picasso = any(p > 0 for p in picasso_passes) or any(pt > 0 for pt in picasso_totals)
    
    if has_vanilla:
        bars1 = ax2.bar(x - width/2, vanilla_passes, width, label='Vanilla Passed', color='#FF6B6B', alpha=0.8)
        # Add total as text
        for i, (bar, total) in enumerate(zip(bars1, vanilla_totals)):
            height = bar.get_height()
            if total > 0:
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}/{total}',
                        ha='center', va='bottom', fontsize=8)
    
    if has_picasso:
        bars2 = ax2.bar(x + width/2, picasso_passes, width, label='PICasso Passed', color='#4ECDC4', alpha=0.8)
        # Add total as text
        for i, (bar, total) in enumerate(zip(bars2, picasso_totals)):
            height = bar.get_height()
            if total > 0:
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}/{total}',
                        ha='center', va='bottom', fontsize=8)
    
    ax2.set_ylabel('Pass Count', fontweight='bold')
    ax2.set_title('Pass Counts by Problem', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(problem_labels, rotation=45, ha='right', fontsize=8)
    if has_vanilla or has_picasso:
        ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved problem-by-problem comparison to: {output_path}")


def plot_improvement_metrics(vanilla_metrics: Dict, picasso_metrics: Dict, output_path: Path):
    """Plot improvement metrics showing how PICasso improves over Vanilla."""
    if not vanilla_metrics or not picasso_metrics:
        print("Cannot compute improvement: need both vanilla and picasso metrics")
        return
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    categories = [
        'Pass Rate',
        'Structural\nPass Rate',
        'Full Pass\nRate',
        'Spec@k\nStructural',
        'Spec@k Full',
        'Spec@k'
    ]
    
    vanilla_values = [
        vanilla_metrics.get('pass_rate', 0),
        vanilla_metrics.get('structural_pass_rate', 0),
        vanilla_metrics.get('full_pass_rate', 0),
        vanilla_metrics.get('spec_at_k_structural', 0) * 100,
        vanilla_metrics.get('spec_at_k_full', 0) * 100,
        vanilla_metrics.get('spec_at_k', 0) * 100
    ]
    
    picasso_values = [
        picasso_metrics.get('pass_rate', 0),
        picasso_metrics.get('structural_pass_rate', 0),
        picasso_metrics.get('full_pass_rate', 0),
        picasso_metrics.get('spec_at_k_structural', 0) * 100,
        picasso_metrics.get('spec_at_k_full', 0) * 100,
        picasso_metrics.get('spec_at_k', 0) * 100
    ]
    
    improvements = [p - v for v, p in zip(vanilla_values, picasso_values)]
    
    x = np.arange(len(categories))
    width = 0.25
    
    bars1 = ax.bar(x - width, vanilla_values, width, label='Vanilla', color='#FF6B6B', alpha=0.8)
    bars2 = ax.bar(x, picasso_values, width, label='PICasso', color='#4ECDC4', alpha=0.8)
    bars3 = ax.bar(x + width, improvements, width, label='Improvement', color='#95E1D3', alpha=0.8)
    
    ax.set_ylabel('Score (%)', fontweight='bold')
    ax.set_title('PICasso Framework Improvement Over Vanilla', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    # Add value labels
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            if abs(height) > 0.1:  # Only label if significant
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}%',
                       ha='center', va='bottom' if height >= 0 else 'top', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved improvement metrics to: {output_path}")


def print_summary(vanilla_metrics: Dict, picasso_metrics: Dict):
    """Print a text summary of the comparison."""
    print("\n" + "="*70)
    print("VANILLA vs PICASSO COMPARISON SUMMARY")
    print("="*70)
    
    if vanilla_metrics:
        print("\n📊 VANILLA (Phase 1) Metrics:")
        print(f"  Problems: {vanilla_metrics.get('num_problems', 0)}")
        print(f"  Total Samples: {vanilla_metrics.get('total_samples', 0)}")
        print(f"  Passed: {vanilla_metrics.get('total_passed', 0)}")
        print(f"  Pass Rate: {vanilla_metrics.get('pass_rate', 0):.2f}%")
        print(f"  Structural Pass Rate: {vanilla_metrics.get('structural_pass_rate', 0):.2f}%")
        print(f"  Full Pass Rate: {vanilla_metrics.get('full_pass_rate', 0):.2f}%")
        print(f"  Spec@k Structural: {vanilla_metrics.get('spec_at_k_structural', 0):.3f}")
        print(f"  Spec@k Full: {vanilla_metrics.get('spec_at_k_full', 0):.3f}")
        print(f"  Spec@k: {vanilla_metrics.get('spec_at_k', 0):.3f}")
    else:
        print("\n⚠️  No Vanilla metrics available")
    
    if picasso_metrics:
        print("\n🎨 PICASSO (Phase 2) Metrics:")
        print(f"  Problems: {picasso_metrics.get('num_problems', 0)}")
        print(f"  Total Samples: {picasso_metrics.get('total_samples', 0)}")
        print(f"  Passed: {picasso_metrics.get('total_passed', 0)}")
        print(f"  Pass Rate: {picasso_metrics.get('pass_rate', 0):.2f}%")
        print(f"  Structural Pass Rate: {picasso_metrics.get('structural_pass_rate', 0):.2f}%")
        print(f"  Full Pass Rate: {picasso_metrics.get('full_pass_rate', 0):.2f}%")
        print(f"  Spec@k Structural: {picasso_metrics.get('spec_at_k_structural', 0):.3f}")
        print(f"  Spec@k Full: {picasso_metrics.get('spec_at_k_full', 0):.3f}")
        print(f"  Spec@k: {picasso_metrics.get('spec_at_k', 0):.3f}")
        print(f"  Avg Opt Efficiency: {picasso_metrics.get('avg_opt_efficiency', 0):.3f}")
        print(f"  Robustness Score: {picasso_metrics.get('robustness_score', 0):.3f}")
    else:
        print("\n⚠️  No PICasso metrics available")
    
    if vanilla_metrics and picasso_metrics:
        print("\n📈 IMPROVEMENT (PICasso - Vanilla):")
        print(f"  Pass Rate: {picasso_metrics.get('pass_rate', 0) - vanilla_metrics.get('pass_rate', 0):+.2f}%")
        print(f"  Structural Pass Rate: {picasso_metrics.get('structural_pass_rate', 0) - vanilla_metrics.get('structural_pass_rate', 0):+.2f}%")
        print(f"  Full Pass Rate: {picasso_metrics.get('full_pass_rate', 0) - vanilla_metrics.get('full_pass_rate', 0):+.2f}%")
        print(f"  Spec@k Structural: {(picasso_metrics.get('spec_at_k_structural', 0) - vanilla_metrics.get('spec_at_k_structural', 0)) * 100:+.2f}%")
        print(f"  Spec@k Full: {(picasso_metrics.get('spec_at_k_full', 0) - vanilla_metrics.get('spec_at_k_full', 0)) * 100:+.2f}%")
        print(f"  Spec@k: {(picasso_metrics.get('spec_at_k', 0) - vanilla_metrics.get('spec_at_k', 0)) * 100:+.2f}%")
    
    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description='Plot and compare Vanilla vs PICasso results')
    parser.add_argument('--json', type=str, required=True,
                       help='Path to JSON results file')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='Output directory for plots (default: same as JSON file directory)')
    parser.add_argument('--prefix', type=str, default='comparison',
                       help='Prefix for output filenames (default: comparison)')
    
    args = parser.parse_args()
    
    json_path = Path(args.json)
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        return
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = json_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and separate results
    print(f"Loading results from: {json_path}")
    results = load_results(json_path)
    vanilla_results, picasso_results = separate_by_phase(results)
    
    print(f"Found {len(vanilla_results)} vanilla problems and {len(picasso_results)} picasso problems")
    
    # Extract metrics
    vanilla_metrics = extract_metrics(vanilla_results) if vanilla_results else {}
    picasso_metrics = extract_metrics(picasso_results) if picasso_results else {}
    
    # Print summary
    print_summary(vanilla_metrics, picasso_metrics)
    
    # Generate plots
    print("Generating plots...")
    
    # 1. Main comparison bar chart
    comparison_path = output_dir / f"{args.prefix}_bar_chart.png"
    plot_comparison_bar_chart(vanilla_metrics, picasso_metrics, comparison_path)
    
    # 2. Problem-by-problem comparison
    if vanilla_results or picasso_results:
        problem_path = output_dir / f"{args.prefix}_by_problem.png"
        plot_problem_by_problem_comparison(vanilla_results, picasso_results, problem_path)
    
    # 3. Improvement metrics
    if vanilla_metrics and picasso_metrics:
        improvement_path = output_dir / f"{args.prefix}_improvement.png"
        plot_improvement_metrics(vanilla_metrics, picasso_metrics, improvement_path)
    
    print(f"\n✅ All plots saved to: {output_dir}")


if __name__ == '__main__':
    main()

