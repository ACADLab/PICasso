#!/usr/bin/env python3
"""
Extract the data used in the initial_loss_vanilla_vs_picasso.png plot.
Filter out models without fair comparison (need both vanilla and picasso data).
Save to CSV with summary statistics.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import glob

OUTPUT_DIR = Path(__file__).parent / "output"
RESULTS_DIR = OUTPUT_DIR / "optimization_analysis"

def load_and_filter_data():
    """Load optimization data and filter for fair comparison."""
    csv_files = glob.glob(str(RESULTS_DIR / "optimization_results_*.csv"))
    if not csv_files:
        raise FileNotFoundError("No optimization CSV files found")
    
    latest = max(csv_files)
    print(f"Loading from: {Path(latest).name}")
    df = pd.read_csv(latest)
    
    # Filter out 150 dB (false calculation)
    df = df[df['circuit_loss_before_db'] < 100].copy()
    
    print(f"\nOriginal data: {len(df)} samples")
    print(f"  Models: {df['model'].nunique()}")
    
    # Check data availability by model
    model_stats = df.groupby(['model', 'phase']).size().unstack(fill_value=0)
    print("\nData availability by model:")
    print("-" * 80)
    for model in sorted(df['model'].unique()):
        vanilla_count = len(df[(df['model'] == model) & (df['phase'] == 'vanilla')])
        picasso_count = len(df[(df['model'] == model) & (df['phase'] == 'picasso')])
        print(f"  {model:25s} Vanilla: {vanilla_count:3d}, Picasso: {picasso_count:3d}")
    
    # Filter: Keep only models with BOTH vanilla and picasso data (at least 1 sample each)
    models_with_both = []
    for model in df['model'].unique():
        vanilla_count = len(df[(df['model'] == model) & (df['phase'] == 'vanilla')])
        picasso_count = len(df[(df['model'] == model) & (df['phase'] == 'picasso')])
        if vanilla_count > 0 and picasso_count > 0:
            models_with_both.append(model)
    
    print(f"\nModels with both Vanilla and Picasso data: {len(models_with_both)}")
    print(f"  {', '.join(models_with_both)}")
    
    # Filter dataframe
    df_filtered = df[df['model'].isin(models_with_both)].copy()
    
    print(f"\nFiltered data: {len(df_filtered)} samples")
    print(f"  Models: {df_filtered['model'].nunique()}")
    print(f"  Vanilla: {len(df_filtered[df_filtered['phase'] == 'vanilla'])}")
    print(f"  Picasso: {len(df_filtered[df_filtered['phase'] == 'picasso'])}")
    
    return df_filtered, models_with_both

def create_summary_statistics(df):
    """Create summary statistics table data."""
    stats_rows = []
    
    # Overall statistics
    vanilla_circuit = df[df['phase'] == 'vanilla']['circuit_loss_before_db'].dropna()
    picasso_circuit = df[df['phase'] == 'picasso']['circuit_loss_before_db'].dropna()
    
    vanilla_total = df[df['phase'] == 'vanilla']['total_loss_before_db'].dropna()
    picasso_total = df[df['phase'] == 'picasso']['total_loss_before_db'].dropna()
    
    vanilla_device = df[df['phase'] == 'vanilla']['device_loss_before_db'].dropna()
    picasso_device = df[df['phase'] == 'picasso']['device_loss_before_db'].dropna()
    
    vanilla_improve = df[df['phase'] == 'vanilla']['improvement_db'].mean()
    picasso_improve = df[df['phase'] == 'picasso']['improvement_db'].mean()
    
    stats_rows.append({
        'metric': 'Mean Initial Circuit Loss',
        'vanilla_value': vanilla_circuit.mean() if len(vanilla_circuit) > 0 else np.nan,
        'picasso_value': picasso_circuit.mean() if len(picasso_circuit) > 0 else np.nan,
        'improvement': (vanilla_circuit.mean() - picasso_circuit.mean()) if len(vanilla_circuit) > 0 and len(picasso_circuit) > 0 else np.nan,
        'unit': 'dB'
    })
    
    stats_rows.append({
        'metric': 'Median Initial Circuit Loss',
        'vanilla_value': vanilla_circuit.median() if len(vanilla_circuit) > 0 else np.nan,
        'picasso_value': picasso_circuit.median() if len(picasso_circuit) > 0 else np.nan,
        'improvement': (vanilla_circuit.median() - picasso_circuit.median()) if len(vanilla_circuit) > 0 and len(picasso_circuit) > 0 else np.nan,
        'unit': 'dB'
    })
    
    stats_rows.append({
        'metric': 'Mean Initial Total Loss',
        'vanilla_value': vanilla_total.mean() if len(vanilla_total) > 0 else np.nan,
        'picasso_value': picasso_total.mean() if len(picasso_total) > 0 else np.nan,
        'improvement': (vanilla_total.mean() - picasso_total.mean()) if len(vanilla_total) > 0 and len(picasso_total) > 0 else np.nan,
        'unit': 'dB'
    })
    
    stats_rows.append({
        'metric': 'Mean Initial Device Loss',
        'vanilla_value': vanilla_device.mean() if len(vanilla_device) > 0 else np.nan,
        'picasso_value': picasso_device.mean() if len(picasso_device) > 0 else np.nan,
        'improvement': (vanilla_device.mean() - picasso_device.mean()) if len(vanilla_device) > 0 and len(picasso_device) > 0 else np.nan,
        'unit': 'dB'
    })
    
    stats_rows.append({
        'metric': 'Mean Optimization Improvement',
        'vanilla_value': vanilla_improve,
        'picasso_value': picasso_improve,
        'improvement': picasso_improve - vanilla_improve,
        'unit': 'dB'
    })
    
    stats_rows.append({
        'metric': 'Samples Improved (Circuit Loss)',
        'vanilla_value': (df[df['phase'] == 'vanilla']['improvement_db'] > 0).sum(),
        'picasso_value': (df[df['phase'] == 'picasso']['improvement_db'] > 0).sum(),
        'improvement': (df[df['phase'] == 'picasso']['improvement_db'] > 0).sum() - (df[df['phase'] == 'vanilla']['improvement_db'] > 0).sum(),
        'unit': 'count'
    })
    
    return pd.DataFrame(stats_rows)

def create_detailed_data_csv(df):
    """Create detailed CSV with all data used in the plot."""
    # Create per-sample data
    sample_data = []
    
    for _, row in df.iterrows():
        sample_data.append({
            'model': row['model'],
            'phase': row['phase'],
            'problem_id': row['problem_id'],
            'sample_idx': row['sample_idx'],
            'device_loss_before_db': row['device_loss_before_db'],
            'device_loss_after_db': row['device_loss_after_db'],
            'circuit_loss_before_db': row['circuit_loss_before_db'],
            'circuit_loss_after_db': row['circuit_loss_after_db'],
            'total_loss_before_db': row['total_loss_before_db'],
            'total_loss_after_db': row['total_loss_after_db'],
            'improvement_db': row['improvement_db'],
            'opt_efficiency': row['opt_efficiency'],
        })
    
    # Create per-model summary
    model_summary = []
    for model in sorted(df['model'].unique()):
        model_df = df[df['model'] == model]
        
        for phase in ['vanilla', 'picasso']:
            phase_df = model_df[model_df['phase'] == phase]
            if len(phase_df) == 0:
                continue
            
            model_summary.append({
                'model': model,
                'phase': phase,
                'num_samples': len(phase_df),
                'mean_circuit_loss_before_db': phase_df['circuit_loss_before_db'].mean(),
                'median_circuit_loss_before_db': phase_df['circuit_loss_before_db'].median(),
                'std_circuit_loss_before_db': phase_df['circuit_loss_before_db'].std(),
                'mean_device_loss_before_db': phase_df['device_loss_before_db'].mean(),
                'mean_total_loss_before_db': phase_df['total_loss_before_db'].mean(),
                'mean_improvement_db': phase_df['improvement_db'].mean(),
                'mean_opt_efficiency': phase_df['opt_efficiency'].mean(),
                'samples_improved': (phase_df['improvement_db'] > 0).sum(),
            })
    
    # Create per-problem comparison
    problem_comparison = []
    for problem_id in sorted(df['problem_id'].unique()):
        problem_df = df[df['problem_id'] == problem_id]
        
        vanilla_df = problem_df[problem_df['phase'] == 'vanilla']
        picasso_df = problem_df[problem_df['phase'] == 'picasso']
        
        if len(vanilla_df) == 0 or len(picasso_df) == 0:
            continue
        
        problem_comparison.append({
            'problem_id': problem_id,
            'vanilla_samples': len(vanilla_df),
            'picasso_samples': len(picasso_df),
            'vanilla_mean_circuit_loss_before_db': vanilla_df['circuit_loss_before_db'].mean(),
            'picasso_mean_circuit_loss_before_db': picasso_df['circuit_loss_before_db'].mean(),
            'improvement_db': vanilla_df['circuit_loss_before_db'].mean() - picasso_df['circuit_loss_before_db'].mean(),
            'picasso_better': 1 if picasso_df['circuit_loss_before_db'].mean() < vanilla_df['circuit_loss_before_db'].mean() else 0,
        })
    
    return pd.DataFrame(sample_data), pd.DataFrame(model_summary), pd.DataFrame(problem_comparison)

if __name__ == "__main__":
    print("=" * 80)
    print("EXTRACTING PLOT DATA")
    print("=" * 80)
    
    df, models_with_both = load_and_filter_data()
    
    # Create detailed data
    sample_df, model_summary_df, problem_comparison_df = create_detailed_data_csv(df)
    stats_df = create_summary_statistics(df)
    
    # Save to CSV
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Main data CSV
    main_csv = RESULTS_DIR / f"initial_loss_plot_data_{timestamp}.csv"
    sample_df.to_csv(main_csv, index=False)
    print(f"\n✅ Saved sample data to: {main_csv}")
    
    # Model summary CSV
    model_csv = RESULTS_DIR / f"initial_loss_model_summary_{timestamp}.csv"
    model_summary_df.to_csv(model_csv, index=False)
    print(f"✅ Saved model summary to: {model_csv}")
    
    # Problem comparison CSV
    problem_csv = RESULTS_DIR / f"initial_loss_problem_comparison_{timestamp}.csv"
    problem_comparison_df.to_csv(problem_csv, index=False)
    print(f"✅ Saved problem comparison to: {problem_csv}")
    
    # Summary statistics CSV
    stats_csv = RESULTS_DIR / f"initial_loss_summary_statistics_{timestamp}.csv"
    stats_df.to_csv(stats_csv, index=False)
    print(f"✅ Saved summary statistics to: {stats_csv}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS (from table in plot)")
    print("=" * 80)
    print(stats_df.to_string(index=False))
    print("\n" + "=" * 80)
    print(f"📊 All data files saved to: {RESULTS_DIR}")
    print("=" * 80)

