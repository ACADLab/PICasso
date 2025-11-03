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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gdsfactory as gf
from hf_inference_workflow.hf_api_client import HFInferenceAgent
from hf_inference_workflow.validators import PNRValidator, DRCValidator, SAXValidator
from hf_inference_workflow.validators.loss_target_validator import LossTargetValidator
from hf_inference_workflow.optimization_integration import OptimizationStage
from hf_inference_workflow.retry_handler import RetryHandler, ValidationStage, AdaptiveRetryHandler
from hf_inference_workflow.config import (
    PYTHON_PROMPT_TEMPLATE,
    JSON_PROMPT_TEMPLATE,
    SAMPLES_PER_PROBLEM,
    MAX_RETRY_ATTEMPTS,
    CSV_OUTPUT_DIR,
    GDS_OUTPUT_DIR,
    PROBLEMS_FILE,
    ENABLE_OPTIMIZATION,
    ENABLE_LOSS_TARGET_CHECK,
    OPTIMIZATION_MAX_ITER,
    OPTIMIZATION_RESTARTS
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_problems(path: str) -> List[Tuple[int, str, str]]:
    """
    Load problems from text file.

    Format expected:
        Problem N (Title):
        Description...

    Returns:
        List of (index, title, body) tuples
    """
    txt = Path(path).read_text(encoding="utf-8")
    pat = re.compile(r"Problem\s+(\d+)\s*\(([^)]+)\)\s*:", re.I)
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


def parse_and_execute_code(code: str) -> Optional[gf.Component]:
    """
    Parse and execute generated Python code to create GDSFactory component.

    Args:
        code: Generated Python code

    Returns:
        GDSFactory Component if successful, None otherwise
    """
    try:
        # Clean code - remove markdown fences if present
        code = code.strip()
        if code.startswith("```"):
            code = code.strip("`")
            if code.startswith("python"):
                code = code[6:]

        # Create execution namespace
        ns = {"gf": gf}

        # Execute code
        exec(code, ns)

        # Try to find the component
        # Look for variable named 'r' or 'c' (common in examples)
        for var_name in ['r', 'c', 'circuit', 'component']:
            if var_name in ns and isinstance(ns[var_name], gf.Component):
                return ns[var_name]

        # If not found, look for any Component instance
        for value in ns.values():
            if isinstance(value, gf.Component):
                return value

        logger.error("No GDSFactory Component found in generated code")
        return None

    except SyntaxError as e:
        logger.error(f"Syntax error in generated code: {e}")
        return None
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return None


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
    retry_handler: RetryHandler,
    problem_idx: int,
    sample_idx: int,
    optimizer: OptimizationStage = None,
    loss_validator: LossTargetValidator = None,
    circuit_type: str = None
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
        "validation_reports": {}
    }

    retry_handler.reset()

    for attempt in range(MAX_RETRY_ATTEMPTS + 1):
        logger.info(f"Problem {problem_idx}, Sample {sample_idx}, Attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS + 1}")

        # Generate code
        if attempt == 0:
            # First attempt
            agent.start_new_conversation()
            code = agent.ASK_LLM(prompt, problem_desc)
        else:
            # Retry with feedback
            feedback = retry_handler.format_feedback_for_llm(
                failed_stage=result["failed_stage"],
                validation_reports=result["validation_reports"],
                problem_description=problem_desc
            )
            retry_prompt = retry_handler.create_retry_prompt(prompt, feedback, attempt)
            code = agent.ASK_LLM(prompt, retry_prompt)

        result["code"] = code
        result["retry_attempts"] = attempt

        # Parse and execute code
        logger.info("Parsing and executing generated code...")
        component = parse_and_execute_code(code)

        if component is None:
            logger.error("Failed to parse/execute code")
            result["failed_stage"] = ValidationStage.PARSING
            retry_handler.record_attempt(attempt, ValidationStage.PARSING, "Parsing failed", code)
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

        # Add optimization metrics (NEW)
        opt_report = reports.get('optimization', {})
        result["optimization_success"] = opt_report.get('success', False)
        result["il_before_db"] = opt_report.get('il_before_db')
        result["il_after_db"] = opt_report.get('il_after_db')
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
            break
        else:
            result["failed_stage"] = failed_stage
            retry_handler.record_attempt(attempt, failed_stage, "Validation failed", code)
            logger.warning(f"Validation failed at stage: {failed_stage.value}")

            if not retry_handler.should_retry(attempt + 1):
                logger.warning(f"Max retries reached")
                break

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
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)

    # Initialize optimizer and loss validator (NEW)
    optimizer = OptimizationStage(
        enable_optimization=ENABLE_OPTIMIZATION,
        max_iter=OPTIMIZATION_MAX_ITER,
        n_restarts=OPTIMIZATION_RESTARTS
    )
    loss_validator = LossTargetValidator()

    results = []
    total_designs = len(problems) * SAMPLES_PER_PROBLEM

    with tqdm(total=total_designs, desc=f"Generating validated designs") as pbar:
        for idx, title, body in problems:
            for sample in range(SAMPLES_PER_PROBLEM):
                logger.info(f"\n{'='*60}")
                logger.info(f"Problem {idx}: {title} - Sample {sample + 1}/{SAMPLES_PER_PROBLEM}")
                logger.info(f"{'='*60}")

                result = generate_with_validation(
                    agent=agent,
                    prompt=prompt_template,
                    problem_desc=body,
                    pnr_validator=pnr_validator,
                    drc_validator=drc_validator,
                    sax_validator=sax_validator,
                    retry_handler=retry_handler,
                    problem_idx=idx,
                    sample_idx=sample,
                    optimizer=optimizer,
                    loss_validator=loss_validator,
                    circuit_type=title.lower()  # Use title as circuit type hint
                )

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
