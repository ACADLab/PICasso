#!/usr/bin/env python3
"""
Analyze optimization results across all models and problems.
Compares before vs after optimization for device-level and circuit-level.
Generates CSV, JSON, and plots.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from extract_opt_efficiency import run_optimization_on_sample, find_successful_samples, load_merged_metrics

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
RESULTS_DIR = OUTPUT_DIR / "optimization_analysis"
RESULTS_DIR.mkdir(exist_ok=True)


def process_all_samples(max_samples_per_problem: int = 5, max_problems: Optional[int] = None) -> List[Dict]:
    """
    Process all successful samples and run optimization.
    
    Args:
        max_samples_per_problem: Maximum samples to process per problem
        max_problems: Maximum problems to process (None = all)
    
    Returns:
        List of optimization results
    """
    logger.info("Loading merged metrics...")
    merged_data = load_merged_metrics()
    
    logger.info("Finding successful samples...")
    successful_samples = find_successful_samples(merged_data)
    
    logger.info(f"Found {len(successful_samples)} successful samples")
    
    # Group by problem to limit samples per problem
    samples_by_problem = {}
    for sample in successful_samples:
        key = (sample['model'], sample['phase'], sample['problem_id'])
        if key not in samples_by_problem:
            samples_by_problem[key] = []
        samples_by_problem[key].append(sample)
    
    # Limit samples per problem
    samples_to_process = []
    for key, samples in samples_by_problem.items():
        samples_to_process.extend(samples[:max_samples_per_problem])
    
    logger.info(f"Processing {len(samples_to_process)} samples (max {max_samples_per_problem} per problem)")
    
    results = []
    total = len(samples_to_process)
    
    for idx, sample in enumerate(samples_to_process, 1):
        model = sample['model']
        phase = sample['phase']
        problem_id = sample['problem_id']
        sample_idx = sample['sample_idx']
        yaml_path = sample.get('yaml_path')
        
        if yaml_path is None:
            logger.warning(f"Skipping {model}/{phase}/problem_{problem_id}/sample_{sample_idx} - no YAML file")
            continue
        
        logger.info(f"[{idx}/{total}] Processing {model}/{phase}/problem_{problem_id}/sample_{sample_idx}")
        
        try:
            # Create optimizer instance
            from hf_inference_workflow.optimization_integration import OptimizationStage
            optimizer = OptimizationStage()
            
            # run_optimization_on_sample expects a dict with yaml_path, gds_path, circuit_type
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
                logger.info(f"  ✅ Success: Loss {result.get('circuit_loss_before_db', 'N/A'):.2f} → {result.get('circuit_loss_after_db', 'N/A'):.2f} dB")
            else:
                logger.warning(f"  ⚠️  Optimization returned None")
                
        except Exception as e:
            logger.error(f"  ❌ Error: {e}", exc_info=True)
            continue
    
    return results


def save_results(results: List[Dict], format: str = 'both'):
    """Save results to CSV and/or JSON."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format in ['csv', 'both']:
        csv_path = RESULTS_DIR / f"optimization_results_{timestamp}.csv"
        
        # Flatten results for CSV
        rows = []
        for r in results:
            row = {
                'model': r.get('model'),
                'phase': r.get('phase'),
                'problem_id': r.get('problem_id'),
                'sample_idx': r.get('sample_idx'),
                'device_loss_before_db': r.get('device_loss_db', 0.0),
                'device_loss_after_db': r.get('device_loss_db', 0.0),  # Device-level doesn't change
                'circuit_loss_before_db': r.get('circuit_loss_before_db'),
                'circuit_loss_after_db': r.get('circuit_loss_after_db'),
                'total_loss_before_db': r.get('circuit_loss_before_db', 0.0) + r.get('device_loss_db', 0.0),
                'total_loss_after_db': r.get('circuit_loss_after_db', 0.0) + r.get('device_loss_db', 0.0),
                'improvement_db': r.get('improvement_db', 0.0),
                'opt_efficiency': r.get('opt_efficiency', 0.0),
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False)
        logger.info(f"✅ Saved CSV to: {csv_path}")
    
    if format in ['json', 'both']:
        json_path = RESULTS_DIR / f"optimization_results_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"✅ Saved JSON to: {json_path}")
    
    return csv_path if format in ['csv', 'both'] else None, json_path if format in ['json', 'both'] else None


def create_plots(csv_path: Path):
    """Create visualization plots from CSV data."""
    df = pd.read_csv(csv_path)
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Optimization Results: Before vs After', fontsize=16, fontweight='bold')
    
    # 1. Circuit-level loss: Before vs After
    ax1 = axes[0, 0]
    before = df['circuit_loss_before_db'].dropna()
    after = df['circuit_loss_after_db'].dropna()
    
    ax1.scatter(before, after, alpha=0.6, s=50)
    max_val = max(before.max(), after.max()) if len(before) > 0 and len(after) > 0 else 10
    ax1.plot([0, max_val], [0, max_val], 'r--', label='No improvement')
    ax1.set_xlabel('Circuit Loss Before (dB)', fontsize=12)
    ax1.set_ylabel('Circuit Loss After (dB)', fontsize=12)
    ax1.set_title('Circuit-Level Optimization', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Total loss: Before vs After
    ax2 = axes[0, 1]
    total_before = df['total_loss_before_db'].dropna()
    total_after = df['total_loss_after_db'].dropna()
    
    ax2.scatter(total_before, total_after, alpha=0.6, s=50, color='green')
    max_val = max(total_before.max(), total_after.max()) if len(total_before) > 0 and len(total_after) > 0 else 10
    ax2.plot([0, max_val], [0, max_val], 'r--', label='No improvement')
    ax2.set_xlabel('Total Loss Before (dB)', fontsize=12)
    ax2.set_ylabel('Total Loss After (dB)', fontsize=12)
    ax2.set_title('Total Loss Optimization', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Improvement distribution
    ax3 = axes[1, 0]
    improvement = df['improvement_db'].dropna()
    if len(improvement) > 0:
        ax3.hist(improvement, bins=30, alpha=0.7, color='purple', edgecolor='black')
        ax3.axvline(0, color='r', linestyle='--', label='No improvement')
        ax3.set_xlabel('Improvement (dB)', fontsize=12)
        ax3.set_ylabel('Frequency', fontsize=12)
        ax3.set_title('Improvement Distribution', fontsize=14, fontweight='bold')
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Opt Efficiency distribution
    ax4 = axes[1, 1]
    opt_eff = df['opt_efficiency'].dropna()
    if len(opt_eff) > 0:
        ax4.hist(opt_eff, bins=30, alpha=0.7, color='orange', edgecolor='black')
        ax4.set_xlabel('Optimization Efficiency', fontsize=12)
        ax4.set_ylabel('Frequency', fontsize=12)
        ax4.set_title('Optimization Efficiency Distribution', fontsize=14, fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    plot_path = RESULTS_DIR / f"optimization_plots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    logger.info(f"✅ Saved plot to: {plot_path}")
    
    return plot_path


def create_summary_statistics(csv_path: Path):
    """Create summary statistics and save to text file."""
    df = pd.read_csv(csv_path)
    
    stats = []
    stats.append("=" * 80)
    stats.append("OPTIMIZATION ANALYSIS SUMMARY")
    stats.append("=" * 80)
    stats.append("")
    
    stats.append(f"Total samples analyzed: {len(df)}")
    stats.append(f"Models: {df['model'].nunique()}")
    stats.append(f"Problems: {df['problem_id'].nunique()}")
    stats.append("")
    
    # Circuit-level statistics
    stats.append("CIRCUIT-LEVEL OPTIMIZATION:")
    stats.append("-" * 80)
    before_mean = df['circuit_loss_before_db'].mean()
    after_mean = df['circuit_loss_after_db'].mean()
    improvement_mean = df['improvement_db'].mean()
    stats.append(f"  Mean loss before: {before_mean:.3f} dB")
    stats.append(f"  Mean loss after:  {after_mean:.3f} dB")
    stats.append(f"  Mean improvement: {improvement_mean:.3f} dB")
    stats.append(f"  Samples improved: {(df['improvement_db'] > 0).sum()} / {len(df)} ({(df['improvement_db'] > 0).sum() / len(df) * 100:.1f}%)")
    stats.append("")
    
    # Opt efficiency statistics
    stats.append("OPTIMIZATION EFFICIENCY:")
    stats.append("-" * 80)
    opt_eff_mean = df['opt_efficiency'].mean()
    opt_eff_median = df['opt_efficiency'].median()
    stats.append(f"  Mean: {opt_eff_mean:.4f}")
    stats.append(f"  Median: {opt_eff_median:.4f}")
    stats.append(f"  Max: {df['opt_efficiency'].max():.4f}")
    stats.append("")
    
    # By model
    stats.append("BY MODEL:")
    stats.append("-" * 80)
    for model in sorted(df['model'].unique()):
        model_df = df[df['model'] == model]
        stats.append(f"  {model}:")
        stats.append(f"    Samples: {len(model_df)}")
        stats.append(f"    Mean improvement: {model_df['improvement_db'].mean():.3f} dB")
        stats.append(f"    Mean opt efficiency: {model_df['opt_efficiency'].mean():.4f}")
        stats.append("")
    
    stats_text = "\n".join(stats)
    
    stats_path = RESULTS_DIR / f"summary_statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(stats_path, 'w') as f:
        f.write(stats_text)
    
    logger.info(f"✅ Saved summary statistics to: {stats_path}")
    print("\n" + stats_text)
    
    return stats_path


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description='Analyze optimization results across all models')
    parser.add_argument('--max-samples', type=int, default=5, help='Max samples per problem (default: 5)')
    parser.add_argument('--max-problems', type=int, default=None, help='Max problems to process (default: all)')
    parser.add_argument('--skip-optimization', action='store_true', help='Skip optimization, use existing results')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("OPTIMIZATION ANALYSIS")
    logger.info("=" * 80)
    
    if not args.skip_optimization:
        logger.info("Processing all samples and running optimization...")
        results = process_all_samples(max_samples_per_problem=args.max_samples, max_problems=args.max_problems)
        
        if not results:
            logger.error("No results to save!")
            return
        
        logger.info(f"\n✅ Processed {len(results)} samples")
        csv_path, json_path = save_results(results)
    else:
        # Find most recent CSV
        csv_files = list(RESULTS_DIR.glob("optimization_results_*.csv"))
        if not csv_files:
            logger.error("No existing CSV files found. Run without --skip-optimization first.")
            return
        csv_path = max(csv_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"Using existing CSV: {csv_path}")
    
    logger.info("\n" + "=" * 80)
    logger.info("CREATING VISUALIZATIONS")
    logger.info("=" * 80)
    
    plot_path = create_plots(csv_path)
    stats_path = create_summary_statistics(csv_path)
    
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"📊 CSV data: {csv_path}")
    if not args.skip_optimization:
        logger.info(f"📄 JSON data: {json_path}")
    logger.info(f"📈 Plot: {plot_path}")
    logger.info(f"📋 Statistics: {stats_path}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

