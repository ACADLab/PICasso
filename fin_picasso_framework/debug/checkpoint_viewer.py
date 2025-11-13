"""
Checkpoint Viewer

Utility to view checkpoints, list all checkpoints for a problem/sample,
show checkpoint details, compare checkpoints between stages, and export data.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CheckpointViewer:
    """
    View and analyze checkpoints.
    
    Provides utilities to:
    - List all checkpoints for a problem/sample
    - Show checkpoint details
    - Compare checkpoints between stages
    - Export checkpoint data
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize checkpoint viewer.
        
        Args:
            base_dir: Base directory for checkpoints (default: fin_picasso_framework/output/benchmark_results)
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "output" / "benchmark_results"
        
        self.base_dir = Path(base_dir)
        self.checkpoints_dir = self.base_dir / "checkpoints"
    
    def list_checkpoints(
        self,
        problem_idx: Optional[int] = None,
        sample_idx: Optional[int] = None,
        stage: Optional[str] = None
    ) -> List[Dict]:
        """
        List all checkpoints matching criteria.
        
        Args:
            problem_idx: Filter by problem index (None = all)
            sample_idx: Filter by sample index (None = all)
            stage: Filter by stage (None = all)
            
        Returns:
            List of checkpoint info dictionaries
        """
        checkpoints = []
        
        stages = ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']
        if stage:
            stages = [stage]
        
        for stage_name in stages:
            stage_dir = self.checkpoints_dir / stage_name
            if not stage_dir.exists():
                continue
            
            for checkpoint_file in stage_dir.glob("*.json"):
                try:
                    with open(checkpoint_file, 'r') as f:
                        checkpoint_data = json.load(f)
                    
                    # Apply filters
                    if problem_idx is not None and checkpoint_data.get('problem_idx') != problem_idx:
                        continue
                    if sample_idx is not None and checkpoint_data.get('sample_idx') != sample_idx:
                        continue
                    
                    checkpoints.append({
                        'file': str(checkpoint_file),
                        'stage': checkpoint_data.get('stage', stage_name),
                        'problem_idx': checkpoint_data.get('problem_idx'),
                        'sample_idx': checkpoint_data.get('sample_idx'),
                        'attempt': checkpoint_data.get('attempt'),
                        'status': checkpoint_data.get('status'),
                        'timestamp': checkpoint_data.get('timestamp'),
                    })
                except Exception as e:
                    logger.warning(f"Failed to read checkpoint {checkpoint_file}: {e}")
        
        # Sort by problem, sample, attempt, then stage
        checkpoints.sort(key=lambda x: (
            x.get('problem_idx', 0),
            x.get('sample_idx', 0),
            x.get('attempt', 0),
            x.get('stage', '')
        ))
        
        return checkpoints
    
    def get_checkpoint_details(self, checkpoint_file: Path) -> Dict:
        """
        Get detailed information about a checkpoint.
        
        Args:
            checkpoint_file: Path to checkpoint JSON file
            
        Returns:
            Dictionary with checkpoint details
        """
        checkpoint_file = Path(checkpoint_file)
        
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file}")
        
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
        
        # Add file info
        checkpoint_data['file_path'] = str(checkpoint_file)
        checkpoint_data['file_size'] = checkpoint_file.stat().st_size
        
        # Check if GDS file exists
        if 'gds_file' in checkpoint_data:
            gds_path = self.base_dir / checkpoint_data['gds_file']
            if gds_path.exists():
                checkpoint_data['gds_file_exists'] = True
                checkpoint_data['gds_file_size'] = gds_path.stat().st_size
            else:
                checkpoint_data['gds_file_exists'] = False
        
        return checkpoint_data
    
    def get_checkpoint_chain(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int
    ) -> List[Dict]:
        """
        Get all checkpoints for a specific problem/sample/attempt in order.
        
        Args:
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Attempt number
            
        Returns:
            List of checkpoint details in stage order
        """
        checkpoints = self.list_checkpoints(
            problem_idx=problem_idx,
            sample_idx=sample_idx
        )
        
        # Filter by attempt
        filtered = [c for c in checkpoints if c.get('attempt') == attempt]
        
        # Sort by stage order
        stage_order = ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']
        filtered.sort(key=lambda x: stage_order.index(x['stage']) if x['stage'] in stage_order else 999)
        
        # Load full details
        detailed = []
        for checkpoint in filtered:
            try:
                details = self.get_checkpoint_details(checkpoint['file'])
                detailed.append(details)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint details: {e}")
        
        return detailed
    
    def compare_checkpoints(
        self,
        checkpoint1_file: Path,
        checkpoint2_file: Path
    ) -> Dict:
        """
        Compare two checkpoints.
        
        Args:
            checkpoint1_file: Path to first checkpoint
            checkpoint2_file: Path to second checkpoint
            
        Returns:
            Comparison dictionary with differences
        """
        cp1 = self.get_checkpoint_details(checkpoint1_file)
        cp2 = self.get_checkpoint_details(checkpoint2_file)
        
        comparison = {
            'checkpoint1': {
                'file': str(checkpoint1_file),
                'stage': cp1.get('stage'),
                'status': cp1.get('status'),
                'timestamp': cp1.get('timestamp'),
            },
            'checkpoint2': {
                'file': str(checkpoint2_file),
                'stage': cp2.get('stage'),
                'status': cp2.get('status'),
                'timestamp': cp2.get('timestamp'),
            },
            'differences': []
        }
        
        # Compare status
        if cp1.get('status') != cp2.get('status'):
            comparison['differences'].append({
                'field': 'status',
                'checkpoint1': cp1.get('status'),
                'checkpoint2': cp2.get('status')
            })
        
        # Compare errors
        error1 = cp1.get('error')
        error2 = cp2.get('error')
        if error1 != error2:
            comparison['differences'].append({
                'field': 'error',
                'checkpoint1': error1,
                'checkpoint2': error2
            })
        
        # Compare validation reports if available
        report1 = cp1.get('validation_report', {})
        report2 = cp2.get('validation_report', {})
        if report1 != report2:
            comparison['differences'].append({
                'field': 'validation_report',
                'note': 'Validation reports differ (see individual checkpoints for details)'
            })
        
        return comparison
    
    def export_checkpoint_data(
        self,
        problem_idx: int,
        sample_idx: int,
        output_file: Optional[Path] = None
    ) -> Path:
        """
        Export all checkpoint data for a problem/sample to JSON.
        
        Args:
            problem_idx: Problem index
            sample_idx: Sample index
            output_file: Output file path (default: auto-generated)
            
        Returns:
            Path to exported file
        """
        if output_file is None:
            output_file = self.base_dir / f"checkpoints_export_problem_{problem_idx}_sample_{sample_idx}.json"
        
        checkpoints = self.list_checkpoints(
            problem_idx=problem_idx,
            sample_idx=sample_idx
        )
        
        # Load full details for each checkpoint
        export_data = {
            'problem_idx': problem_idx,
            'sample_idx': sample_idx,
            'export_timestamp': datetime.now().isoformat(),
            'checkpoints': []
        }
        
        for checkpoint in checkpoints:
            try:
                details = self.get_checkpoint_details(checkpoint['file'])
                export_data['checkpoints'].append(details)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {checkpoint['file']}: {e}")
        
        # Save export
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Exported {len(export_data['checkpoints'])} checkpoints to {output_file}")
        return output_file
    
    def print_checkpoint_summary(
        self,
        problem_idx: int,
        sample_idx: int
    ):
        """
        Print a summary of all checkpoints for a problem/sample.
        
        Args:
            problem_idx: Problem index
            sample_idx: Sample index
        """
        checkpoints = self.list_checkpoints(
            problem_idx=problem_idx,
            sample_idx=sample_idx
        )
        
        print(f"\n{'='*70}")
        print(f"Checkpoint Summary: Problem {problem_idx}, Sample {sample_idx}")
        print(f"{'='*70}")
        print(f"Total checkpoints: {len(checkpoints)}")
        print()
        
        # Group by attempt
        attempts = {}
        for cp in checkpoints:
            attempt = cp.get('attempt', 0)
            if attempt not in attempts:
                attempts[attempt] = []
            attempts[attempt].append(cp)
        
        for attempt in sorted(attempts.keys()):
            print(f"Attempt {attempt}:")
            print("-" * 70)
            for cp in sorted(attempts[attempt], key=lambda x: x.get('stage', '')):
                status_symbol = "✅" if cp.get('status') == 'pass' else "❌"
                print(f"  {status_symbol} {cp.get('stage', 'unknown'):12s} - {cp.get('status', 'unknown'):4s} - {cp.get('timestamp', 'N/A')}")
            print()


