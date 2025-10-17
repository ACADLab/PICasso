"""
Validated Photonic Circuit Generation with OpenAI API

This module generates photonic circuit designs with comprehensive validation:
- P&R (Place & Route) checks
- DRC (Design Rule Checks)
- SAX compilation and routing validation

Saves BOTH first attempts and final clean designs for comparison.
Failed designs are retried with LLM feedback for improvement.
"""

import re
import sys
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import pandas as pd
from tqdm import tqdm
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gdsfactory as gf
from hf_inference_workflow.openai_api_client import OpenAIInferenceAgent
from hf_inference_workflow.validators import PNRValidator, DRCValidator, SAXValidator
from hf_inference_workflow.retry_handler import RetryHandler, ValidationStage, AdaptiveRetryHandler
from hf_inference_workflow.config import (
    PYTHON_PROMPT_TEMPLATE,
    JSON_PROMPT_TEMPLATE,
    SAMPLES_PER_PROBLEM,
    MAX_RETRY_ATTEMPTS,
    CSV_OUTPUT_DIR,
    GDS_FIRST_ATTEMPT_DIR,
    GDS_CLEAN_DIR,
    CODE_CLEAN_DIR,
    PROBLEMS_FILE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUEST_DELAY
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
    gds_path: str = None
) -> Tuple[bool, Dict[str, Dict], Optional[ValidationStage]]:
    """
    Run all validators on a design.

    Args:
        component: GDSFactory component to validate
        pnr_validator: P&R validator instance
        drc_validator: DRC validator instance
        sax_validator: SAX validator instance
        gds_path: Optional GDS file path for DRC

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

    logger.info("✅ All validations passed!")
    return True, reports, None


def generate_with_validation(
    agent: OpenAIInferenceAgent,
    prompt: str,
    problem_desc: str,
    pnr_validator: PNRValidator,
    drc_validator: DRCValidator,
    sax_validator: SAXValidator,
    retry_handler: RetryHandler,
    problem_idx: int,
    sample_idx: int
) -> Dict:
    """
    Generate design with validation and retry logic.

    Saves:
    - First attempt GDS (always)
    - Final clean GDS + code (only if validation passes)

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
        "first_attempt_status": None,
        "first_attempt_failed_stage": None,
        "pnr_passed": False,
        "drc_passed": False,
        "sax_passed": False,
        "first_attempt_gds_path": None,
        "final_gds_path": None,
        "final_code_path": None,
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

            # Record first attempt failure
            if attempt == 0:
                result["first_attempt_status"] = "failed"
                result["first_attempt_failed_stage"] = "PARSING"

            retry_handler.record_attempt(attempt, ValidationStage.PARSING, "Parsing failed", code)
            continue

        # Create GDS file paths
        gds_filename_temp = f"problem_{problem_idx}_sample_{sample_idx}_attempt_{attempt}.gds"
        gds_path_temp = str(GDS_FIRST_ATTEMPT_DIR / gds_filename_temp)

        try:
            component.write_gds(gds_path_temp)

            # Save first attempt GDS (always save attempt 0)
            if attempt == 0:
                result["first_attempt_gds_path"] = gds_path_temp
                logger.info(f"✅ First attempt GDS saved: {gds_path_temp}")

        except Exception as e:
            logger.error(f"Failed to write GDS: {e}")
            result["failed_stage"] = ValidationStage.PARSING

            if attempt == 0:
                result["first_attempt_status"] = "failed"
                result["first_attempt_failed_stage"] = "GDS_WRITE"

            continue

        # Run validations
        all_passed, reports, failed_stage = validate_design(
            component, pnr_validator, drc_validator, sax_validator, gds_path_temp
        )

        result["validation_reports"] = reports
        result["pnr_passed"] = reports.get('pnr', {}).get('passed', False)
        result["drc_passed"] = reports.get('drc', {}).get('passed', False)
        result["sax_passed"] = reports.get('sax', {}).get('passed', False)

        # Record first attempt status
        if attempt == 0:
            if all_passed:
                result["first_attempt_status"] = "passed"
            else:
                result["first_attempt_status"] = "failed"
                result["first_attempt_failed_stage"] = failed_stage.value if failed_stage else "UNKNOWN"

        if all_passed:
            # SUCCESS! Save to PIC_set
            result["success"] = True
            result["failed_stage"] = None

            # Save final clean GDS
            gds_clean_filename = f"problem_{problem_idx}_sample_{sample_idx}_final.gds"
            gds_clean_path = str(GDS_CLEAN_DIR / gds_clean_filename)
            component.write_gds(gds_clean_path)
            result["final_gds_path"] = gds_clean_path
            logger.info(f"✅ Clean GDS saved: {gds_clean_path}")

            # Save final clean Python code
            code_clean_filename = f"problem_{problem_idx}_sample_{sample_idx}_final.py"
            code_clean_path = str(CODE_CLEAN_DIR / code_clean_filename)
            with open(code_clean_path, 'w', encoding='utf-8') as f:
                f.write(code)
            result["final_code_path"] = code_clean_path
            logger.info(f"✅ Clean Python code saved: {code_clean_path}")

            logger.info(f"✅ Design validated successfully after {attempt + 1} attempt(s)!")
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
    agent: OpenAIInferenceAgent,
    problems: List[Tuple[int, str, str]],
    prompt_template: str,
    csv_name: str,
    samples_per_problem: int = None
):
    """
    Run validated generation for all problems.

    Args:
        agent: OpenAI Inference agent
        problems: List of (idx, title, body) tuples
        prompt_template: Prompt template to use
        csv_name: Output CSV filename
        samples_per_problem: Override number of samples per problem
    """
    # Initialize validators
    pnr_validator = PNRValidator()
    drc_validator = DRCValidator()
    sax_validator = SAXValidator()
    retry_handler = AdaptiveRetryHandler(max_retries=MAX_RETRY_ATTEMPTS)

    # Use override if provided, otherwise use config
    num_samples = samples_per_problem if samples_per_problem is not None else SAMPLES_PER_PROBLEM

    results = []
    total_designs = len(problems) * num_samples

    with tqdm(total=total_designs, desc=f"Generating validated designs") as pbar:
        for idx, title, body in problems:
            for sample in range(num_samples):
                logger.info(f"\n{'='*60}")
                logger.info(f"Problem {idx}: {title} - Sample {sample + 1}/{num_samples}")
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
                    sample_idx=sample
                )

                # Format result for CSV
                csv_row = {
                    "problem_idx": idx,
                    "problem_title": title,
                    "sample": sample,
                    "first_attempt_status": result["first_attempt_status"],
                    "first_attempt_failed_stage": result["first_attempt_failed_stage"],
                    "first_attempt_gds_path": result["first_attempt_gds_path"],
                    "retry_attempts": result["retry_attempts"],
                    "final_success": result["success"],
                    "final_failed_stage": result["failed_stage"].value if result["failed_stage"] else None,
                    "final_pnr_passed": result["pnr_passed"],
                    "final_drc_passed": result["drc_passed"],
                    "final_sax_passed": result["sax_passed"],
                    "final_gds_path": result["final_gds_path"],
                    "final_code_path": result["final_code_path"],
                }

                results.append(csv_row)
                pbar.update(1)

                # Add inter-request delay to avoid rate limits (except after last design)
                is_last_design = (idx == problems[-1][0] and sample == num_samples - 1)
                if not is_last_design:
                    logger.info(f"Waiting {REQUEST_DELAY}s to avoid rate limits...")
                    time.sleep(REQUEST_DELAY)

    # Save results to CSV
    df = pd.DataFrame(results)
    csv_path = CSV_OUTPUT_DIR / csv_name
    df.to_csv(csv_path, index=False)

    # Print summary statistics
    logger.info(f"\n{'='*60}")
    logger.info("GENERATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total designs attempted: {len(results)}")
    logger.info(f"First attempt success rate: {(df['first_attempt_status'] == 'passed').sum()} ({(df['first_attempt_status'] == 'passed').mean()*100:.1f}%)")
    logger.info(f"Final successful designs: {df['final_success'].sum()} ({df['final_success'].mean()*100:.1f}%)")
    logger.info(f"Average retry attempts: {df['retry_attempts'].mean():.2f}")
    logger.info(f"Final P&R pass rate: {df['final_pnr_passed'].sum()} ({df['final_pnr_passed'].mean()*100:.1f}%)")
    logger.info(f"Final DRC pass rate: {df['final_drc_passed'].sum()} ({df['final_drc_passed'].mean()*100:.1f}%)")
    logger.info(f"Final SAX pass rate: {df['final_sax_passed'].sum()} ({df['final_sax_passed'].mean()*100:.1f}%)")
    logger.info(f"\nResults saved to: {csv_path}")
    logger.info(f"First attempt GDS files: {GDS_FIRST_ATTEMPT_DIR}")
    logger.info(f"Clean dataset (PIC_set): {GDS_CLEAN_DIR}")


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate validated photonic circuits with OpenAI API")
    parser.add_argument("--problems", type=str, default=str(PROBLEMS_FILE), help="Path to problems file")
    parser.add_argument("--output", type=str, default="openai_validated_designs.csv", help="Output CSV filename")
    parser.add_argument("--samples", type=int, default=SAMPLES_PER_PROBLEM, help="Samples per problem")
    parser.add_argument("--model", type=str, default=OPENAI_MODEL, help="OpenAI model to use")
    parser.add_argument("--format", type=str, choices=["python", "json"], default="python", help="Output format")
    parser.add_argument("--api-key", type=str, default=None, help="OpenAI API key (optional)")

    args = parser.parse_args()

    # Load problems
    problems = load_problems(args.problems)

    # Initialize agent
    logger.info("Initializing OpenAI Inference Agent...")
    logger.info(f"Model: {args.model}")
    api_key = args.api_key if args.api_key else OPENAI_API_KEY
    agent = OpenAIInferenceAgent(api_key=api_key, model=args.model)

    # Select prompt template
    prompt = PYTHON_PROMPT_TEMPLATE if args.format == "python" else JSON_PROMPT_TEMPLATE

    # Run generation
    run_validated_generation(
        agent=agent,
        problems=problems,
        prompt_template=prompt,
        csv_name=args.output,
        samples_per_problem=args.samples
    )

    logger.info("\n✅ Generation complete!")
    logger.info(f"\n📊 Check results:")
    logger.info(f"  - CSV report: {CSV_OUTPUT_DIR / args.output}")
    logger.info(f"  - First attempts: {GDS_FIRST_ATTEMPT_DIR}")
    logger.info(f"  - Clean dataset: {GDS_CLEAN_DIR}")


if __name__ == "__main__":
    main()
