"""
Result Saver Module

Saves code, GDS files, validation reports at each stage with structured organization.
Creates checkpoint files with timestamps, stage names, status, and error messages.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
import gdsfactory as gf

logger = logging.getLogger(__name__)


class ResultSaver:
    """
    Saves results in structured format for benchmarking and debugging.
    
    Organizes results into:
    - raw_llm/ - Code before framework processing
    - framework_processed/ - After framework processing
    - checkpoints/ - Debug checkpoints at each stage
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize result saver.
        
        Args:
            base_dir: Base directory for results (default: fin_picasso_framework/output/benchmark_results)
        """
        if base_dir is None:
            base_dir = Path(__file__).parent.parent / "output" / "benchmark_results"
        
        self.base_dir = Path(base_dir)
        self._create_directory_structure()
    
    def _create_directory_structure(self):
        """Create directory structure for results."""
        directories = [
            self.base_dir / "raw_llm" / "code",
            self.base_dir / "raw_llm" / "gds",
            self.base_dir / "raw_llm" / "errors",
            self.base_dir / "framework_processed" / "code",
            self.base_dir / "framework_processed" / "gds",
            self.base_dir / "framework_processed" / "validation_reports",
            self.base_dir / "framework_processed" / "optimization",
            self.base_dir / "checkpoints" / "pilot",
            self.base_dir / "checkpoints" / "pnr",
            self.base_dir / "checkpoints" / "drc",
            self.base_dir / "checkpoints" / "sax",
            self.base_dir / "checkpoints" / "functional",
            self.base_dir / "checkpoints" / "optimization",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save_raw_llm_code(
        self,
        code: str,
        problem_idx: int,
        sample_idx: int,
        attempt: int = 0,
        error: Optional[str] = None
    ) -> Path:
        """
        Save raw LLM-generated code (before framework processing).
        
        Args:
            code: Generated code
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Attempt number (default: 0 for first attempt)
            error: Error message if any
            
        Returns:
            Path to saved file
        """
        filename = f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}.py"
        filepath = self.base_dir / "raw_llm" / "code" / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Problem {problem_idx}, Sample {sample_idx}, Attempt {attempt}\n")
            if error:
                f.write(f"# Error: {error}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("\n")
            f.write(code)
        
        logger.debug(f"Saved raw LLM code to {filepath}")
        return filepath
    
    def save_raw_llm_error(
        self,
        error: str,
        problem_idx: int,
        sample_idx: int,
        attempt: int = 0
    ) -> Path:
        """
        Save raw LLM error log.
        
        Args:
            error: Error message
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Attempt number
            
        Returns:
            Path to saved file
        """
        filename = f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}_error.txt"
        filepath = self.base_dir / "raw_llm" / "errors" / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Problem {problem_idx}, Sample {sample_idx}, Attempt {attempt}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write("=" * 70 + "\n\n")
            f.write(error)
        
        logger.debug(f"Saved raw LLM error to {filepath}")
        return filepath
    
    def save_raw_llm_gds(
        self,
        component: gf.Component,
        problem_idx: int,
        sample_idx: int,
        attempt: int = 0
    ) -> Optional[Path]:
        """
        Save raw LLM GDS file (if component was generated).
        
        Args:
            component: GDSFactory component
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Attempt number
            
        Returns:
            Path to saved GDS file, or None if save failed
        """
        try:
            filename = f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}.gds"
            filepath = self.base_dir / "raw_llm" / "gds" / filename
            
            component.write_gds(str(filepath))
            logger.debug(f"Saved raw LLM GDS to {filepath}")
            return filepath
        except Exception as e:
            logger.warning(f"Failed to save raw LLM GDS: {e}")
            return None
    
    def save_framework_code(
        self,
        code: str,
        problem_idx: int,
        sample_idx: int,
        attempt: int,
        success: bool
    ) -> Path:
        """
        Save framework-processed code (after retries and validation).
        
        Args:
            code: Final code
            problem_idx: Problem index
            sample_idx: Sample index
            attempt: Final attempt number
            success: Whether generation succeeded
            
        Returns:
            Path to saved file
        """
        filename = f"problem_{problem_idx}_sample_{sample_idx}_final.py"
        filepath = self.base_dir / "framework_processed" / "code" / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Problem {problem_idx}, Sample {sample_idx}\n")
            f.write(f"# Final Attempt: {attempt}\n")
            f.write(f"# Success: {success}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write("\n")
            f.write(code)
        
        logger.debug(f"Saved framework code to {filepath}")
        return filepath
    
    def save_framework_gds(
        self,
        component: gf.Component,
        problem_idx: int,
        sample_idx: int
    ) -> Optional[Path]:
        """
        Save framework-processed GDS file.
        
        Args:
            component: Final GDSFactory component
            problem_idx: Problem index
            sample_idx: Sample index
            
        Returns:
            Path to saved GDS file, or None if save failed
        """
        try:
            filename = f"problem_{problem_idx}_sample_{sample_idx}_final.gds"
            filepath = self.base_dir / "framework_processed" / "gds" / filename
            
            component.write_gds(str(filepath))
            logger.debug(f"Saved framework GDS to {filepath}")
            return filepath
        except Exception as e:
            logger.warning(f"Failed to save framework GDS: {e}")
            return None
    
    def save_validation_report(
        self,
        validation_reports: Dict,
        problem_idx: int,
        sample_idx: int
    ) -> Path:
        """
        Save validation reports as JSON.
        
        Args:
            validation_reports: Dictionary of validation reports
            problem_idx: Problem index
            sample_idx: Sample index
            
        Returns:
            Path to saved JSON file
        """
        filename = f"problem_{problem_idx}_sample_{sample_idx}_validation.json"
        filepath = self.base_dir / "framework_processed" / "validation_reports" / filename
        
        # Convert to JSON-serializable format
        json_data = self._make_json_serializable(validation_reports)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, default=str)
        
        logger.debug(f"Saved validation report to {filepath}")
        return filepath
    
    def save_optimization_result(
        self,
        optimization_result: Dict,
        problem_idx: int,
        sample_idx: int
    ) -> Path:
        """
        Save optimization results as JSON.
        
        Args:
            optimization_result: Optimization result dictionary
            problem_idx: Problem index
            sample_idx: Sample index
            
        Returns:
            Path to saved JSON file
        """
        filename = f"problem_{problem_idx}_sample_{sample_idx}_optimization.json"
        filepath = self.base_dir / "framework_processed" / "optimization" / filename
        
        json_data = self._make_json_serializable(optimization_result)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, default=str)
        
        logger.debug(f"Saved optimization result to {filepath}")
        return filepath
    
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
        timestamp = datetime.now().isoformat()
        filename = f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}_{stage}.json"
        filepath = self.base_dir / "checkpoints" / stage / filename
        
        checkpoint_data = {
            'timestamp': timestamp,
            'stage': stage,
            'problem_idx': problem_idx,
            'sample_idx': sample_idx,
            'attempt': attempt,
            'status': status,
            'error': error,
            'metadata': metadata or {}
        }
        
        # Add code if provided
        if code:
            checkpoint_data['code'] = code
        
        # Add validation report if provided
        if validation_report:
            checkpoint_data['validation_report'] = self._make_json_serializable(validation_report)
        
        # Save component as GDS if provided
        if component:
            try:
                gds_filename = filename.replace('.json', '.gds')
                gds_filepath = self.base_dir / "checkpoints" / stage / gds_filename
                component.write_gds(str(gds_filepath))
                checkpoint_data['gds_file'] = str(gds_filepath.relative_to(self.base_dir))
            except Exception as e:
                logger.warning(f"Failed to save checkpoint GDS: {e}")
                checkpoint_data['gds_save_error'] = str(e)
        
        # Save checkpoint JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)
        
        logger.debug(f"Saved checkpoint to {filepath}")
        return filepath
    
    def _make_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)
    
    def get_result_summary(
        self,
        problem_idx: int,
        sample_idx: int
    ) -> Dict:
        """
        Get summary of all saved results for a problem/sample.
        
        Args:
            problem_idx: Problem index
            sample_idx: Sample index
            
        Returns:
            Dictionary with paths to all saved files
        """
        summary = {
            'problem_idx': problem_idx,
            'sample_idx': sample_idx,
            'raw_llm': {},
            'framework_processed': {},
            'checkpoints': {}
        }
        
        # Find raw LLM files
        raw_code_dir = self.base_dir / "raw_llm" / "code"
        raw_gds_dir = self.base_dir / "raw_llm" / "gds"
        raw_errors_dir = self.base_dir / "raw_llm" / "errors"
        
        pattern = f"problem_{problem_idx}_sample_{sample_idx}_*"
        
        summary['raw_llm']['code'] = [str(f) for f in raw_code_dir.glob(pattern + ".py")]
        summary['raw_llm']['gds'] = [str(f) for f in raw_gds_dir.glob(pattern + ".gds")]
        summary['raw_llm']['errors'] = [str(f) for f in raw_errors_dir.glob(pattern + "_error.txt")]
        
        # Find framework processed files
        framework_code_dir = self.base_dir / "framework_processed" / "code"
        framework_gds_dir = self.base_dir / "framework_processed" / "gds"
        framework_reports_dir = self.base_dir / "framework_processed" / "validation_reports"
        framework_opt_dir = self.base_dir / "framework_processed" / "optimization"
        
        summary['framework_processed']['code'] = [
            str(f) for f in framework_code_dir.glob(f"problem_{problem_idx}_sample_{sample_idx}_final.py")
        ]
        summary['framework_processed']['gds'] = [
            str(f) for f in framework_gds_dir.glob(f"problem_{problem_idx}_sample_{sample_idx}_final.gds")
        ]
        summary['framework_processed']['validation_reports'] = [
            str(f) for f in framework_reports_dir.glob(f"problem_{problem_idx}_sample_{sample_idx}_validation.json")
        ]
        summary['framework_processed']['optimization'] = [
            str(f) for f in framework_opt_dir.glob(f"problem_{problem_idx}_sample_{sample_idx}_optimization.json")
        ]
        
        # Find checkpoints
        for stage in ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']:
            checkpoint_dir = self.base_dir / "checkpoints" / stage
            summary['checkpoints'][stage] = [
                str(f) for f in checkpoint_dir.glob(f"problem_{problem_idx}_sample_{sample_idx}_*_{stage}.json")
            ]
        
        return summary


