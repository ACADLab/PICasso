"""
Checkpoint Manager

Saves state at each validation stage for debugging and analysis.
Manages checkpoints with code, components, validation results, and error messages.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import gdsfactory as gf

from ..utils.result_saver import ResultSaver

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoints at each validation stage.
    
    Saves state including:
    - Code at that point
    - Component object (if available)
    - Validation results
    - Error messages
    - Timestamp and stage name
    """
    
    def __init__(self, result_saver: Optional[ResultSaver] = None):
        """
        Initialize checkpoint manager.
        
        Args:
            result_saver: ResultSaver instance (creates new one if None)
        """
        self.result_saver = result_saver or ResultSaver()
        self.checkpoints = []  # In-memory checkpoint list
    
    def save_checkpoint(
        self,
        stage: str,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        status: str,
        code: Optional[str] = None,
        component: Optional[gf.Component] = None,
        validation_report: Optional[Dict] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Path:
        """
        Save checkpoint at a validation stage.
        
        Args:
            stage: Stage name (pilot, pnr, drc, sax, functional, optimization)
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Attempt number
            status: Status (pass, fail, error)
            code: Code at this stage
            component: Component at this stage (if available)
            validation_report: Validation report (if available)
            error: Error message (if failed)
            metadata: Additional metadata
            
        Returns:
            Path to saved checkpoint file
        """
        checkpoint_path = self.result_saver.save_checkpoint(
            stage=stage,
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            component=component,
            validation_report=validation_report,
            error=error,
            metadata=metadata
        )
        
        # Store in memory
        self.checkpoints.append({
            'stage': stage,
            'problem_idx': problem_idx,
            'sample_idx': sample_idx,
            'attempt': attempt,
            'status': status,
            'path': str(checkpoint_path),
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(f"Checkpoint saved: {stage} - {status} (problem {problem_idx}, sample {sample_idx}, attempt {attempt})")
        return checkpoint_path
    
    def save_pilot_checkpoint(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        code: str,
        passed: bool,
        error: Optional[str] = None
    ) -> Path:
        """Save checkpoint after pilot validation."""
        status = "pass" if passed else "fail"
        return self.save_checkpoint(
            stage="pilot",
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            error=error,
            metadata={'validation_type': 'pilot'}
        )
    
    def save_pnr_checkpoint(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        component: gf.Component,
        code: str,
        validation_report: Dict,
        passed: bool
    ) -> Path:
        """Save checkpoint after P&R validation."""
        status = "pass" if passed else "fail"
        error = None if passed else validation_report.get('errors', ['Unknown error'])[0] if validation_report.get('errors') else None
        return self.save_checkpoint(
            stage="pnr",
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            component=component,
            validation_report=validation_report,
            error=error,
            metadata={'validation_type': 'pnr'}
        )
    
    def save_drc_checkpoint(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        component: gf.Component,
        code: str,
        validation_report: Dict,
        passed: bool
    ) -> Path:
        """Save checkpoint after DRC validation."""
        status = "pass" if passed else "fail"
        violations = validation_report.get('violations', 0)
        error = None if passed else f"DRC violations: {violations}"
        return self.save_checkpoint(
            stage="drc",
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            component=component,
            validation_report=validation_report,
            error=error,
            metadata={'validation_type': 'drc', 'violations': violations}
        )
    
    def save_sax_checkpoint(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        component: gf.Component,
        code: str,
        validation_report: Dict,
        passed: bool
    ) -> Path:
        """Save checkpoint after SAX validation."""
        status = "pass" if passed else "fail"
        error = None if passed else validation_report.get('errors', ['Unknown error'])[0] if validation_report.get('errors') else None
        return self.save_checkpoint(
            stage="sax",
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            component=component,
            validation_report=validation_report,
            error=error,
            metadata={'validation_type': 'sax'}
        )
    
    def save_functional_checkpoint(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        component: gf.Component,
        code: str,
        validation_report: Dict,
        passed: bool
    ) -> Path:
        """Save checkpoint after functional validation."""
        status = "pass" if passed else "fail"
        error = None if passed else validation_report.get('error', 'Functional test failed')
        return self.save_checkpoint(
            stage="functional",
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            component=component,
            validation_report=validation_report,
            error=error,
            metadata={'validation_type': 'functional'}
        )
    
    def save_optimization_checkpoint(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        component: gf.Component,
        code: str,
        optimization_result: Dict
    ) -> Path:
        """Save checkpoint after optimization."""
        status = "pass" if optimization_result.get('success', False) else "fail"
        error = None if status == "pass" else optimization_result.get('error', 'Optimization failed')
        return self.save_checkpoint(
            stage="optimization",
            problem_idx=problem_idx,
            sample_idx=sample_idx,
            attempt=attempt,
            status=status,
            code=code,
            component=component,
            validation_report=optimization_result,
            error=error,
            metadata={'validation_type': 'optimization'}
        )
    
    def get_checkpoints(
        self,
        problem_idx: Optional[int] = None,
        sample_idx: Optional[int] = None,
        stage: Optional[str] = None
    ) -> List[Dict]:
        """
        Get checkpoints matching criteria.
        
        Args:
            problem_idx: Filter by problem index (None = all)
            sample_idx: Filter by sample index (None = all)
            stage: Filter by stage (None = all)
            
        Returns:
            List of checkpoint dictionaries
        """
        filtered = self.checkpoints
        
        if problem_idx is not None:
            filtered = [c for c in filtered if c['problem_idx'] == problem_idx]
        
        if sample_idx is not None:
            filtered = [c for c in filtered if c['sample_idx'] == sample_idx]
        
        if stage is not None:
            filtered = [c for c in filtered if c['stage'] == stage]
        
        return filtered
    
    def get_checkpoint_chain(
        self,
        problem_idx: int,
        sample_idx: int,
        attempt: int
    ) -> List[Dict]:
        """
        Get all checkpoints for a specific problem/sample/attempt.
        
        Args:
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Attempt number
            
        Returns:
            List of checkpoints in order
        """
        checkpoints = self.get_checkpoints(
            problem_idx=problem_idx,
            sample_idx=sample_idx
        )
        
        # Filter by attempt and sort by stage order
        stage_order = ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']
        filtered = [c for c in checkpoints if c['attempt'] == attempt]
        filtered.sort(key=lambda x: stage_order.index(x['stage']) if x['stage'] in stage_order else 999)
        
        return filtered
    
    def clear_checkpoints(self):
        """Clear in-memory checkpoint list."""
        self.checkpoints = []

