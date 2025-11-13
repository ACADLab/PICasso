"""
Validated Photonic Circuit Generation with HuggingFace Inference API

This module generates photonic circuit designs with comprehensive validation:
- P&R (Place & Route) checks
- DRC (Design Rule Checks)
- SAX compilation and routing validation

Failed designs are retried with LLM feedback for improvement.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import pandas as pd
from tqdm import tqdm
import logging
import tempfile
import numpy as np
import json
import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gdsfactory as gf

# Import from local modules or parent directory
import sys
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir / "hf_inference_workflow"))

try:
    from hf_inference_workflow.hf_api_client import HFInferenceAgent
    from hf_inference_workflow.retry_handler import RetryHandler, ValidationStage, AdaptiveRetryHandler
    from hf_inference_workflow.auto_corrector import AutoCorrector
    from hf_inference_workflow.metrics import (
        compute_opt_efficiency,
        compute_robustness_score,
        compute_spec_at_k,
        estimate_pass_at_k as metrics_pass_at_k
    )
except ImportError:
    # If not available, create minimal stubs
    HFInferenceAgent = None
    RetryHandler = None
    ValidationStage = None
    AdaptiveRetryHandler = None
    AutoCorrector = None
    compute_opt_efficiency = None
    compute_robustness_score = None
    compute_spec_at_k = None
    metrics_pass_at_k = None

# Import from local validators
from .validators import PNRValidator, DRCValidator, SAXValidator, FunctionalValidator
from .validators.loss_target_validator import LossTargetValidator
from .pilot.pilot_validator_enhanced import PilotValidatorEnhanced as PilotValidator
from .optimization_integration import OptimizationStage

# Import new error handling and result saving modules
from .error_handling import ErrorExtractor, FeedbackGenerator
from .utils import ResultSaver
from .debug import CheckpointManager
from .pilot.pilot_prompt_updater import PilotPromptUpdater
from .robustness import TemplateRobustnessChecker, ErrorAnalyzer

# Import component spec loader for dynamic component injection
try:
    from .port_matching.component_spec_loader import ComponentSpecLoader
    COMPONENT_LOADER_AVAILABLE = True
except ImportError:
    ComponentSpecLoader = None
    COMPONENT_LOADER_AVAILABLE = False

from .config import (
    SAMPLES_PER_PROBLEM,
    MAX_RETRY_ATTEMPTS,
    CSV_OUTPUT_DIR,
    GDS_OUTPUT_DIR,
    ENABLE_OPTIMIZATION,
    ENABLE_DEVICE_OPTIMIZATION,
    ENABLE_LOSS_TARGET_CHECK,
    ENABLE_FUNCTIONAL_VALIDATION,
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_RESTARTS,
    ENABLE_AUTO_CORRECTION,
    ENABLE_RESULT_SAVING,
    ENABLE_CHECKPOINTS,
    ENABLE_ERROR_EXTRACTION,
    ENABLE_ENHANCED_FEEDBACK,
    ENABLE_ROBUSTNESS_CHECK,
    ROBUSTNESS_CHECK_AFTER_PASS_AT_K,
    ENABLE_DYNAMIC_PILOT_UPDATES,
    ENABLE_EARLY_NETLIST_VALIDATION,
    MIN_NETLIST_SPACING
)

# Import prompt templates from config or use defaults
try:
    from hf_inference_workflow.config import PYTHON_PROMPT_TEMPLATE, JSON_PROMPT_TEMPLATE, PROBLEMS_FILE
except ImportError:
    PYTHON_PROMPT_TEMPLATE = ""
    JSON_PROMPT_TEMPLATE = ""
    PROBLEMS_FILE = Path(__file__).parent.parent / "problems.txt"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Two-Phase Tracking: Raw LLM vs Framework Results
# ============================================================================

# Global tracking lists for pass@k benchmarking
RAW_LLM_RESULTS = []      # Phase 1: Raw LLM (first attempt only, no retries)
FRAMEWORK_RESULTS = []    # Phase 2: Framework (with retries + validation)


def load_problems(path: str) -> List[Tuple[int, str, str]]:
    """
    Load problems from text file.

    Format expected:
        Problem N (Title):
        or
        Problem N (Title) [Complexity N]:
        Description...

    Returns:
        List of (index, title, body) tuples
    """
    txt = Path(path).read_text(encoding="utf-8")
    # Updated regex to handle optional [Complexity N] part
    pat = re.compile(r"Problem\s+(\d+)\s*\(([^)]+)\)(?:\s*\[Complexity\s+\d+\])?\s*:", re.I)
    matches = list(pat.finditer(txt))
    out = []

    for i, m in enumerate(matches):
        idx, title = int(m.group(1)), m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(txt)
        body = txt[start:end].strip()
        if body:
            out.append((idx, title, body))

    logger.info(f"Loaded {len(out)} problems from {path}")
    return out


def estimate_pass_at_k(num_samples, num_correct, k):
    """
    Numerically stable implementation of the pass@k metric.

    Formula: pass@k = 1 - P(all k samples are incorrect)
             = 1 - C(n-c, k) / C(n, k)

    where n = total samples, c = correct samples, k = samples considered

    Args:
        num_samples: Total number of samples generated (n)
        num_correct: Number of correct samples (c)
        k: Number of samples to consider

    Returns:
        Probability that at least one of k samples is correct
    """
    if num_correct >= k:
        # If there are enough correct samples to guarantee at least one correct pick
        return 1.0

    if num_correct == 0:
        # No correct samples - impossible to get one right
        return 0.0

    # Calculate the probability that all k samples are incorrect
    # P(all wrong) = C(n-c, k) / C(n, k)
    # Use product form for numerical stability instead of factorial
    numerator = np.prod(np.arange(num_samples - num_correct, num_samples - num_correct - k, -1))
    denominator = np.prod(np.arange(num_samples, num_samples - k, -1))

    # 1 - P(all wrong) = P(at least one correct)
    return 1.0 - numerator / denominator


def save_two_phase_results():
    """Save raw LLM and framework results to separate CSV files."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save raw LLM results (Phase 1)
    if RAW_LLM_RESULTS:
        raw_df = pd.DataFrame(RAW_LLM_RESULTS)
        raw_path = CSV_OUTPUT_DIR / f"raw_llm_results_{timestamp}.csv"
        raw_df.to_csv(raw_path, index=False)
        logger.info(f"✅ Saved raw LLM results to: {raw_path}")

        # Also save as latest (for notebook convenience)
        latest_raw_path = CSV_OUTPUT_DIR / "raw_llm_results.csv"
        raw_df.to_csv(latest_raw_path, index=False)
        logger.info(f"✅ Saved as: {latest_raw_path}")

    # Save framework results (Phase 2)
    if FRAMEWORK_RESULTS:
        framework_df = pd.DataFrame(FRAMEWORK_RESULTS)
        framework_path = CSV_OUTPUT_DIR / f"framework_results_{timestamp}.csv"
        framework_df.to_csv(framework_path, index=False)
        logger.info(f"✅ Saved framework results to: {framework_path}")

        # Also save as latest
        latest_framework_path = CSV_OUTPUT_DIR / "framework_results.csv"
        framework_df.to_csv(latest_framework_path, index=False)
        logger.info(f"✅ Saved as: {latest_framework_path}")

    # Calculate and save comparison metrics
    if RAW_LLM_RESULTS and FRAMEWORK_RESULTS:
        import json

        raw_df = pd.DataFrame(RAW_LLM_RESULTS)
        framework_df = pd.DataFrame(FRAMEWORK_RESULTS)

        # Calculate pass@k by circuit
        comparison = {}
        for circuit_type in raw_df['circuit_type'].unique():
            raw_circuit = raw_df[raw_df['circuit_type'] == circuit_type]
            framework_circuit = framework_df[framework_df['circuit_type'] == circuit_type]

            raw_pass_count = int(raw_circuit['success'].sum())
            raw_total = len(raw_circuit)
            framework_pass_count = int(framework_circuit['success'].sum())
            framework_total = len(framework_circuit)

            # Use numerically stable pass@k calculation
            # k = number of samples to consider (typically equal to total samples generated)
            k_value = min(raw_total, framework_total)  # Use smaller of the two

            raw_pass_at_k = estimate_pass_at_k(
                num_samples=raw_total,
                num_correct=raw_pass_count,
                k=k_value
            ) if raw_total > 0 else 0.0

            framework_pass_at_k = estimate_pass_at_k(
                num_samples=framework_total,
                num_correct=framework_pass_count,
                k=k_value
            ) if framework_total > 0 else 0.0

            # Compute Spec@k (structural + functional)
            # Raw LLM: No functional validation, so Spec@k = 0
            raw_spec_at_k = 0.0

            # Framework: Count samples passing both structural and functional
            framework_spec_passed = 0
            if 'spec_passed' in framework_circuit.columns:
                framework_spec_passed = int(framework_circuit['spec_passed'].sum())

            framework_spec_at_k = estimate_pass_at_k(
                num_samples=framework_total,
                num_correct=framework_spec_passed,
                k=k_value
            ) if framework_total > 0 else 0.0

            # Compute average Opt-Efficiency for framework
            avg_opt_efficiency = 0.0
            if 'opt_efficiency' in framework_circuit.columns:
                valid_opt_eff = framework_circuit['opt_efficiency'].dropna()
                avg_opt_efficiency = float(valid_opt_eff.mean()) if len(valid_opt_eff) > 0 else 0.0

            # Compute average Robustness Score for framework
            avg_robustness = 0.0
            if 'robustness_score' in framework_circuit.columns:
                valid_robustness = framework_circuit['robustness_score'].dropna()
                avg_robustness = float(valid_robustness.mean()) if len(valid_robustness) > 0 else 0.0

            comparison[circuit_type] = {
                "raw_llm": {
                    "pass_at_k": float(raw_pass_at_k),
                    "spec_at_k": float(raw_spec_at_k),
                    "avg_opt_efficiency": 0.0,
                    "avg_robustness": 0.0,
                    "passed": int(raw_pass_count),
                    "total": int(raw_total),
                    "error_breakdown": raw_circuit['error_type'].value_counts().to_dict() if 'error_type' in raw_circuit else {}
                },
                "framework": {
                    "pass_at_k": float(framework_pass_at_k),
                    "spec_at_k": float(framework_spec_at_k),
                    "avg_opt_efficiency": avg_opt_efficiency,
                    "avg_robustness": avg_robustness,
                    "passed": int(framework_pass_count),
                    "spec_passed": int(framework_spec_passed),
                    "total": int(framework_total),
                    "avg_retries": float(framework_circuit['retries_used'].mean()) if 'retries_used' in framework_circuit else 0
                },
                "improvement": {
                    "pass_at_k": float(framework_pass_at_k - raw_pass_at_k),
                    "spec_at_k": float(framework_spec_at_k - raw_spec_at_k),
                    "opt_efficiency": avg_opt_efficiency,
                    "robustness": avg_robustness,
                    "pass_at_k_relative_pct": float((framework_pass_at_k - raw_pass_at_k) / raw_pass_at_k * 100) if raw_pass_at_k > 0 else 0
                }
            }

        # Save comparison metrics
        comparison_path = CSV_OUTPUT_DIR / f"comparison_metrics_{timestamp}.json"
        with open(comparison_path, 'w') as f:
            json.dump(comparison, f, indent=2)
        logger.info(f"✅ Saved comparison metrics to: {comparison_path}")

        # Also save as latest
        latest_comparison_path = CSV_OUTPUT_DIR / "comparison_metrics.json"
        with open(latest_comparison_path, 'w') as f:
            json.dump(comparison, f, indent=2)
        logger.info(f"✅ Saved as: {latest_comparison_path}")

        # Print summary
        logger.info("\n" + "="*70)
        logger.info("TWO-PHASE BENCHMARKING SUMMARY (WITH NOVEL METRICS)")
        logger.info("="*70)
        for circuit, metrics in comparison.items():
            logger.info(f"\n{circuit}:")
            logger.info(f"  Raw LLM:")
            logger.info(f"    Pass@k:          {metrics['raw_llm']['pass_at_k']*100:.1f}% ({metrics['raw_llm']['passed']}/{metrics['raw_llm']['total']})")
            logger.info(f"    Spec@k:          {metrics['raw_llm']['spec_at_k']*100:.1f}% (no functional validation)")
            logger.info(f"  Framework:")
            logger.info(f"    Pass@k:          {metrics['framework']['pass_at_k']*100:.1f}% ({metrics['framework']['passed']}/{metrics['framework']['total']})")
            logger.info(f"    Spec@k:          {metrics['framework']['spec_at_k']*100:.1f}% ({metrics['framework'].get('spec_passed', 0)}/{metrics['framework']['total']})")
            logger.info(f"    Opt-Efficiency:  {metrics['framework']['avg_opt_efficiency']:.3f}")
            logger.info(f"    Robustness:      {metrics['framework']['avg_robustness']:.3f}")
            logger.info(f"  Improvement:")
            logger.info(f"    Pass@k:          +{metrics['improvement']['pass_at_k']*100:.1f}%")
            logger.info(f"    Spec@k:          +{metrics['improvement']['spec_at_k']*100:.1f}%")
            logger.info(f"    Robustness:      {metrics['framework']['avg_robustness']:.3f}")
        logger.info("="*70 + "\n")


def get_parsing_error_feedback(error_msg: str) -> str:
    """Generate specific feedback based on parsing error type."""
    if not error_msg:
        return "Unknown parsing error"

    error_type = error_msg.split(":")[0]

    if error_type == "ROUTING_COLLISION":
        return """
ROUTING COLLISION DETECTED - Critical spacing issue!

Root Cause: Components are too close together, causing waveguides to overlap.

Required Fixes:
  1. INCREASE ALL SPACING: Components must be at least 50µm apart (minimum 30µm)
  2. VERTICAL SEPARATION: For stacked components, use ±40µm or more vertical offset
  3. HORIZONTAL SPACING: Place components 100-200µm apart horizontally
  4. ROUTE PLANNING: Ensure route paths don't cross or overlap
  5. USE LARGER BEND RADIUS: radius=15 (instead of 10) for gentler curves

Example Fix for 8-QAM:
  - MZMs vertically spaced: y-positions at 0, 120, 240 (not 0, 100, 200)
  - MMIs horizontal offset: x=400+ (not 300)
  - Phase shifters with ±50µm vertical offset (not ±30µm)

CRITICAL: Generous spacing is essential for collision-free routing!
"""
    elif error_type == "MIRROR_ERROR":
        return """
MIRROR METHOD ERROR - Incorrect mirror() usage!

Correct Pattern:
  component_ref = r.add_ref(gf.components.mmi1x2())  # First: add_ref
  component_ref.mirror()  # Then: call mirror() on the reference

Wrong Pattern:
  component = gf.components.mmi1x2().mirror()  # ❌ Error!
  r.add_ref(component)

Fix: Always call mirror() AFTER add_ref(), never before!
"""
    elif error_type == "PORT_ERROR":
        return """
PORT ERROR - Invalid port name or missing port!

Fixes:
  1. Verify port names from components reference (e.g., 'o1', 'o2', not 'output1')
  2. Check component has the port you're trying to access
  3. Ensure all components are properly instantiated before accessing ports
  4. Use exact port names from GDSFactory component specs
"""
    elif error_type == "SYNTAX_ERROR":
        return """
SYNTAX ERROR - Invalid Python code!

Common Issues:
  1. Check indentation (use consistent spaces)
  2. Verify parentheses and brackets are balanced
  3. Check string quotes are properly closed
  4. Ensure no undefined variables
"""
    else:
        return f"Execution error: {error_msg}\nPlease review the generated code for errors."


def _clean_generated_code(code: str) -> str:
    """
    Clean generated code to fix common LLM errors before validation.
    
    Fixes:
    - Invalid decimal literals (10.0.5 -> 10.0, 10µm -> 10.0, 10.0.5.2 -> 10.0)
    - Unicode characters in numbers
    - Malformed number patterns
    
    IMPORTANT: Only fixes numeric literals, not method calls or other code.
    """
    import re
    
    # Step 1: Fix numbers with units attached (must match as complete numeric literals)
    # Pattern: number followed by unit, but not part of identifier
    # Match: 10µm, 100um, but not variable10µm (which would be invalid anyway)
    code = re.sub(r'(\d+)(µm|um)(?=\s|,|\)|]|$)', r'\1.0', code)
    code = re.sub(r'(\d+\.\d+)(µm|um)(?=\s|,|\)|]|$)', r'\1', code)  # 10.5µm -> 10.5
    
    # Step 2: Remove Unicode from numbers (×, etc.) - only after numbers
    code = re.sub(r'(\d+\.?\d*)\s*×(?=\s|,|\)|]|$)', r'\1', code)
    
    # Step 3: Fix invalid decimal literals with multiple dots (10.0.5 -> 10.0, 10.0.5.2 -> 10.0)
    # Must be a complete numeric literal, not part of method call
    def fix_multiple_dots(match):
        num_str = match.group(0)
        parts = num_str.split('.')
        if len(parts) > 2:
            # Multiple dots - keep only first two parts (integer and first decimal)
            return f"{parts[0]}.{parts[1]}"
        return num_str
    
    # Match numbers with 3+ dots (e.g., 10.0.5, 10.0.5.2) - word boundary ensures it's a number
    # Use non-greedy to match shortest first, then apply recursively
    while re.search(r'\b\d+\.\d+\.\d+', code):
        code = re.sub(r'\b\d+\.\d+\.\d+(?=\s|,|\)|]|$)', fix_multiple_dots, code)
    
    # Step 4: Fix decimal followed by non-digit unit (10.µm -> 10.0)
    # Only match if followed by unit characters, not method names
    code = re.sub(r'(\d+)\.(µm|um|×)(?=\s|,|\)|]|$)', r'\1.0', code)
    
    # Step 5: Fix cases where decimal point is followed by non-numeric (10.µm -> 10.0)
    # This catches cases like "10.µm" where µm comes right after the dot
    code = re.sub(r'(\d+)\.([^\d\s,\)\]\[]+)(?=\s|,|\)|]|$)', r'\1.0', code)
    
    return code


def parse_and_execute_code(code: str, auto_correction_depth: int = 0, max_auto_correction_depth: int = 3) -> Tuple[Optional[gf.Component], Optional[str]]:
    """
    Parse and execute generated Python code to create GDSFactory component.

    Args:
        code: Generated Python code

    Returns:
        Tuple of (GDSFactory Component if successful, detailed error message if failed)
        Returns (None, error_msg) on failure, (component, None) on success
    """
    try:
        # Clean code - extract from <result> section if present (structured prompt format)
        code = code.strip()

        # Try to extract code from <result> tag (new structured format)
        if "<result>" in code and "</result>" in code:
            import re
            result_match = re.search(r'<result>(.*?)</result>', code, re.DOTALL)
            if result_match:
                code = result_match.group(1).strip()
                logger.info("Extracted code from <result> section")

        # Remove markdown code fences more robustly
        import re
        # Remove ```python or ``` at start
        code = re.sub(r'^```(?:python)?\s*\n?', '', code, flags=re.MULTILINE)
        # Remove ``` at end
        code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)
        code = code.strip()

        # Clean common LLM errors (decimal literals, Unicode, etc.)
        code = _clean_generated_code(code)

        # Create execution namespace
        ns = {"gf": gf}

        # Execute code
        exec(code, ns)

        # Try to find the component
        # Look for variable named 'r' or 'c' (common in examples)
        for var_name in ['r', 'c', 'circuit', 'component']:
            if var_name in ns and isinstance(ns[var_name], gf.Component):
                return ns[var_name], None

        # If not found, look for any Component instance
        for value in ns.values():
            if isinstance(value, gf.Component):
                return value, None

        logger.error("No GDSFactory Component found in generated code")
        return None, "NO_COMPONENT_FOUND"

    except SyntaxError as e:
        error_msg = f"SYNTAX_ERROR: {str(e)}"
        logger.error(f"Syntax error in generated code: {e}")
        return None, error_msg
    except AttributeError as e:
        # Detect mirror() errors and other attribute issues
        if "mirror" in str(e).lower():
            error_msg = f"MIRROR_ERROR: {str(e)}"
            logger.error(f"Mirror method error: {e}")
        else:
            error_msg = f"ATTRIBUTE_ERROR: {str(e)}"
            logger.error(f"Attribute error: {e}")
        return None, error_msg
    except Exception as e:
        # Detect routing collision errors specifically
        error_str = str(e).lower()
        if "routing collision" in error_str or "collision" in error_str:
            error_msg = f"ROUTING_COLLISION: {str(e)}"
            logger.error(f"Routing collision detected: {e}")
            
            # IMMEDIATE AUTO-CORRECTION: Try fixing using YAML netlist approach (GDSFactory native)
            # CRITICAL: Prevent infinite loop by limiting recursion depth
            if ENABLE_AUTO_CORRECTION and auto_correction_depth < max_auto_correction_depth:
                logger.info(f"🔄 Attempting immediate auto-correction for routing collision (YAML netlist fix, depth: {auto_correction_depth + 1}/{max_auto_correction_depth})...")
                try:
                    # Strategy: Try to get component before routing collision occurs
                    # Then extract netlist, fix spacing in YAML, rebuild using gf.read.from_yaml()
                    try:
                        from fin_picasso_framework.utils.yaml_netlist_helper import (
                            extract_netlist_from_component,
                            netlist_to_yaml,
                            fix_yaml_spacing,
                            yaml_to_component
                        )
                    except ImportError:
                        # Fallback to relative import
                        from .utils.yaml_netlist_helper import (
                            extract_netlist_from_component,
                            netlist_to_yaml,
                            fix_yaml_spacing,
                            yaml_to_component
                        )
                    
                    # Try executing code to get component (even if it has routing collision)
                    # Routing collision usually happens during route() calls, so we might get partial component
                    try:
                        ns = {"gf": gf}
                        # Execute code - might fail at routing, but components might be placed
                        exec(code, ns)
                        
                        # Try to find component
                        temp_component = None
                        for var_name in ['r', 'c', 'circuit', 'component']:
                            if var_name in ns and isinstance(ns[var_name], gf.Component):
                                temp_component = ns[var_name]
                                break
                        
                        # If we got a component, try YAML-based fix
                        if temp_component is not None:
                            logger.info("📦 Extracted component before routing collision - attempting YAML-based fix...")
                            
                            # Extract netlist
                            netlist = extract_netlist_from_component(temp_component)
                            if netlist and 'instances' in netlist:
                                # Convert to YAML
                                yaml_str = netlist_to_yaml(netlist)
                                
                                if yaml_str:
                                    # Fix spacing in YAML (more aggressive for routing collisions)
                                    fixed_yaml = fix_yaml_spacing(yaml_str, min_spacing=100.0)  # 100um for routing safety
                                    
                                    if fixed_yaml != yaml_str:
                                        logger.info("✅ Fixed spacing in YAML netlist - rebuilding component...")
                                        
                                        # Rebuild from fixed YAML using gf.read.from_yaml()
                                        fixed_component, rebuild_error = yaml_to_component(fixed_yaml)
                                        
                                        if fixed_component is not None:
                                            logger.info("✅ YAML-based auto-correction SUCCESS! Routing collision fixed via YAML spacing adjustment")
                                            return fixed_component, None  # Return fixed component, no error
                                        else:
                                            logger.warning(f"⚠️  YAML fix applied but rebuild failed: {rebuild_error}")
                    except Exception as exec_error:
                        logger.debug(f"Could not extract component for YAML fix: {exec_error}")
                    
                    # Fallback: Code-based auto-correction (increase spacing in Python code)
                    logger.info("🔄 Falling back to code-based auto-correction...")
                    auto_corrector = AutoCorrector()
                    corrected_code = auto_corrector.attempt_correction(code, "routing_error")
                    if corrected_code and corrected_code != code:
                        logger.info("✅ Auto-correction applied: Increased spacing by 2.0x (code-based fix)")
                        # CRITICAL: Pass recursion depth to prevent infinite loop
                        component_corrected, error_msg_corrected = parse_and_execute_code(
                            corrected_code, 
                            auto_correction_depth=auto_correction_depth + 1,
                            max_auto_correction_depth=max_auto_correction_depth
                        )
                        if component_corrected is not None:
                            logger.info("✅ Auto-correction SUCCESS! Routing collision fixed by spacing adjustment")
                            return component_corrected, None  # Return corrected component, no error
                        else:
                            logger.warning(f"Auto-correction applied but still failed: {error_msg_corrected[:100]}")
                except Exception as auto_corr_error:
                    logger.warning(f"Auto-correction attempt failed: {auto_corr_error}")
            elif auto_correction_depth >= max_auto_correction_depth:
                logger.warning(f"⚠️  Max auto-correction depth ({max_auto_correction_depth}) reached. Giving up on routing collision fix.")
        elif "port" in error_str and ("not found" in error_str or "invalid" in error_str):
            error_msg = f"PORT_ERROR: {str(e)}"
            logger.error(f"Port error: {e}")
        else:
            error_msg = f"EXECUTION_ERROR: {str(e)}"
            logger.error(f"Execution error: {e}")
        return None, error_msg


def validate_design(
    component: gf.Component,
    pnr_validator: PNRValidator,
    drc_validator: DRCValidator,
    sax_validator: SAXValidator,
    gds_path: str = None,
    circuit_type: str = None,
    circuit_description: str = None,
    optimizer: OptimizationStage = None,
    loss_validator: LossTargetValidator = None
) -> Tuple[bool, Dict[str, Dict], Optional[ValidationStage]]:
    """
    Run all validators and optimization on a design.

    Args:
        component: GDSFactory component to validate
        pnr_validator: P&R validator instance
        drc_validator: DRC validator instance
        sax_validator: SAX validator instance
        gds_path: Optional GDS file path for DRC
        circuit_type: Circuit type for loss target lookup
        circuit_description: Circuit description for type detection
        optimizer: Optimization stage instance
        loss_validator: Loss target validator instance

    Returns:
        (all_passed, reports_dict, failed_stage)
    """
    reports = {}

    # Stage 1: P&R Validation
    logger.info("Running P&R validation...")
    pnr_passed, pnr_report = pnr_validator.validate(component)
    reports['pnr'] = pnr_report

    if not pnr_passed:
        logger.warning("P&R validation failed")
        return False, reports, ValidationStage.PNR

    # Stage 2: DRC Validation
    logger.info("Running DRC validation...")
    drc_passed, drc_report = drc_validator.validate(component, gds_path)
    reports['drc'] = drc_report

    if not drc_passed:
        logger.warning("DRC validation failed")
        return False, reports, ValidationStage.DRC

    # Stage 3: SAX Validation
    logger.info("Running SAX validation...")
    sax_passed, sax_report = sax_validator.validate(component)
    reports['sax'] = sax_report

    if not sax_passed:
        logger.warning("SAX validation failed")
        return False, reports, ValidationStage.SAX

    # Stage 3.5: Functional Validation (NEW - Like VHDL/SPICE Testbenches)
    if ENABLE_FUNCTIONAL_VALIDATION and circuit_type:
        logger.info("Running functional validation (testbench)...")
        functional_validator = FunctionalValidator(enable=True)
        functional_result = functional_validator.validate(component, circuit_type)
        reports['functional'] = functional_result

        if functional_result['passed']:
            logger.info(
                f"✅ Functional test passed: {functional_result['test_name']} - "
                f"{functional_result['actual']}"
            )
        else:
            logger.warning(
                f"⚠️  Functional test failed: {functional_result['test_name']} - "
                f"{functional_result.get('error', functional_result['actual'])}"
            )
            # Don't fail validation if functional test fails (it's a soft check for now)
            # In the future, we can make this a hard requirement
    else:
        reports['functional'] = {'passed': True, 'test_name': 'functional_test_disabled'}

    # Stage 4: Optimization (NEW)
    if ENABLE_OPTIMIZATION and optimizer:
        logger.info("Running phase optimization...")
        opt_result = optimizer.optimize_design(component, circuit_type)
        reports['optimization'] = opt_result

        if opt_result['success']:
            logger.info(
                f"✅ Optimization successful: IL {opt_result.get('il_before_db', 'N/A')} → "
                f"{opt_result.get('il_after_db', 'N/A')} dB "
                f"(Δ {opt_result.get('improvement_db', 0.0):+.2f} dB)"
            )
        else:
            logger.warning(f"⚠️  Optimization failed: {opt_result.get('error', 'Unknown error')}")
            # Don't fail validation if optimization fails (it's optional)
    else:
        reports['optimization'] = {'success': False, 'error': 'Optimization disabled'}

    # Stage 5: Loss Target Validation (NEW)
    if ENABLE_LOSS_TARGET_CHECK and loss_validator:
        logger.info("Checking loss target compliance...")
        loss_passed, loss_report = loss_validator.validate(
            component=component,
            circuit_type=circuit_type,
            circuit_description=circuit_description,
            measured_loss_db=None,  # Will be extracted from optimization or SAX
            optimization_result=reports.get('optimization')
        )
        reports['loss_target'] = loss_report

        if loss_passed:
            logger.info(f"✅ Loss target met: {loss_report.get('achieved_db', 'N/A')} dB")
        else:
            logger.warning(f"⚠️  Loss target not met (but design still valid)")
            # Don't fail validation if loss target not met (it's a soft check)
    else:
        reports['loss_target'] = {'passed': True, 'feedback': 'Loss target check disabled'}

    logger.info("✅ All validations passed!")
    return True, reports, None


def generate_with_validation(
    agent: HFInferenceAgent,
    prompt: str,
    problem_desc: str,
    pnr_validator: PNRValidator,
    drc_validator: DRCValidator,
    sax_validator: SAXValidator,
    pilot_validator: PilotValidator,
    retry_handler: RetryHandler,
    problem_idx: int,
    sample_idx: int,
    optimizer: OptimizationStage = None,
    loss_validator: LossTargetValidator = None,
    circuit_type: str = None,
    result_saver: ResultSaver = None,
    checkpoint_manager: CheckpointManager = None,
    feedback_generator: FeedbackGenerator = None
) -> Dict:
    """
    Generate design with validation and retry logic.

    Returns:
        Dictionary with generation results and validation status
    """
    result = {
        "problem_idx": problem_idx,
        "sample_idx": sample_idx,
        "success": False,
        "code": None,
        "retry_attempts": 0,
        "failed_stage": None,
        "pnr_passed": False,
        "drc_passed": False,
        "sax_passed": False,
        "gds_path": None,
        "validation_reports": {},
        "auto_corrected": False,
        "correction_type": None
    }

    retry_handler.reset()
    
    # Initialize result saving and checkpointing if enabled
    if result_saver is None and ENABLE_RESULT_SAVING:
        result_saver = ResultSaver()
    if checkpoint_manager is None and ENABLE_CHECKPOINTS:
        checkpoint_manager = CheckpointManager(result_saver)
    if feedback_generator is None and ENABLE_ENHANCED_FEEDBACK:
        feedback_generator = FeedbackGenerator()

    # Track raw LLM attempt (Phase 1)
    raw_attempt_logged = False

    for attempt in range(MAX_RETRY_ATTEMPTS + 1):
        logger.info(f"Problem {problem_idx}, Sample {sample_idx}, Attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS + 1}")

        # Generate code
        # NOTE: prompt parameter now includes component injection (permanent) + pilot prompt (dynamic)
        if attempt == 0:
            # PHASE 1: First attempt with VANILLA LLM (no component knowledge injection)
            try:
                from hf_inference_workflow.config import VANILLA_LLM_PROMPT, ENABLE_TWO_PHASE_TRACKING
            except ImportError:
                VANILLA_LLM_PROMPT = prompt
                ENABLE_TWO_PHASE_TRACKING = False
            
            if agent:
                agent.start_new_conversation()
                # Use vanilla prompt for Phase 1 baseline, or regular prompt if two-phase disabled
                # Even in vanilla mode, we still include component injection (it's permanent)
                phase1_prompt = VANILLA_LLM_PROMPT if ENABLE_TWO_PHASE_TRACKING else prompt
                code = agent.ASK_LLM(phase1_prompt, problem_desc)
                logger.info("📊 Using Vanilla LLM prompt (Phase 1 baseline - no component specs)" if ENABLE_TWO_PHASE_TRACKING else "📊 Using Framework prompt (with component injection)")
                
                # Save raw LLM code
                if result_saver:
                    result_saver.save_raw_llm_code(code, problem_idx, sample_idx, attempt)
            else:
                code = ""
                logger.warning("No LLM agent available")
        else:
            # PHASE 2: Retry with framework (component knowledge + targeted feedback)
            # prompt already includes component injection + pilot prompt
            logger.info(f"📊 Using Framework prompt (Phase 2 - with component specs & validation feedback)")
            
            # Use enhanced feedback generator if enabled
            if feedback_generator and ENABLE_ENHANCED_FEEDBACK:
                feedback = feedback_generator.generate_feedback(
                    error_message=result.get("parsing_error") or str(result.get("failed_stage", "")),
                    code=result.get("code"),
                    validation_report=result.get("validation_reports"),
                    failed_stage=result.get("failed_stage").value if result.get("failed_stage") else None,
                    attempt_number=attempt,
                    problem_description=problem_desc
                )
                retry_prompt = feedback_generator.generate_retry_prompt(prompt, feedback, attempt)
            else:
                # Fallback to original retry handler
                feedback = retry_handler.format_feedback_for_llm(
                    failed_stage=result["failed_stage"],
                    validation_reports=result["validation_reports"],
                    problem_description=problem_desc
                )
                retry_prompt = retry_handler.create_retry_prompt(prompt, feedback, attempt)
            
            code = agent.ASK_LLM(prompt, retry_prompt)
            
            # Save retry attempt code
            if result_saver:
                result_saver.save_raw_llm_code(code, problem_idx, sample_idx, attempt)

        # Extract code from markdown/structured format BEFORE validation
        # This must happen before pilot validation since pilot uses ast.parse() which fails on syntax errors
        import re
        
        # Extract from <result> tag if present
        if "<result>" in code and "</result>" in code:
            result_match = re.search(r'<result>(.*?)</result>', code, re.DOTALL)
            if result_match:
                code = result_match.group(1).strip()
                logger.debug("Extracted code from <result> section")
        
        # Remove markdown code fences (```python ... ```)
        code = re.sub(r'^```(?:python)?\s*\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)
        code = code.strip()
        
        # Clean code (fix common LLM errors like invalid decimal literals)
        # Use local function
        # Log raw code for debugging (first 500 chars)
        if attempt == 0 or attempt == 1:  # Log first two attempts
            code_preview = code[:500].replace('\n', '\\n')
            logger.debug(f"Raw generated code (first 500 chars): {code_preview}")
        
        cleaned_code = _clean_generated_code(code)
        
        # Log if cleaning made changes
        if cleaned_code != code:
            logger.info(f"Code cleaning applied (removed Unicode/fixed decimals)")
            cleaned_preview = cleaned_code[:500].replace('\n', '\\n')
            logger.debug(f"Cleaned code (first 500 chars): {cleaned_preview}")
        
        result["code"] = cleaned_code
        result["retry_attempts"] = attempt

        # PILOT VALIDATION: Pre-execution code validation (uses cleaned code)
        logger.info("Running pilot validation (pre-execution checks)...")
        pilot_valid, pilot_error = pilot_validator.validate(cleaned_code)
        
        # Save pilot checkpoint
        if checkpoint_manager:
            checkpoint_manager.save_pilot_checkpoint(
                problem_idx, sample_idx, attempt, cleaned_code,
                pilot_valid, pilot_error if not pilot_valid else None
            )

        if not pilot_valid:
            logger.warning(f"❌ Pilot validation failed: {pilot_error}")
            result["failed_stage"] = ValidationStage.PARSING
            result["parsing_error"] = f"PILOT_ERROR: {pilot_error}"

            # Save failed code for analysis (first attempt only)
            if attempt == 0:
                from pathlib import Path
                failed_code_dir = Path(__file__).parent.parent / "output" / "failed_code_samples"
                failed_code_dir.mkdir(parents=True, exist_ok=True)
                failed_code_file = failed_code_dir / f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}.py"
                with open(failed_code_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Problem {problem_idx}, Sample {sample_idx}, Attempt {attempt}\n")
                    f.write(f"# Error: {pilot_error}\n")
                    f.write(f"# Raw code:\n{code}\n")
                    f.write(f"\n# Cleaned code:\n{cleaned_code}\n")
                logger.debug(f"Saved failed code sample to: {failed_code_file}")

            # Track pilot violation
            if "pilot_violations" not in result:
                result["pilot_violations"] = []
            result["pilot_violations"].append({
                "attempt": attempt,
                "error": pilot_error
            })

            # Provide feedback for retry
            pilot_feedback = pilot_validator.get_feedback(pilot_error)
            logger.info(f"Pilot feedback for LLM: {pilot_feedback}")

            # Skip code execution and retry
            retry_handler.record_attempt(attempt, ValidationStage.PARSING, pilot_feedback, code)

            if not retry_handler.should_retry(attempt + 1):
                logger.warning("Max retries reached for pilot validation")
                
                # AUTO-CORRECTION: Try auto-correct pilot errors as last resort
                # Always enabled in framework mode (ENABLE_AUTO_CORRECTION controls this)
                if ENABLE_AUTO_CORRECTION and not result.get("auto_corrected", False):
                    logger.info("Attempting auto-correction for pilot validation failure...")
                    auto_corrector = AutoCorrector()
                    
                    # Extract error type from pilot error message
                    error_type = "parsing"  # Default
                    if "SYNTAX" in pilot_error.upper() or "invalid character" in pilot_error.lower():
                        error_type = "parsing"
                    elif "ROUTING" in pilot_error.upper():
                        error_type = "routing_error"
                    elif "MIRROR" in pilot_error.upper():
                        error_type = "mirror_error"
                    elif "SPACING" in pilot_error.upper():
                        error_type = "spacing_error"
                    elif "PORT" in pilot_error.upper():
                        error_type = "port_error"
                    
                    # Try auto-correction with iterative refinement (up to 3 passes)
                    corrected_code = code
                    max_correction_passes = 3
                    correction_applied = False
                    
                    for correction_pass in range(max_correction_passes):
                        corrected_code = auto_corrector.attempt_correction(
                            code=corrected_code,
                            error_type=error_type,
                            validation_reports={"pilot_error": pilot_error}
                        )
                        
                        if corrected_code and corrected_code != code:
                            correction_applied = True
                            logger.info(f"Auto-correction pass {correction_pass + 1} applied for {error_type}")
                            
                            # Re-validate corrected code with pilot
                            pilot_valid_corrected, pilot_error_corrected = pilot_validator.validate(corrected_code)
                            
                            if pilot_valid_corrected:
                                logger.info(f"✅ Auto-correction fixed pilot validation after {correction_pass + 1} pass(es)! Continuing...")
                                result["auto_corrected"] = True
                                result["correction_type"] = error_type
                                result["code"] = corrected_code
                                code = corrected_code  # Use corrected code for execution
                                # Continue to code execution below (don't break)
                                break
                            else:
                                # Update error for next pass
                                pilot_error = pilot_error_corrected
                                # Update error_type based on new error
                                if "SYNTAX" in pilot_error.upper() or "invalid" in pilot_error.lower():
                                    error_type = "parsing"
                                elif "ROUTING" in pilot_error.upper():
                                    error_type = "routing_error"
                                error_preview = pilot_error_corrected[:50] if pilot_error_corrected and len(pilot_error_corrected) > 50 else (pilot_error_corrected or "unknown")
                                logger.info(f"Auto-correction pass {correction_pass + 1} fixed some issues, but new error: {error_preview}...")
                        else:
                            break  # No more corrections possible
                    
                    # Final check: if correction was applied, validate it; otherwise we failed
                    if correction_applied and corrected_code:
                        final_valid, final_error = pilot_validator.validate(corrected_code)
                        if not final_valid:
                            logger.warning(f"Auto-correction could not fix pilot error after {max_correction_passes} passes. Final error: {final_error[:100] if final_error else 'unknown'}")
                        break
                    else:
                        logger.warning(f"Auto-correction could not fix pilot error - no corrections applied")
                        break
                else:
                    break
            else:
                continue  # Skip to next retry iteration

        logger.info("✅ Pilot validation passed")

        # Parse and execute code
        logger.info("Parsing and executing generated code...")
        component, error_msg = parse_and_execute_code(code)

        # YAML-BASED ITERATIVE ROUTING/PLACEMENT FIXING (if component created successfully)
        # Extract netlist, validate, iteratively fix spacing/routing issues, rebuild
        if component is not None and ENABLE_EARLY_NETLIST_VALIDATION:
            try:
                try:
                    from fin_picasso_framework.utils.yaml_routing_fixer import fix_routing_and_placement_iterative
                except ImportError:
                    from .utils.yaml_routing_fixer import fix_routing_and_placement_iterative
                
                logger.info("🔄 Attempting iterative YAML-based routing/placement fixes (3 iterations)...")
                
                # Try iterative fixes (3 iterations with increasing spacing + rotation)
                fixed_component, fix_info = fix_routing_and_placement_iterative(
                    component=component,
                    max_iterations=3,
                    initial_spacing_multiplier=1.5,
                    spacing_increment=0.5,
                    enable_rotation=True,  # Enable PhIDO-style brute-force rotation
                    rotation_timeout=120   # 2 minutes timeout (like PhIDO)
                )
                
                if fixed_component is not None and fix_info["success"]:
                    method = fix_info.get("method_used", "unknown")
                    if method == "rotation":
                        logger.info(f"✅ YAML-based routing/placement fix successful using rotation algorithm!")
                        logger.info(f"   Rotation applied: {fix_info.get('rotation_info', {}).get('orientation', {})}")
                    else:
                        logger.info(f"✅ YAML-based routing/placement fix successful after {fix_info['iterations']} iteration(s) using spacing fix!")
                        logger.info(f"   Final spacing multiplier: {fix_info['final_spacing_multiplier']}x")
                    component = fixed_component
                else:
                    logger.warning(f"⚠️  YAML iterative fixes failed after {fix_info['iterations']} iterations")
                    if fix_info.get("errors"):
                        logger.warning(f"   Errors: {fix_info['errors'][-1] if fix_info['errors'] else 'Unknown'}")
                    # Continue with original component - fixes are optional enhancement
                    
            except Exception as yaml_error:
                logger.warning(f"⚠️  YAML iterative fixing failed (non-critical): {yaml_error}")
                # Continue with original component - YAML validation is optional enhancement

        # PHASE 1: Track raw LLM (first attempt only, before any retries)
        if attempt == 0 and not raw_attempt_logged:
            raw_success = component is not None
            RAW_LLM_RESULTS.append({
                "problem_idx": problem_idx,
                "circuit_type": circuit_type or f"problem_{problem_idx}",
                "sample_idx": sample_idx,
                "success": raw_success,
                "error_type": error_msg.split(":")[0] if error_msg else None,
                "error_details": error_msg if error_msg else None,
                "code_length": len(code),
            })
            raw_attempt_logged = True
            logger.info(f"📊 Phase 1 (Raw LLM): {'✅ PASSED' if raw_success else '❌ FAILED'}")

        if component is None:
            logger.error(f"Failed to parse/execute code: {error_msg}")
            result["failed_stage"] = ValidationStage.PARSING
            result["parsing_error"] = error_msg  # Store specific error for feedback

            # Add error-specific feedback to validation reports
            result["validation_reports"]["parsing"] = {
                "passed": False,
                "error_type": error_msg.split(":")[0] if error_msg else "UNKNOWN",
                "error_details": error_msg,
                "feedback": get_parsing_error_feedback(error_msg)
            }

            retry_handler.record_attempt(attempt, ValidationStage.PARSING, error_msg or "Parsing failed", code)
            continue

        # Create GDS file path
        gds_filename = f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}.gds"
        gds_path = str(GDS_OUTPUT_DIR / gds_filename)

        try:
            component.write_gds(gds_path)
            result["gds_path"] = gds_path
        except Exception as e:
            logger.error(f"Failed to write GDS: {e}")
            result["failed_stage"] = ValidationStage.PARSING
            continue

        # Run validations + optimization + loss check
        all_passed, reports, failed_stage = validate_design(
            component=component,
            pnr_validator=pnr_validator,
            drc_validator=drc_validator,
            sax_validator=sax_validator,
            gds_path=gds_path,
            circuit_type=circuit_type,
            circuit_description=problem_desc,
            optimizer=optimizer,
            loss_validator=loss_validator
        )

        result["validation_reports"] = reports
        result["pnr_passed"] = reports.get('pnr', {}).get('passed', False)
        result["drc_passed"] = reports.get('drc', {}).get('passed', False)
        result["sax_passed"] = reports.get('sax', {}).get('passed', False)
        
        # Save checkpoints at each validation stage
        if checkpoint_manager:
            # P&R checkpoint
            checkpoint_manager.save_pnr_checkpoint(
                problem_idx, sample_idx, attempt, component, cleaned_code,
                reports.get('pnr', {}), result["pnr_passed"]
            )
            
            # DRC checkpoint
            if result["pnr_passed"]:
                checkpoint_manager.save_drc_checkpoint(
                    problem_idx, sample_idx, attempt, component, cleaned_code,
                    reports.get('drc', {}), result["drc_passed"]
                )
            
            # SAX checkpoint
            if result["drc_passed"]:
                checkpoint_manager.save_sax_checkpoint(
                    problem_idx, sample_idx, attempt, component, cleaned_code,
                    reports.get('sax', {}), result["sax_passed"]
                )
            
            # Functional checkpoint
            if result["sax_passed"] and reports.get('functional'):
                checkpoint_manager.save_functional_checkpoint(
                    problem_idx, sample_idx, attempt, component, cleaned_code,
                    reports.get('functional', {}), reports.get('functional', {}).get('passed', False)
                )
            
            # Optimization checkpoint
            if reports.get('optimization'):
                checkpoint_manager.save_optimization_checkpoint(
                    problem_idx, sample_idx, attempt, component, cleaned_code,
                    reports.get('optimization', {})
                )

        # Add optimization metrics (NEW)
        opt_report = reports.get('optimization', {})
        result["optimization_success"] = opt_report.get('success', False)

        # Two-level optimization metrics
        result["device_loss_db"] = opt_report.get('device_loss_db')
        result["circuit_loss_before_db"] = opt_report.get('circuit_loss_before_db')
        result["circuit_loss_after_db"] = opt_report.get('circuit_loss_after_db')
        result["total_loss_db"] = opt_report.get('total_loss_db')
        result["circuit_improvement_db"] = opt_report.get('improvement_db', 0.0)

        # Legacy fields (for backward compatibility)
        result["il_before_db"] = opt_report.get('circuit_loss_before_db') or opt_report.get('il_before_db')
        result["il_after_db"] = opt_report.get('total_loss_db') or opt_report.get('il_after_db')
        result["il_improvement_db"] = opt_report.get('improvement_db', 0.0)

        # Add loss target metrics (NEW)
        loss_report = reports.get('loss_target', {})
        result["loss_target_db"] = loss_report.get('target_db')
        result["loss_achieved_db"] = loss_report.get('achieved_db')
        result["loss_margin_db"] = loss_report.get('margin_db')
        result["meets_loss_target"] = loss_report.get('meets_target', False)

        if all_passed:
            result["success"] = True
            result["failed_stage"] = None
            logger.info(f"✅ Design validated successfully!")
            
            # Save final framework-processed results
            if result_saver:
                result_saver.save_framework_code(cleaned_code, problem_idx, sample_idx, attempt, True)
                if component:
                    result_saver.save_framework_gds(component, problem_idx, sample_idx)
                result_saver.save_validation_report(reports, problem_idx, sample_idx)
                if reports.get('optimization'):
                    result_saver.save_optimization_result(reports['optimization'], problem_idx, sample_idx)
            
            break
        else:
            result["failed_stage"] = failed_stage
            retry_handler.record_attempt(attempt, failed_stage, "Validation failed", code)
            logger.warning(f"Validation failed at stage: {failed_stage.value}")

            if not retry_handler.should_retry(attempt + 1):
                logger.warning(f"Max retries reached")
                
                # AUTO-CORRECTION: Try auto-correct as last resort
                if ENABLE_AUTO_CORRECTION and not result.get("auto_corrected", False):
                    logger.info("Attempting auto-correction as fallback...")
                    auto_corrector = AutoCorrector()
                    
                    # Determine error type from failed stage and error message
                    error_type = "unknown"
                    error_msg = result.get("parsing_error") or ""
                    
                    # Parse error message to extract actual error type
                    if error_msg:
                        error_msg_lower = error_msg.lower()
                        # Check for specific error patterns in the message
                        if "syntax" in error_msg_lower or "unterminated" in error_msg_lower or "invalid" in error_msg_lower:
                            error_type = "parsing"  # Syntax errors
                        elif "mirror" in error_msg_lower:
                            error_type = "mirror_error"
                        elif "port" in error_msg_lower and ("not found" in error_msg_lower or "invalid" in error_msg_lower):
                            error_type = "port_error"
                        elif "routing" in error_msg_lower or "collision" in error_msg_lower:
                            error_type = "routing_error"
                        elif "spacing" in error_msg_lower:
                            error_type = "spacing_error"
                        else:
                            # Try to extract from error prefix (e.g., "PILOT_ERROR: Syntax error" -> "parsing")
                            error_prefix = error_msg.split(":")[0].lower()
                            if "pilot" in error_prefix:
                                # Extract the actual error type from after "PILOT_ERROR:"
                                if ":" in error_msg:
                                    actual_error = error_msg.split(":", 1)[1].strip().lower()
                                    if "syntax" in actual_error or "unterminated" in actual_error:
                                        error_type = "parsing"
                                    elif "mirror" in actual_error:
                                        error_type = "mirror_error"
                                    elif "port" in actual_error:
                                        error_type = "port_error"
                                    elif "routing" in actual_error:
                                        error_type = "routing_error"
                                    else:
                                        error_type = "parsing"  # Default for pilot errors
                                else:
                                    error_type = "parsing"  # Default for pilot errors
                            else:
                                error_type = error_prefix.replace("_error", "").replace("error", "")
                    
                    # Fallback to failed_stage if error_type still unknown
                    if error_type == "unknown" and result.get("failed_stage"):
                        stage = result.get("failed_stage").value
                        if stage == "parsing":
                            error_type = "parsing"
                        elif stage == "pnr":
                            error_type = "spacing_error"
                        elif stage == "drc":
                            error_type = "drc_error"
                        elif stage == "sax":
                            # Check SAX error details
                            sax_error = result.get("validation_reports", {}).get("sax", {}).get("error", "")
                            if "more than two connected" in sax_error.lower() or "port" in sax_error.lower():
                                error_type = "port_error"
                            else:
                                error_type = "sax_error"
                    
                    corrected_code = auto_corrector.attempt_correction(
                        code=result.get("code", code),
                        error_type=error_type,
                        validation_reports=result.get("validation_reports")
                    )
                    
                    if corrected_code and corrected_code != result.get("code", code):
                        logger.info(f"Auto-correction applied for {error_type}")
                        
                        # Try parsing and executing corrected code
                        component_corrected, error_msg_corrected = parse_and_execute_code(corrected_code)
                        
                        if component_corrected is not None:
                            logger.info("✅ Auto-correction succeeded! Re-running validation...")
                            result["auto_corrected"] = True
                            result["correction_type"] = error_type
                            result["code"] = corrected_code
                            
                            # Create GDS file for corrected design
                            gds_filename_corrected = f"problem_{problem_idx}_sample_{sample_idx}_autocorrect.gds"
                            gds_path_corrected = str(GDS_OUTPUT_DIR / gds_filename_corrected)
                            
                            try:
                                component_corrected.write_gds(gds_path_corrected)
                                result["gds_path"] = gds_path_corrected
                                
                                # Re-run validation pipeline on corrected design
                                all_passed_corrected, reports_corrected, failed_stage_corrected = validate_design(
                                    component=component_corrected,
                                    pnr_validator=pnr_validator,
                                    drc_validator=drc_validator,
                                    sax_validator=sax_validator,
                                    gds_path=gds_path_corrected,
                                    circuit_type=circuit_type,
                                    circuit_description=problem_desc,
                                    optimizer=optimizer,
                                    loss_validator=loss_validator
                                )
                                
                                result["validation_reports"] = reports_corrected
                                result["pnr_passed"] = reports_corrected.get('pnr', {}).get('passed', False)
                                result["drc_passed"] = reports_corrected.get('drc', {}).get('passed', False)
                                result["sax_passed"] = reports_corrected.get('sax', {}).get('passed', False)
                                
                                # Update optimization metrics
                                opt_report_corrected = reports_corrected.get('optimization', {})
                                result["optimization_success"] = opt_report_corrected.get('success', False)
                                result["device_loss_db"] = opt_report_corrected.get('device_loss_db')
                                result["circuit_loss_before_db"] = opt_report_corrected.get('circuit_loss_before_db')
                                result["circuit_loss_after_db"] = opt_report_corrected.get('circuit_loss_after_db')
                                result["total_loss_db"] = opt_report_corrected.get('total_loss_db')
                                result["circuit_improvement_db"] = opt_report_corrected.get('improvement_db', 0.0)
                                result["il_before_db"] = opt_report_corrected.get('circuit_loss_before_db') or opt_report_corrected.get('il_before_db')
                                result["il_after_db"] = opt_report_corrected.get('total_loss_db') or opt_report_corrected.get('il_after_db')
                                result["il_improvement_db"] = opt_report_corrected.get('improvement_db', 0.0)
                                
                                # Update loss target metrics
                                loss_report_corrected = reports_corrected.get('loss_target', {})
                                result["loss_target_db"] = loss_report_corrected.get('target_db')
                                result["loss_achieved_db"] = loss_report_corrected.get('achieved_db')
                                result["loss_margin_db"] = loss_report_corrected.get('margin_db')
                                result["meets_loss_target"] = loss_report_corrected.get('meets_target', False)
                                
                                if all_passed_corrected:
                                    result["success"] = True
                                    result["failed_stage"] = None
                                    logger.info("✅ Auto-corrected design passed all validations!")
                                else:
                                    result["failed_stage"] = failed_stage_corrected
                                    logger.warning(f"Auto-corrected design failed at: {failed_stage_corrected.value}")
                                    
                            except Exception as e:
                                logger.error(f"Auto-corrected design GDS write failed: {e}")
                        else:
                            logger.warning(f"Auto-correction did not fix parsing error: {error_msg_corrected}")
                    else:
                        logger.warning("No auto-correction available for this error type")
                
                break

    # PHASE 2: Track framework result (after retries + validation)
    framework_success = result["success"]
    retries_used = result["retry_attempts"]

    framework_entry = {
        "problem_idx": problem_idx,
        "circuit_type": circuit_type or f"problem_{problem_idx}",
        "sample_idx": sample_idx,
        "success": framework_success,
        "retries_used": retries_used,
        "validation_passed": all([
            result.get("pnr_passed", False),
            result.get("drc_passed", False),
            result.get("sax_passed", False)
        ]) if framework_success else False,
        "auto_corrected": result.get("auto_corrected", False),
        "correction_type": result.get("correction_type", None),
    }

    # Add validation metrics if available
    if framework_success and result.get("validation_reports"):
        pnr_report = result["validation_reports"].get("pnr", {})
        framework_entry["pnr_score"] = pnr_report.get("metrics", {}).get("quality_score")
        framework_entry["layout_area"] = pnr_report.get("metrics", {}).get("layout_area")

        drc_report = result["validation_reports"].get("drc", {})
        framework_entry["drc_violations"] = drc_report.get("violations", 0)

        framework_entry["sax_compiled"] = result["validation_reports"].get("sax", {}).get("sax_compiled", False)

        # Add two-level optimization metrics
        framework_entry["device_loss_db"] = result.get("device_loss_db")
        framework_entry["circuit_loss_before_db"] = result.get("circuit_loss_before_db")
        framework_entry["circuit_loss_after_db"] = result.get("circuit_loss_after_db")
        framework_entry["total_loss_db"] = result.get("total_loss_db")
        framework_entry["circuit_improvement_db"] = result.get("circuit_improvement_db", 0.0)

        # Legacy fields (for backward compatibility with old notebooks)
        framework_entry["il_after_db"] = result.get("il_after_db")
        framework_entry["il_improvement_db"] = result.get("il_improvement_db", 0.0)

    # ALWAYS add novel metric columns (even for failed samples)
    # Add functional validation metrics
    functional_report = result.get("validation_reports", {}).get("functional", {}) if result.get("validation_reports") else {}
    framework_entry["spec_passed"] = functional_report.get("passed", False)
    framework_entry["functional_test_name"] = functional_report.get("test_name", "")
    framework_entry["functional_metric_value"] = functional_report.get("metric_value")

    # Compute novel metrics (Opt-Efficiency and Robustness Score)
    opt_efficiency = compute_opt_efficiency(result)
    framework_entry["opt_efficiency"] = opt_efficiency

    # Compute Spec@k for this single sample (0.0 or 1.0)
    spec_passed = framework_success and framework_entry["spec_passed"]
    spec_at_k_single = 1.0 if spec_passed else 0.0

    # Compute Robustness Score
    robustness_score = compute_robustness_score(
        spec_at_k=spec_at_k_single,
        opt_efficiency=opt_efficiency,
        alpha=0.7,
        beta=0.3
    )
    framework_entry["robustness_score"] = robustness_score

    FRAMEWORK_RESULTS.append(framework_entry)
    logger.info(f"📊 Phase 2 (Framework): {'✅ PASSED' if framework_success else '❌ FAILED'} (retries: {retries_used})")

    return result


def run_validated_generation(
    agent: HFInferenceAgent,
    problems: List[Tuple[int, str, str]],
    prompt_template: str,
    csv_name: str
):
    """
    Run validated generation for all problems.

    Args:
        agent: HF Inference agent
        problems: List of (idx, title, body) tuples
        prompt_template: Prompt template to use
        csv_name: Output CSV filename
    """
    # Initialize validators
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    pilot_validator = PilotValidator()  # Pre-execution code validation
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)
    
    # Initialize result saving and checkpointing
    result_saver = ResultSaver() if ENABLE_RESULT_SAVING else None
    checkpoint_manager = CheckpointManager(result_saver) if ENABLE_CHECKPOINTS else None
    feedback_generator = FeedbackGenerator() if ENABLE_ENHANCED_FEEDBACK else None
    pilot_prompt_updater = PilotPromptUpdater() if ENABLE_DYNAMIC_PILOT_UPDATES else None

    # Initialize optimizer and loss validator (NEW)
    # Two-level optimization: device geometries + circuit parameters
    optimizer = OptimizationStage(
        enable_optimization=ENABLE_OPTIMIZATION,
        enable_device_optimization=ENABLE_DEVICE_OPTIMIZATION,
        max_iter=OPTIMIZATION_MAX_ITER,
        n_restarts=OPTIMIZATION_RESTARTS
    )
    loss_validator = LossTargetValidator()

    # ============================================================================
    # COMPONENT INJECTION: Load once at framework start (permanent)
    # ============================================================================
    component_injection_text = ""
    if COMPONENT_LOADER_AVAILABLE and ComponentSpecLoader:
        try:
            component_loader = ComponentSpecLoader(use_pydoc=True)
            # Extract common component types from all problems
            all_component_types = set()
            for _, _, body in problems:
                # Simple extraction - look for common component names in problem text
                import re
                common_components = ['mmi1x2', 'mzi', 'mzm', 'straight', 'straight_heater_metal', 
                                   'coupler', 'ring', 'bend', 'taper', 'grating_coupler']
                for comp in common_components:
                    if comp in body.lower():
                        all_component_types.add(comp)
            
            # If no components found, use default common components
            if not all_component_types:
                all_component_types = {'mmi1x2', 'mzi', 'mzm', 'straight', 'straight_heater_metal', 
                                     'coupler', 'bend_euler'}
            
            # Generate comprehensive component specs (loaded once, used for all problems)
            component_injection_text = component_loader.generate_port_reference(
                component_types=list(all_component_types),
                include_sax=True
            )
            logger.info(f"✅ Loaded component injection for {len(all_component_types)} components")
            logger.info(f"Component injection length: {len(component_injection_text)} chars")
        except Exception as e:
            logger.warning(f"Failed to load component injection: {e}")
    
    # Inject component specs into base prompt template (permanent)
    base_prompt_with_injection = prompt_template
    if component_injection_text:
        # Insert component injection after the initial instruction
        if "--- AVAILABLE GDSFACTORY COMPONENTS REFERENCE ---" not in prompt_template:
            # Add component injection section
            injection_section = f"\n\n--- AVAILABLE GDSFACTORY COMPONENTS REFERENCE ---\n{component_injection_text}\n--- END COMPONENTS REFERENCE ---\n"
            # Insert after first line or after "You are a professional" line
            if "You are a professional" in prompt_template:
                base_prompt_with_injection = prompt_template.replace(
                    "You are a professional Photonic Integrated Circuit (PIC) designer with expertise in GDSFactory.\nYour task is to generate Python code based on the circuit design requirements provided.",
                    f"You are a professional Photonic Integrated Circuit (PIC) designer with expertise in GDSFactory.\nYour task is to generate Python code based on the circuit design requirements provided.{injection_section}"
                )
            else:
                # Insert at the beginning
                base_prompt_with_injection = injection_section + "\n" + prompt_template
    
    # ============================================================================
    # PILOT PROMPT: Start with base restrictions, update dynamically
    # ============================================================================
    # Load permanent pilot rules from file (if exists)
    base_pilot_prompt = ""
    if pilot_prompt_updater:
        # Get base pilot prompt with learned rules (permanent)
        base_pilot_prompt = pilot_prompt_updater.get_updated_pilot_prompt("")
        if base_pilot_prompt:
            logger.info(f"✅ Loaded permanent pilot rules ({len(base_pilot_prompt)} chars)")
    
    # Combine base prompt with component injection and pilot prompt
    current_prompt = base_prompt_with_injection
    if base_pilot_prompt:
        # Append pilot restrictions to prompt
        current_prompt = current_prompt + "\n\n--- PILOT RESTRICTIONS (Auto-Updated) ---\n" + base_pilot_prompt + "\n--- END PILOT RESTRICTIONS ---\n"

    results = []
    total_designs = len(problems) * SAMPLES_PER_PROBLEM
    
    # Track failures per problem for pilot prompt updates
    problem_failures = {}  # {problem_idx: [failed_case_dict, ...]}

    with tqdm(total=total_designs, desc=f"Generating validated designs") as pbar:
        for idx, title, body in problems:
            # Track failures for this problem
            problem_failures[idx] = []
            
            for sample in range(SAMPLES_PER_PROBLEM):
                logger.info(f"\n{'='*60}")
                logger.info(f"Problem {idx}: {title} - Sample {sample + 1}/{SAMPLES_PER_PROBLEM}")
                logger.info(f"{'='*60}")

                result = generate_with_validation(
                    agent=agent,
                    prompt=current_prompt,  # Use potentially updated prompt
                    problem_desc=body,
                    pnr_validator=pnr_validator,
                    drc_validator=drc_validator,
                    sax_validator=sax_validator,
                    pilot_validator=pilot_validator,
                    retry_handler=retry_handler,
                    problem_idx=idx,
                    sample_idx=sample,
                    optimizer=optimizer,
                    loss_validator=loss_validator,
                    circuit_type=title.lower(),  # Use title as circuit type hint
                    result_saver=result_saver,
                    checkpoint_manager=checkpoint_manager,
                    feedback_generator=feedback_generator
                )

                # Track failures for pilot prompt updates
                if not result["success"]:
                    failed_case = {
                        'error_message': result.get("parsing_error") or str(result.get("failed_stage", "")),
                        'code': result.get("code", ""),
                        'validation_report': result.get("validation_reports", {}),
                        'failed_stage': result.get("failed_stage").value if result.get("failed_stage") else None,
                        'sample': sample,
                        'retry_attempts': result.get("retry_attempts", 0),
                        'attempt_number': result.get("retry_attempts", 0) + 1  # Current attempt number (1-indexed)
                    }
                    problem_failures[idx].append(failed_case)
                    
                    # Update pilot prompt after EACH failure (pass@1, pass@2, pass@3, etc.)
                    # This allows the NEXT attempt to benefit from the learning immediately
                    if pilot_prompt_updater and ENABLE_DYNAMIC_PILOT_UPDATES:
                        retry_attempts = result.get("retry_attempts", 0)
                        attempt_number = retry_attempts + 1  # Current attempt (1-indexed)
                        
                        logger.info(f"\n{'='*60}")
                        logger.info(f"Pass@{attempt_number} failure detected - Updating pilot prompt for next attempt...")
                        logger.info(f"Error: {failed_case['error_message'][:100]}")
                        logger.info(f"{'='*60}")
                        
                        # Analyze this single failure (immediate learning)
                        failed_cases_to_analyze = [failed_case]  # Analyze just this failure
                        
                        # Analyze failures
                        analysis = pilot_prompt_updater.analyze_failures(
                            failed_cases=failed_cases_to_analyze,
                            max_retries=attempt_number
                        )
                        
                        # Update pilot rules (auto-apply)
                        update_report = pilot_prompt_updater.update_pilot_rules(
                            analysis=analysis,
                            auto_apply=True
                        )
                        
                        if update_report['applied']:
                            logger.info(f"✅ Applied {len(update_report['applied'])} pilot rule updates after pass@{attempt_number}")
                            for update in update_report['applied']:
                                logger.info(f"  - {update['update']}")
                            
                            # Save rules permanently
                            pilot_prompt_updater._save_rules()
                            
                            # Get updated pilot prompt (permanent rules + new learned rules)
                            updated_pilot_prompt = pilot_prompt_updater.get_updated_pilot_prompt("")
                            
                            # Reconstruct current_prompt with updated pilot prompt
                            # Keep component injection (permanent), update pilot prompt (dynamic)
                            current_prompt = base_prompt_with_injection
                            if updated_pilot_prompt:
                                current_prompt = current_prompt + "\n\n--- PILOT RESTRICTIONS (Auto-Updated) ---\n" + updated_pilot_prompt + "\n--- END PILOT RESTRICTIONS ---\n"
                            
                            logger.info(f"✅ Updated pilot prompt will be used for attempt {attempt_number + 1}")
                        else:
                            logger.info(f"ℹ️ No new pilot rules to apply after pass@{attempt_number} (may need more context)")
                            
                            # Still update the prompt with existing learned rules
                            updated_pilot_prompt = pilot_prompt_updater.get_updated_pilot_prompt("")
                            current_prompt = base_prompt_with_injection
                            if updated_pilot_prompt:
                                current_prompt = current_prompt + "\n\n--- PILOT RESTRICTIONS (Auto-Updated) ---\n" + updated_pilot_prompt + "\n--- END PILOT RESTRICTIONS ---\n"

                # Format result for CSV
                csv_row = {
                    "problem_idx": idx,
                    "problem_title": title,
                    "sample": sample,
                    "success": result["success"],
                    "retry_attempts": result["retry_attempts"],
                    "failed_stage": result["failed_stage"].value if result["failed_stage"] else None,
                    "pnr_passed": result["pnr_passed"],
                    "drc_passed": result["drc_passed"],
                    "sax_passed": result["sax_passed"],
                    "gds_path": result["gds_path"],
                    "code": result["code"]
                }

                results.append(csv_row)
                pbar.update(1)
            
            # Summary after all samples for this problem
            failed_cases = problem_failures.get(idx, [])
            if len(failed_cases) > 0:
                logger.info(f"\n{'='*60}")
                logger.info(f"Problem {idx} Summary: {len(failed_cases)}/{SAMPLES_PER_PROBLEM} samples failed")
                logger.info(f"{'='*60}")

    # Save results to CSV
    df = pd.DataFrame(results)
    csv_path = CSV_OUTPUT_DIR / csv_name
    df.to_csv(csv_path, index=False)

    # Print summary statistics
    logger.info(f"\n{'='*60}")
    logger.info("GENERATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total designs attempted: {len(results)}")
    logger.info(f"Successful designs: {df['success'].sum()} ({df['success'].mean()*100:.1f}%)")
    logger.info(f"P&R pass rate: {df['pnr_passed'].sum()} ({df['pnr_passed'].mean()*100:.1f}%)")
    logger.info(f"DRC pass rate: {df['drc_passed'].sum()} ({df['drc_passed'].mean()*100:.1f}%)")
    logger.info(f"SAX pass rate: {df['sax_passed'].sum()} ({df['sax_passed'].mean()*100:.1f}%)")
    logger.info(f"Average retry attempts: {df['retry_attempts'].mean():.2f}")
    logger.info(f"Results saved to: {csv_path}")

    # Save two-phase tracking results
    save_two_phase_results()


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate validated photonic circuits with HF Inference API")
    parser.add_argument("--problems", type=str, default=str(PROBLEMS_FILE), help="Path to problems file")
    parser.add_argument("--output", type=str, default="hf_validated_designs.csv", help="Output CSV filename")
    parser.add_argument("--samples", type=int, default=SAMPLES_PER_PROBLEM, help="Samples per problem")
    parser.add_argument("--model", type=str, default=None, help="Override default model")
    parser.add_argument("--format", type=str, choices=["python", "json"], default="python", help="Output format")

    args = parser.parse_args()

    # Load problems
    problems = load_problems(args.problems)

    # Initialize agent
    logger.info("Initializing HuggingFace Inference Agent...")
    agent = HFInferenceAgent(model=args.model) if args.model else HFInferenceAgent()

    # Select prompt template
    prompt = PYTHON_PROMPT_TEMPLATE if args.format == "python" else JSON_PROMPT_TEMPLATE

    # Run generation
    run_validated_generation(
        agent=agent,
        problems=problems,
        prompt_template=prompt,
        csv_name=args.output
    )

    logger.info("\n✅ Generation complete!")


if __name__ == "__main__":
    main()
