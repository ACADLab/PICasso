"""
Test script to verify optimization efficiency calculation on a single problem.
Focuses on TASK 1 (MZI) which should have tunable parameters.
"""

import sys
import logging
from pathlib import Path
import json

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from extract_opt_efficiency import (
    load_merged_metrics,
    find_successful_samples,
    run_optimization_on_sample
)
from hf_inference_workflow.optimization_integration import OptimizationStage
from gd_picasso.metrics import compute_opt_efficiency

def test_single_problem(problem_id: int = 1, max_samples: int = 5):
    """Test optimization on a single problem."""
    logger.info(f"Testing optimization for Problem {problem_id}")
    
    # Load merged metrics
    merged_data = load_merged_metrics()
    if not merged_data:
        logger.error("Could not load merged metrics")
        return
    
    # Find successful samples for this problem
    successful_samples = find_successful_samples(merged_data)
    
    # Filter for the specific problem
    problem_samples = [
        s for s in successful_samples 
        if str(s['problem_id']) == str(problem_id)
    ]
    
    logger.info(f"Found {len(problem_samples)} successful samples for Problem {problem_id}")
    
    if not problem_samples:
        logger.error(f"No successful samples found for Problem {problem_id}")
        return
    
    # Test first few samples
    test_samples = problem_samples[:max_samples]
    
    optimizer = OptimizationStage(max_iter=50, n_restarts=2)
    
    success_count = 0
    for i, sample in enumerate(test_samples):
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing sample {i+1}/{len(test_samples)}")
        logger.info(f"Model: {sample['model']}, Phase: {sample['phase']}")
        logger.info(f"Problem: {sample['problem_id']}, Sample: {sample['sample_idx']}")
        logger.info(f"YAML: {sample.get('yaml_path')}")
        logger.info(f"GDS: {sample.get('gds_path')}")
        logger.info(f"{'='*80}")
        
        try:
            # Run optimization
            logger.info("Running optimization...")
            opt_result = run_optimization_on_sample(sample, optimizer)
            
            if opt_result is None:
                logger.warning("  ⚠️  Optimization returned None")
                continue
            
            logger.info(f"  Optimization result keys: {list(opt_result.keys())}")
            
            # Check for success - optimization may have run even if success=False
            # Check for loss data in various possible keys
            il_before = (opt_result.get('circuit_loss_before_db') or 
                        opt_result.get('il_before_db') or
                        opt_result.get('validation_reports', {}).get('optimization', {}).get('circuit_loss_before_db'))
            il_after = (opt_result.get('circuit_loss_after_db') or 
                       opt_result.get('il_after_db') or
                       opt_result.get('validation_reports', {}).get('optimization', {}).get('circuit_loss_after_db'))
            
            if il_before is not None or il_after is not None:
                
                logger.info(f"  Loss before: {il_before} dB")
                logger.info(f"  Loss after: {il_after} dB")
                
                if il_before is not None and il_after is not None:
                    # Calculate opt_efficiency
                    epsilon = 0.1
                    improvement = il_before - il_after
                    opt_eff = improvement / (il_before + epsilon) if il_before > 0 else 0.0
                    opt_eff = max(0.0, min(1.0, opt_eff))
                    
                    logger.info(f"  ✅ Opt Efficiency: {opt_eff:.4f}")
                    logger.info(f"  Improvement: {improvement:.4f} dB")
                    logger.info(f"  Loss: {il_before:.3f} dB → {il_after:.3f} dB")
                    success_count += 1
                else:
                    logger.warning(f"  ⚠️  Missing or invalid loss data (before: {il_before}, after: {il_after})")
            else:
                error = opt_result.get('error', 'Unknown error')
                logger.warning(f"  ⚠️  Optimization failed: {error}")
                
                # Log detailed error information
                if 'detailed_error' in opt_result:
                    logger.debug(f"  Detailed error: {opt_result['detailed_error']}")
        
        except Exception as e:
            logger.error(f"  ❌ Exception: {e}", exc_info=True)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY: {success_count}/{len(test_samples)} successful optimizations")
    logger.info(f"{'='*80}")

if __name__ == "__main__":
    # Test Problem 1 (MZI)
    test_single_problem(problem_id=1, max_samples=5)

