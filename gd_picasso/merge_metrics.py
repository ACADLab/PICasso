#!/usr/bin/env python3
"""
Merge all metrics CSV files from different models into a single JSON file.
Organizes by model -> phase -> problem -> samples
"""

import csv
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def convert_value(value):
    """Convert string values to appropriate types."""
    if value == '':
        return None
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    try:
        # Try to convert to float
        float_val = float(value)
        # If it's a whole number, return as int if reasonable
        if float_val.is_integer() and abs(float_val) < 1e10:
            return int(float_val)
        return float_val
    except ValueError:
        return value

def merge_all_metrics(output_dir: Path = None):
    """Merge all metrics CSV files into a single JSON structure."""
    if output_dir is None:
        output_dir = Path(__file__).parent / "output"
    
    # Find all metrics.csv files
    metrics_files = list(output_dir.glob("*_results/metrics.csv"))
    
    if not metrics_files:
        print(f"❌ No metrics.csv files found in {output_dir}")
        return None
    
    print(f"Found {len(metrics_files)} metrics files")
    
    # Structure: {model: {phase: {problem_id: {summary: {...}, samples: [...]}}}}
    merged_data = {}
    
    for csv_path in sorted(metrics_files):
        model_name = csv_path.parent.name.replace("_results", "")
        print(f"Processing {model_name}...")
        
        if model_name not in merged_data:
            merged_data[model_name] = {
                "vanilla": {},
                "picasso": {}
            }
        
        # Read CSV
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                
                # Group by phase and problem
                phase_problem_data = defaultdict(lambda: defaultdict(list))
                
                for row in reader:
                    phase = row.get('phase', '').lower()
                    problem_id = row.get('problem_id', '')
                    
                    if phase not in ['vanilla', 'picasso'] or not problem_id:
                        continue
                    
                    # Convert all values
                    sample_data = {}
                    for key, value in row.items():
                        sample_data[key] = convert_value(value)
                    
                    phase_problem_data[phase][problem_id].append(sample_data)
                
                # Organize by phase and problem
                for phase in ['vanilla', 'picasso']:
                    if phase not in phase_problem_data:
                        continue
                    
                    for problem_id in sorted(phase_problem_data[phase].keys(), key=lambda x: int(x) if x.isdigit() else 0):
                        samples = phase_problem_data[phase][problem_id]
                        
                        # Calculate summary statistics
                        summary = {
                            "problem_id": problem_id,
                            "num_samples": len(samples),
                            "structural_pass_count": sum(1 for s in samples if s.get('structural_pass') == True),
                            "functional_pass_count": sum(1 for s in samples if s.get('functional_pass') == True),
                            "drc_passed_count": sum(1 for s in samples if s.get('drc_passed') == True),
                            "lvs_passed_count": sum(1 for s in samples if s.get('lvs_passed') == True),
                            "opt_done_count": sum(1 for s in samples if s.get('opt_done') == True),
                        }
                        
                        # Get problem-level metrics (these are the same for all samples of a problem)
                        if samples:
                            first_sample = samples[0]
                            summary["pass_at_k"] = first_sample.get('pass_at_k')
                            summary["spec_at_k_structural"] = first_sample.get('spec_at_k_structural')
                            summary["spec_at_k_full"] = first_sample.get('spec_at_k_full')
                            summary["spec_at_k"] = first_sample.get('spec_at_k')
                            summary["opt_eff"] = first_sample.get('opt_eff')
                            summary["robust_pass"] = first_sample.get('robust_pass')
                            summary["robustness_score"] = first_sample.get('robustness_score')
                        
                        # Calculate percentages
                        if summary["num_samples"] > 0:
                            summary["structural_pass_rate"] = summary["structural_pass_count"] / summary["num_samples"]
                            summary["functional_pass_rate"] = summary["functional_pass_count"] / summary["num_samples"]
                            summary["drc_passed_rate"] = summary["drc_passed_count"] / summary["num_samples"]
                            summary["lvs_passed_rate"] = summary["lvs_passed_count"] / summary["num_samples"]
                            summary["opt_done_rate"] = summary["opt_done_count"] / summary["num_samples"]
                        else:
                            summary["structural_pass_rate"] = 0.0
                            summary["functional_pass_rate"] = 0.0
                            summary["drc_passed_rate"] = 0.0
                            summary["lvs_passed_rate"] = 0.0
                            summary["opt_done_rate"] = 0.0
                        
                        # Store in merged structure
                        merged_data[model_name][phase][problem_id] = {
                            "summary": summary,
                            "samples": samples
                        }
        
        except Exception as e:
            print(f"  ⚠️  Error processing {model_name}: {e}")
            continue
    
    # Add overall summary for each model
    for model_name in merged_data:
        for phase in ['vanilla', 'picasso']:
            problems = merged_data[model_name][phase]
            if problems:
                total_problems = len(problems)
                total_samples = sum(p["summary"]["num_samples"] for p in problems.values())
                total_structural_pass = sum(p["summary"]["structural_pass_count"] for p in problems.values())
                total_functional_pass = sum(p["summary"]["functional_pass_count"] for p in problems.values())
                
                merged_data[model_name][f"{phase}_summary"] = {
                    "total_problems": total_problems,
                    "total_samples": total_samples,
                    "total_structural_pass": total_structural_pass,
                    "total_functional_pass": total_functional_pass,
                    "structural_pass_rate": total_structural_pass / total_samples if total_samples > 0 else 0.0,
                    "functional_pass_rate": total_functional_pass / total_samples if total_samples > 0 else 0.0,
                }
    
    return merged_data

def main():
    """Main function to merge metrics and save to JSON."""
    output_dir = Path(__file__).parent / "output"
    
    print("=" * 80)
    print("Merging All Metrics CSV Files")
    print("=" * 80)
    print()
    
    merged_data = merge_all_metrics(output_dir)
    
    if merged_data is None:
        return
    
    # Generate filename with datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"merged_finished_metrics_{timestamp}.json"
    
    # Save to JSON
    print()
    print(f"Saving merged data to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(merged_data, f, indent=2)
    
    print(f"✅ Successfully merged {len(merged_data)} models")
    print(f"   Output: {output_file}")
    
    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for model_name in sorted(merged_data.keys()):
        model = merged_data[model_name]
        vanilla_summary = model.get("vanilla_summary", {})
        picasso_summary = model.get("picasso_summary", {})
        
        print(f"\n{model_name}:")
        if vanilla_summary:
            print(f"  Vanilla: {vanilla_summary.get('total_problems', 0)} problems, "
                  f"{vanilla_summary.get('total_samples', 0)} samples")
        if picasso_summary:
            print(f"  Picasso: {picasso_summary.get('total_problems', 0)} problems, "
                  f"{picasso_summary.get('total_samples', 0)} samples")

if __name__ == "__main__":
    main()


