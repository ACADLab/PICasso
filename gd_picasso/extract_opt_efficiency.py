#!/usr/bin/env python3
"""
Extract opt_efficiency from existing successful samples by running optimization on GDS files.

This script:
1. Finds all successful samples (structural_pass=True) with GDS files
2. Runs actual optimization on each GDS file
3. Calculates opt_efficiency from loss measurements
4. Updates metrics CSV files with new values
5. Recomputes problem-level metrics
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import gdsfactory as gf

# Import optimization and metrics
try:
    from hf_inference_workflow.optimization_integration import OptimizationStage
    OPTIMIZATION_AVAILABLE = True
except ImportError:
    OPTIMIZATION_AVAILABLE = False
    print("⚠️  Warning: hf_inference_workflow.optimization_integration not available")
    print("   Trying alternative import...")
    try:
        from fin_picasso_framework.optimization_integration import OptimizationStage
        OPTIMIZATION_AVAILABLE = True
    except ImportError:
        print("❌ Error: Could not import OptimizationStage")
        sys.exit(1)

from gd_picasso.metrics import compute_opt_efficiency, compute_metrics_for_circuit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def load_merged_metrics() -> Dict:
    """Load the most recent merged metrics JSON file."""
    merged_files = list(OUTPUT_DIR.glob("merged_finished_metrics_*.json"))
    if not merged_files:
        logger.error("No merged metrics JSON file found")
        return {}
    
    # Get most recent file
    latest_file = max(merged_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Loading merged metrics from: {latest_file}")
    
    with open(latest_file) as f:
        return json.load(f)


def find_successful_samples(merged_data: Dict) -> List[Dict]:
    """
    Find all successful samples that have YAML files (preferred) or GDS files.
    
    Returns list of dicts with: model, phase, problem_id, sample_idx, yaml_path, gds_path
    """
    successful_samples = []
    
    for model_name, model_data in merged_data.items():
        for phase in ['vanilla', 'picasso']:
            if phase not in model_data:
                continue
            
            problems = model_data[phase]
            for problem_id, problem_data in problems.items():
                if problem_id.endswith('_summary'):
                    continue
                
                samples = problem_data.get('samples', [])
                for sample in samples:
                    if sample.get('structural_pass') == True:
                        # Check if YAML file exists (preferred - has netlist info)
                        yaml_path = OUTPUT_DIR / f"{model_name}_results" / phase / f"problem_{problem_id}" / f"sample_{sample['sample_idx']}" / "circuit.yaml"
                        gds_path = OUTPUT_DIR / f"{model_name}_results" / phase / f"problem_{problem_id}" / f"sample_{sample['sample_idx']}" / "circuit.gds"
                        
                        # Prefer YAML, but accept GDS if YAML doesn't exist
                        if yaml_path.exists() or gds_path.exists():
                            successful_samples.append({
                                'model': model_name,
                                'phase': phase,
                                'problem_id': problem_id,
                                'sample_idx': sample['sample_idx'],
                                'yaml_path': yaml_path if yaml_path.exists() else None,
                                'gds_path': gds_path if gds_path.exists() else None,
                                'circuit_type': None  # Will try to infer from problem
                            })
    
    logger.info(f"Found {len(successful_samples)} successful samples with YAML/GDS files")
    return successful_samples


def get_circuit_type_from_problem(problem_id: str, problems_file: Path = None) -> Optional[str]:
    """Try to infer circuit type from problem ID."""
    if problems_file is None:
        problems_file = Path(__file__).parent / "problems_parsed.txt"
    
    if not problems_file.exists():
        return None
    
    try:
        with open(problems_file) as f:
            content = f.read()
            # Look for problem number
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith(f"TASK {problem_id}") or (i > 0 and f"TASK {problem_id}" in lines[i-1]):
                    # Try to extract circuit type from next few lines
                    for j in range(i, min(i+10, len(lines))):
                        if 'MZM' in lines[j] or 'Modulator' in lines[j]:
                            return 'mzm'
                        elif 'Ring' in lines[j] or 'Filter' in lines[j]:
                            return 'ring_filter'
                        elif 'Switch' in lines[j]:
                            return 'switch'
                        elif 'Splitter' in lines[j]:
                            return 'splitter'
                    break
    except Exception as e:
        logger.debug(f"Could not infer circuit type: {e}")
    
    return None


def fix_netlist_structure(netlist: Dict) -> Optional[Dict]:
    """Fix netlist structure if instances have wrong format."""
    if 'instances' not in netlist:
        return None
    
    fixed = netlist.copy()
    fixed_instances = {}
    
    for inst_name, inst_data in netlist['instances'].items():
        if isinstance(inst_data, str):
            # Instance is just a string (component name)
            fixed_instances[inst_name] = {'component': inst_data, 'settings': {}}
        elif isinstance(inst_data, dict):
            # Check if it has 'model' instead of 'component'
            if 'model' in inst_data and 'component' not in inst_data:
                fixed_inst = inst_data.copy()
                fixed_inst['component'] = fixed_inst.pop('model')
                fixed_instances[inst_name] = fixed_inst
            else:
                fixed_instances[inst_name] = inst_data
        else:
            logger.warning(f"Unknown instance format for {inst_name}: {type(inst_data)}")
            continue
    
    fixed['instances'] = fixed_instances
    return fixed


def run_optimization_on_sample(sample_info: Dict, optimizer: OptimizationStage) -> Optional[Dict]:
    """
    Run optimization on a single sample's YAML or GDS file.
    
    Prefers YAML file (has netlist info), falls back to GDS if needed.
    Handles YAML validation errors by trying to fix them.
    
    Returns dict with opt_efficiency and loss data, or None if failed.
    """
    yaml_path = sample_info.get('yaml_path')
    gds_path = sample_info.get('gds_path')
    circuit_type = sample_info.get('circuit_type')
    
    try:
        component = None
        
        # Prefer YAML file (has netlist information)
        if yaml_path and yaml_path.exists():
            logger.debug(f"Loading YAML: {yaml_path}")
            try:
                with open(yaml_path, 'r') as f:
                    yaml_str = f.read()
                component = gf.read.from_yaml(yaml_str)
            except Exception as e:
                # YAML might have validation errors - try to fix placements
                logger.debug(f"YAML load failed, trying to fix: {e}")
                try:
                    import yaml as yaml_lib
                    data = yaml_lib.safe_load(yaml_str)
                    # Fix None placements
                    if 'placements' in data:
                        placements = data['placements']
                        fixed_placements = {}
                        for key, value in placements.items():
                            if value is not None:
                                fixed_placements[key] = value
                            else:
                                # Set default placement if None
                                fixed_placements[key] = {'x': 0, 'y': 0}
                        data['placements'] = fixed_placements
                        yaml_str = yaml_lib.dump(data, default_flow_style=False)
                        component = gf.read.from_yaml(yaml_str)
                        logger.debug("Fixed YAML placements and reloaded")
                except Exception as e2:
                    logger.debug(f"YAML fix failed: {e2}")
                    component = None
        
        # Fallback to GDS if YAML failed
        if component is None and gds_path and gds_path.exists():
            logger.debug(f"Loading GDS: {gds_path}")
            try:
                component = gf.import_gds(str(gds_path))
            except Exception as e:
                logger.warning(f"GDS load also failed: {e}")
                return None
        
        if component is None:
            logger.warning(f"Could not load component from YAML or GDS")
            return None
        
        # Try to extract tunables from YAML if netlist extraction fails
        tunables_from_yaml = None
        netlist_from_yaml = None
        
        if yaml_path and yaml_path.exists():
            try:
                import yaml as yaml_lib
                with open(yaml_path, 'r') as f:
                    yaml_data = yaml_lib.safe_load(f.read())
                
                # Create minimal netlist from YAML
                if 'instances' in yaml_data:
                    # Extract connections from routes.optical.links if connections key doesn't exist
                    connections = yaml_data.get('connections', {})
                    if not connections and 'routes' in yaml_data:
                        routes = yaml_data.get('routes', {})
                        if isinstance(routes, dict) and 'optical' in routes:
                            optical_routes = routes['optical']
                            if isinstance(optical_routes, dict) and 'links' in optical_routes:
                                connections = optical_routes['links']
                                logger.debug(f"Extracted {len(connections)} connections from routes.optical.links")
                    
                    netlist_from_yaml = {
                        'instances': yaml_data['instances'],
                        'connections': connections,
                        'ports': yaml_data.get('ports', {})
                    }
                    
                    # Extract tunables directly from YAML instances
                    from netlist_optimize import Tunable
                    import numpy as np
                    tunables_list = []
                    for inst_name, inst_data in yaml_data['instances'].items():
                        if isinstance(inst_data, dict):
                            comp_type = inst_data.get('component', '')
                            settings = inst_data.get('settings', {})
                            
                            # Check for heater/phase shifter components
                            if any(kw in comp_type.lower() for kw in ['heater', 'phase', 'shifter']):
                                tunables_list.append(Tunable(
                                    inst=inst_name,
                                    key='phi',
                                    lo=-np.pi,
                                    hi=np.pi,
                                    x0=settings.get('phi', 0.0)
                                ))
                    
                    if tunables_list:
                        tunables_from_yaml = tunables_list
                        logger.debug(f"Extracted {len(tunables_from_yaml)} tunables from YAML")
            except Exception as e:
                logger.debug(f"Could not extract tunables from YAML: {e}")
        
        # Run optimization
        model_name = sample_info.get('model', 'unknown')
        phase_name = sample_info.get('phase', 'unknown')
        problem_id = sample_info.get('problem_id', 'unknown')
        sample_idx = sample_info.get('sample_idx', 'unknown')
        logger.debug(f"Running optimization for {model_name} {phase_name} problem {problem_id} sample {sample_idx}")
        
        # Validate netlist structure before optimization
        if netlist_from_yaml is None:
            logger.warning("No netlist available - cannot optimize")
            return None
        
        # Ensure netlist has required structure
        if 'instances' not in netlist_from_yaml:
            logger.warning("Netlist missing 'instances' key")
            return None
        
        # Validate instances structure
        for inst_name, inst_data in netlist_from_yaml['instances'].items():
            if not isinstance(inst_data, dict):
                logger.warning(f"Instance {inst_name} is not a dict: {type(inst_data)}")
                continue
            if 'component' not in inst_data:
                logger.warning(f"Instance {inst_name} missing 'component' key, keys: {list(inst_data.keys())}")
        
        # Pass YAML netlist and tunables directly to optimize_design to bypass GDSFactory netlist extraction
        # This is important because circuits that passed DRC/LVS may still fail GDSFactory's strict netlist extraction
        try:
            opt_result = optimizer.optimize_design(
                component, 
                circuit_type=circuit_type,
                netlist=netlist_from_yaml,  # Use YAML netlist directly
                tunables=tunables_from_yaml  # Use YAML-extracted tunables
            )
        except KeyError as e:
            if 'model' in str(e):
                logger.error(f"KeyError 'model' - netlist structure issue. Instances: {list(netlist_from_yaml.get('instances', {}).keys())[:3]}")
                # Try to fix: check if instances have wrong structure
                fixed_netlist = fix_netlist_structure(netlist_from_yaml)
                if fixed_netlist:
                    logger.info("Attempting with fixed netlist structure")
                    opt_result = optimizer.optimize_design(
                        component,
                        circuit_type=circuit_type,
                        netlist=fixed_netlist,
                        tunables=tunables_from_yaml
                    )
                else:
                    raise
            else:
                raise
        
        # Extract loss data - we need both before and after for opt_efficiency
        circuit_loss_before = opt_result.get('circuit_loss_before_db')
        circuit_loss_after = opt_result.get('circuit_loss_after_db')
        
        # Check if we have valid loss data (both must be present and > 0)
        if circuit_loss_before is None or circuit_loss_after is None:
            # No circuit-level optimization data (likely no tunable parameters)
            logger.debug(f"No circuit loss data (before={circuit_loss_before}, after={circuit_loss_after}) - likely no tunable parameters")
            return None
        
        if circuit_loss_before <= 0 or circuit_loss_after < 0:
            logger.debug(f"Invalid loss values (before={circuit_loss_before}, after={circuit_loss_after})")
            return None
        
        # Calculate opt_efficiency
        # Create a result dict in the format expected by compute_opt_efficiency
        result_dict = {
            'validation_reports': {
                'optimization': {
                    'circuit_loss_before_db': circuit_loss_before,
                    'circuit_loss_after_db': circuit_loss_after
                }
            }
        }
        
        opt_eff = compute_opt_efficiency(result_dict)
        
        return {
            'opt_efficiency': opt_eff,
            'circuit_loss_before_db': circuit_loss_before,
            'circuit_loss_after_db': circuit_loss_after,
            'device_loss_db': opt_result.get('device_loss_db'),
            'total_loss_db': opt_result.get('total_loss_db'),
            'improvement_db': opt_result.get('improvement_db', 0.0)
        }
        
    except Exception as e:
        logger.warning(f"Failed to optimize {gds_path}: {e}")
        return None


def update_metrics_csv(model_name: str, opt_results: Dict[Tuple[str, str, str, int], Dict], output_dir: Path = None) -> bool:
    """
    Update metrics CSV file with new opt_efficiency values.
    
    Args:
        model_name: Model name
        opt_results: Dict mapping (phase, problem_id, sample_idx) -> opt_result
        output_dir: Output directory
    
    Returns:
        True if successful, False otherwise
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR
    
    csv_path = output_dir / f"{model_name}_results" / "metrics.csv"
    
    if not csv_path.exists():
        logger.warning(f"Metrics CSV not found: {csv_path}")
        return False
    
    # Read existing CSV
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
    
    if not fieldnames:
        logger.error(f"CSV file has no headers: {csv_path}")
        return False
    
    # Update rows with opt_efficiency
    updated_count = 0
    for row in rows:
        phase = row.get('phase', '').lower()
        problem_id = str(row.get('problem_id', ''))
        try:
            sample_idx = int(row.get('sample_idx', 0))
        except (ValueError, TypeError):
            continue
        
        key = (phase, problem_id, str(sample_idx))
        if key in opt_results:
            opt_result = opt_results[key]
            # Update opt_eff column
            row['opt_eff'] = str(opt_result['opt_efficiency'])
            updated_count += 1
    
    # Write updated CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logger.info(f"Updated {updated_count} rows in {csv_path}")
    
    # Now recompute problem-level metrics
    recompute_problem_metrics(csv_path, opt_results)
    
    return True


def recompute_problem_metrics(csv_path: Path, opt_results: Dict[Tuple[str, str, str], Dict]):
    """
    Recompute problem-level metrics (avg opt_efficiency, robustness_score) after updating opt_eff.
    
    Note: opt_eff is a problem-level metric (same for all samples of a problem).
    We compute the average across all samples, then update all samples with the same value.
    """
    # Read all rows
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
    
    # Group samples by problem
    problem_samples = {}
    for row in rows:
        phase = row.get('phase', '').lower()
        problem_id = str(row.get('problem_id', ''))
        key = (phase, problem_id)
        
        if key not in problem_samples:
            problem_samples[key] = []
        problem_samples[key].append(row)
    
    # For each problem, compute average opt_efficiency from all samples
    problem_opt_effs = {}
    for (phase, problem_id), samples in problem_samples.items():
        opt_effs = []
        for sample in samples:
            try:
                opt_eff = float(sample.get('opt_eff', 0) or 0)
                if opt_eff > 0:
                    opt_effs.append(opt_eff)
            except (ValueError, TypeError):
                pass
        
        if opt_effs:
            # Average opt_efficiency across all samples of this problem
            avg_opt_eff = sum(opt_effs) / len(opt_effs)
        else:
            avg_opt_eff = 0.0
        
        problem_opt_effs[(phase, problem_id)] = avg_opt_eff
    
    # Update all rows with problem-level metrics
    for row in rows:
        phase = row.get('phase', '').lower()
        problem_id = str(row.get('problem_id', ''))
        key = (phase, problem_id)
        
        if key in problem_opt_effs:
            # Update opt_eff (problem-level, same for all samples of this problem)
            row['opt_eff'] = str(problem_opt_effs[key])
            
            # Recompute robustness_score if we have spec_at_k
            try:
                # Try spec_at_k first, fallback to spec_at_k_structural
                spec_at_k_str = row.get('spec_at_k', '0') or row.get('spec_at_k_structural', '0') or '0'
                spec_at_k = float(spec_at_k_str)
                opt_eff = problem_opt_effs[key]
                robust_pass_str = row.get('robust_pass', '0') or '0'
                robust_pass = float(robust_pass_str)
                
                # Robustness score formula: R = Spec@k × (α + β·OptEff + γ·RobustPass)
                # Default: α=0.5, β=0.2, γ=0.3
                alpha, beta, gamma = 0.5, 0.2, 0.3
                robustness = spec_at_k * (alpha + beta * opt_eff + gamma * robust_pass)
                robustness = max(0.0, min(1.0, robustness))
                
                row['robustness_score'] = str(robustness)
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not recompute robustness_score for {key}: {e}")
    
    # Write back
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logger.info(f"Recomputed problem-level metrics for {csv_path}")


def main():
    """Main function to extract and update opt_efficiency."""
    logger.info("=" * 80)
    logger.info("Extracting Opt Efficiency from Existing Samples")
    logger.info("=" * 80)
    
    if not OPTIMIZATION_AVAILABLE:
        logger.error("OptimizationStage not available. Cannot proceed.")
        return
    
    # Initialize optimizer
    logger.info("Initializing optimizer...")
    optimizer = OptimizationStage(enable_optimization=True, enable_device_optimization=True)
    
    # Load merged metrics to find successful samples
    logger.info("Loading merged metrics...")
    merged_data = load_merged_metrics()
    if not merged_data:
        logger.error("Failed to load merged metrics")
        return
    
    # Find successful samples
    logger.info("Finding successful samples with GDS files...")
    successful_samples = find_successful_samples(merged_data)
    
    if not successful_samples:
        logger.warning("No successful samples found with GDS files")
        return
    
    # Group by model for processing
    samples_by_model = {}
    for sample in successful_samples:
        model = sample['model']
        if model not in samples_by_model:
            samples_by_model[model] = []
        samples_by_model[model].append(sample)
    
    # Process each model
    all_opt_results = {}
    total_processed = 0
    total_successful = 0
    
    # Limit processing for testing (remove this after verification)
    # samples_by_model = {k: v[:5] for k, v in samples_by_model.items()}  # Test with first 5 samples per model
    
    for model_name, samples in samples_by_model.items():
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Processing {model_name}: {len(samples)} samples")
        logger.info(f"{'=' * 80}")
        
        model_opt_results = {}
        
        for i, sample_info in enumerate(samples, 1):
            logger.info(f"[{i}/{len(samples)}] Processing {sample_info['phase']} problem {sample_info['problem_id']} sample {sample_info['sample_idx']}")
            
            # Try to infer circuit type
            if sample_info['circuit_type'] is None:
                sample_info['circuit_type'] = get_circuit_type_from_problem(sample_info['problem_id'])
            
            # Run optimization
            opt_result = run_optimization_on_sample(sample_info, optimizer)
            total_processed += 1
            
            if opt_result:
                total_successful += 1
                # Key format: (phase, problem_id, sample_idx_str)
                key = (sample_info['phase'].lower(), str(sample_info['problem_id']), str(sample_info['sample_idx']))
                model_opt_results[key] = opt_result
                logger.info(f"  ✅ Opt Efficiency: {opt_result['opt_efficiency']:.4f} "
                          f"(Loss: {opt_result['circuit_loss_before_db']:.2f} → {opt_result['circuit_loss_after_db']:.2f} dB)")
            else:
                logger.info(f"  ⚠️  Optimization failed or no loss data")
        
        # Update CSV for this model
        if model_opt_results:
            logger.info(f"\nUpdating metrics CSV for {model_name}...")
            update_metrics_csv(model_name, model_opt_results)
            all_opt_results[model_name] = model_opt_results
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total samples processed: {total_processed}")
    logger.info(f"Successful optimizations: {total_successful}")
    logger.info(f"Success rate: {total_successful/total_processed*100:.1f}%")
    
    # Show opt_efficiency statistics by model
    logger.info("\nOpt Efficiency by Model:")
    for model_name, results in all_opt_results.items():
        opt_effs = [r['opt_efficiency'] for r in results.values()]
        if opt_effs:
            avg_opt_eff = sum(opt_effs) / len(opt_effs)
            max_opt_eff = max(opt_effs)
            logger.info(f"  {model_name}: avg={avg_opt_eff:.4f}, max={max_opt_eff:.4f}, count={len(opt_effs)}")
    
    logger.info("\n✅ Done! Metrics CSV files have been updated.")
    logger.info("   Run merge_metrics.py to regenerate merged JSON with updated opt_efficiency values.")


if __name__ == "__main__":
    main()

