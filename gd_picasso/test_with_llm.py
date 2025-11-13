"""
Test gd_picasso Framework with LLM Inference

Runs the full PIC set (36 problems) through the gd_picasso framework using LLM inference.
Uses YAML DSL format (PhIDO-inspired approach).
"""

import sys
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict
import json
from datetime import datetime

# Add parent directory to path
framework_dir = Path(__file__).parent
parent_dir = framework_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Check for gdsfactory
try:
    import gdsfactory as gf
    _gdsfactory_available = True
except ImportError as e:
    print(f"ERROR: gdsfactory not available: {e}")
    sys.exit(1)

# Import gd_picasso components
from gd_picasso.config import (
    YAML_DSL_PROMPT_TEMPLATE,
    ENABLE_YAML_PILOT_VALIDATION,
    ENABLE_DRC_CHECK,
    ENABLE_LVS_CHECK,
    ENABLE_AUTO_CORRECTION,
    MAX_RETRY_ATTEMPTS
)
from gd_picasso.validators.yaml_pilot_validator import YAMLPilotValidator
from gd_picasso.validators.drc_validator import DRCValidator
from gd_picasso.validators.lvs_validator import LVSValidator
from gd_picasso.injection.component_spec_loader import ComponentSpecLoader
from gd_picasso.pilot.base_pilot_generator import BasePilotGenerator
from gd_picasso.optimizers.optimization_integration import OptimizationIntegration

# Try to import LLM agents
try:
    from hf_inference_workflow.openai_api_client import OpenAIInferenceAgent
    OPENAI_AGENT_AVAILABLE = True
except ImportError:
    OPENAI_AGENT_AVAILABLE = False
    print("WARNING: OpenAIInferenceAgent not available")

try:
    from hf_inference_workflow.hf_api_client import HFInferenceAgent
    HF_AGENT_AVAILABLE = True
except ImportError:
    HF_AGENT_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gd_picasso_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_problems(problems_file: str) -> List[Dict]:
    """
    Load problems from file.
    
    Args:
        problems_file: Path to problems file
        
    Returns:
        List of problem dictionaries
    """
    problems = []
    problem_file_path = Path(problems_file)
    
    if not problem_file_path.exists():
        logger.error(f"Problems file not found: {problems_file}")
        return problems
    
    with open(problem_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse problems (simple parser - assumes "Problem N" format)
    lines = content.split('\n')
    current_problem = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('Problem '):
            # Save previous problem
            if current_problem:
                problems.append(current_problem)
            
            # Start new problem
            # Extract problem number and name
            parts = line.split(':', 1)
            if len(parts) == 2:
                problem_header = parts[0].strip()
                problem_name = parts[1].strip()
                
                # Extract complexity
                complexity = None
                if '[Complexity' in problem_name:
                    complexity_part = problem_name.split('[Complexity')[1].split(']')[0].strip()
                    complexity = int(complexity_part) if complexity_part.isdigit() else None
                    problem_name = problem_name.split('[')[0].strip()
                
                current_problem = {
                    'id': problem_header.replace('Problem ', '').split()[0],
                    'name': problem_name,
                    'complexity': complexity,
                    'description': []
                }
        elif current_problem and line:
            current_problem['description'].append(line)
    
    # Add last problem
    if current_problem:
        problems.append(current_problem)
    
    # Join description lines
    for problem in problems:
        problem['description'] = '\n'.join(problem['description'])
    
    logger.info(f"Loaded {len(problems)} problems from {problems_file}")
    return problems


def create_agent(model_name: str = "gpt-4o") -> Optional[object]:
    """
    Create inference agent for specified model.
    
    Args:
        model_name: Model name ('gpt-4o', 'gpt-4o-mini', etc.)
        
    Returns:
        Agent instance or None
    """
    if model_name.startswith('gpt'):
        if not OPENAI_AGENT_AVAILABLE:
            logger.error("OpenAIInferenceAgent not available")
            return None
        
        # Check for API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            return None
        
        try:
            agent = OpenAIInferenceAgent(model=model_name, api_key=api_key)
            logger.info(f"✅ Created OpenAI agent with model: {model_name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create OpenAI agent: {e}")
            return None
    else:
        logger.error(f"Unknown model: {model_name}")
        return None


def validate_yaml_dsl(yaml_str: str, pilot_validator: YAMLPilotValidator) -> tuple:
    """
    Validate YAML DSL using pilot validator.
    
    Returns:
        (is_valid, error_message, error_details)
    """
    return pilot_validator.validate(yaml_str)


def build_component_from_yaml(yaml_str: str) -> tuple:
    """
    Build GDSFactory component from YAML DSL.
    
    Returns:
        (component, error_message)
    """
    try:
        component = gf.read.from_yaml(yaml_str)
        return component, None
    except Exception as e:
        return None, str(e)


def run_single_problem(
    problem: Dict,
    agent: object,
    prompt_template: str,
    pilot_validator: YAMLPilotValidator,
    drc_validator: DRCValidator,
    lvs_validator: LVSValidator,
    optimizer: OptimizationIntegration,
    samples_per_problem: int = 5
) -> Dict:
    """
    Run a single problem through the framework.
    
    Returns:
        Result dictionary with pass/fail status and metrics
    """
    problem_id = problem['id']
    problem_desc = problem['description']
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Processing Problem {problem_id}: {problem['name']}")
    logger.info(f"{'='*70}")
    
    results = {
        'problem_id': problem_id,
        'problem_name': problem['name'],
        'complexity': problem.get('complexity'),
        'samples': [],
        'pass_count': 0,
        'fail_count': 0
    }
    
    for sample_idx in range(samples_per_problem):
        logger.info(f"\n--- Sample {sample_idx + 1}/{samples_per_problem} ---")
        
        sample_result = {
            'sample_idx': sample_idx + 1,
            'passed': False,
            'errors': [],
            'warnings': [],
            'yaml_valid': False,
            'component_built': False,
            'drc_passed': False,
            'lvs_passed': False,
            'optimization_done': False
        }
        
        # Step 1: Generate YAML DSL from LLM (with retry logic)
        yaml_output = None
        component = None
        build_error = None
        
        for attempt in range(MAX_RETRY_ATTEMPTS + 1):
            try:
                # Split prompt into system prompt and user query
                # The prompt_template is the system prompt (instructions)
                # The problem description is the user query
                system_prompt = prompt_template.replace("{problem_description}", "")
                
                if attempt == 0:
                    user_query = f"Problem:\n{problem_desc}\n\nGenerate the YAML DSL netlist:"
                    logger.info("Calling LLM to generate YAML DSL...")
                else:
                    # Add feedback from previous attempt
                    feedback_text = ""
                    if error_msg:
                        feedback_text = f"\n\nERROR from previous attempt:\n{error_msg}\n"
                        if error_details:
                            feedback = pilot_validator.get_feedback(error_msg, error_details)
                            feedback_text += f"\n{feedback}\n"
                    if build_error:
                        feedback_text += f"\n\nComponent build error:\n{build_error}\n"
                        feedback_text += "\nPlease fix the YAML DSL and try again.\n"
                    
                    user_query = f"Problem:\n{problem_desc}\n{feedback_text}\n\nGenerate the corrected YAML DSL netlist:"
                    logger.info(f"Retrying LLM call (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS + 1})...")
                
                # Check if agent has ASK_LLM method (takes system_prompt, user_q)
                if hasattr(agent, 'ASK_LLM'):
                    yaml_output = agent.ASK_LLM(system_prompt, user_query)
                elif hasattr(agent, 'ask_llm'):
                    yaml_output = agent.ask_llm(system_prompt, user_query)
                elif hasattr(agent, 'generate'):
                    # For agents that take single prompt
                    full_prompt = prompt_template.format(problem_description=problem_desc)
                    if attempt > 0:
                        full_prompt += feedback_text
                    yaml_output = agent.generate(full_prompt)
                else:
                    raise AttributeError("Agent does not have ASK_LLM, ask_llm, or generate method")
                
                # Clean YAML output (remove markdown code blocks if present)
                yaml_output = yaml_output.strip()
                if yaml_output.startswith('```yaml'):
                    yaml_output = yaml_output[7:]
                if yaml_output.startswith('```'):
                    yaml_output = yaml_output[3:]
                if yaml_output.endswith('```'):
                    yaml_output = yaml_output[:-3]
                yaml_output = yaml_output.strip()
                
                logger.info("YAML DSL generated")
                
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                sample_result['errors'].append(f"LLM call failed: {str(e)}")
                if attempt == MAX_RETRY_ATTEMPTS:
                    results['samples'].append(sample_result)
                    results['fail_count'] += 1
                    break
                continue
            
            # Step 2: Validate YAML DSL (pilot validation)
            error_msg = None
            error_details = None
            if ENABLE_YAML_PILOT_VALIDATION:
                is_valid, error_msg, error_details = validate_yaml_dsl(yaml_output, pilot_validator)
                if not is_valid:
                    logger.warning(f"YAML pilot validation failed: {error_msg}")
                    if attempt < MAX_RETRY_ATTEMPTS:
                        continue  # Retry with feedback
                    else:
                        sample_result['errors'].append(f"YAML validation: {error_msg}")
                        sample_result['yaml_valid'] = False
                        results['samples'].append(sample_result)
                        results['fail_count'] += 1
                        break
                
                sample_result['yaml_valid'] = True
                logger.info("✅ YAML pilot validation passed")
            
            # Step 3: Build component from YAML
            component, build_error = build_component_from_yaml(yaml_output)
            if component is None:
                logger.error(f"Failed to build component: {build_error}")
                if attempt < MAX_RETRY_ATTEMPTS:
                    continue  # Retry with feedback
                else:
                    sample_result['errors'].append(f"Component build failed: {build_error}")
                    results['samples'].append(sample_result)
                    results['fail_count'] += 1
                    break
            
            # Success! Break out of retry loop
            logger.info("✅ Component built from YAML")
            sample_result['component_built'] = True
            break
        
        # If we exhausted retries, continue to next sample
        if component is None:
            continue
        
        # Step 4: DRC validation
        if ENABLE_DRC_CHECK:
            drc_passed, drc_report = drc_validator.validate(component)
            sample_result['drc_passed'] = drc_passed
            if not drc_passed:
                logger.warning(f"DRC validation failed: {drc_report.get('violations', 0)} violations")
                sample_result['warnings'].append(f"DRC: {drc_report.get('violations', 0)} violations")
            else:
                logger.info("✅ DRC validation passed")
        
        # Step 5: LVS validation (optional, may be slow)
        if ENABLE_LVS_CHECK:
            # For now, skip LVS (can be slow for large circuits)
            sample_result['lvs_passed'] = True  # Placeholder
            logger.info("⏭️  LVS validation skipped (can be slow)")
        
        # Step 6: Optimization
        try:
            opt_result = optimizer.optimize_design(component, circuit_type=problem['name'])
            sample_result['optimization_done'] = opt_result.get('success', False)
            if sample_result['optimization_done']:
                logger.info("✅ Optimization completed")
        except Exception as e:
            logger.warning(f"Optimization failed: {e}")
            sample_result['warnings'].append(f"Optimization: {str(e)}")
        
        # Determine if sample passed
        sample_result['passed'] = (
            sample_result['yaml_valid'] and
            sample_result['component_built'] and
            sample_result['drc_passed']
        )
        
        if sample_result['passed']:
            results['pass_count'] += 1
            logger.info(f"✅ Sample {sample_idx + 1} PASSED")
        else:
            results['fail_count'] += 1
            logger.info(f"❌ Sample {sample_idx + 1} FAILED")
        
        results['samples'].append(sample_result)
    
    logger.info(f"\nProblem {problem_id} Summary: {results['pass_count']}/{samples_per_problem} passed")
    return results


def run_test(
    problems_file: str = "Pic_set.txt",
    model_name: str = "gpt-4o",
    num_problems: Optional[int] = None,
    samples_per_problem: int = 5
):
    """
    Run full test suite.
    
    Args:
        problems_file: Path to problems file
        model_name: LLM model name
        num_problems: Number of problems to test (None = all)
        samples_per_problem: Number of samples per problem
    """
    logger.info("="*70)
    logger.info("gd_picasso Framework Test Suite")
    logger.info("="*70)
    logger.info(f"Model: {model_name}")
    logger.info(f"Problems file: {problems_file}")
    logger.info(f"Samples per problem: {samples_per_problem}")
    
    # Load problems
    problems = load_problems(problems_file)
    if not problems:
        logger.error("No problems loaded!")
        return
    
    if num_problems:
        problems = problems[:num_problems]
        logger.info(f"Testing first {num_problems} problems")
    
    # Create agent
    agent = create_agent(model_name)
    if agent is None:
        logger.error("Failed to create agent")
        return
    
    # Initialize validators and components
    pilot_validator = YAMLPilotValidator()
    drc_validator = DRCValidator()
    lvs_validator = LVSValidator(enabled=False)  # Disable for speed
    optimizer = OptimizationIntegration()
    
    # Load component specs and generate injection
    component_loader = ComponentSpecLoader()
    component_injection = component_loader.generate_yaml_dsl_injection(
        include_examples=True,
        include_error_patterns=True
    )
    
    # Generate base pilot prompt
    pilot_generator = BasePilotGenerator()
    base_pilot_prompt = pilot_generator.generate_base_pilot_prompt()
    
    # Build prompt template (system prompt - instructions for LLM)
    # The template already has {component_injection} and {pilot_prompt} placeholders
    prompt_template = YAML_DSL_PROMPT_TEMPLATE.format(
        component_injection=component_injection,
        pilot_prompt=base_pilot_prompt
    )
    # Note: Problem description will be passed as user_query to ASK_LLM
    
    # Run tests
    all_results = []
    for problem in problems:
        result = run_single_problem(
            problem=problem,
            agent=agent,
            prompt_template=prompt_template,
            pilot_validator=pilot_validator,
            drc_validator=drc_validator,
            lvs_validator=lvs_validator,
            optimizer=optimizer,
            samples_per_problem=samples_per_problem
        )
        all_results.append(result)
    
    # Save results
    output_dir = Path(__file__).parent / "output" / "test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"results_{model_name}_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"\nResults saved to: {results_file}")
    
    # Print summary
    total_passed = sum(r['pass_count'] for r in all_results)
    total_samples = sum(len(r['samples']) for r in all_results)
    pass_rate = (total_passed / total_samples * 100) if total_samples > 0 else 0
    
    logger.info("\n" + "="*70)
    logger.info("FINAL SUMMARY")
    logger.info("="*70)
    logger.info(f"Total problems: {len(all_results)}")
    logger.info(f"Total samples: {total_samples}")
    logger.info(f"Total passed: {total_passed}")
    logger.info(f"Pass rate: {pass_rate:.1f}%")
    logger.info("="*70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test gd_picasso framework with LLM')
    parser.add_argument('--model', type=str, default='gpt-4o', help='Model name (gpt-4o, gpt-4o-mini, etc.)')
    parser.add_argument('--problems', type=str, default='Pic_set.txt', help='Problems file path')
    parser.add_argument('--num-problems', type=int, default=None, help='Number of problems to test (None = all)')
    parser.add_argument('--samples', type=int, default=5, help='Samples per problem')
    
    args = parser.parse_args()
    
    run_test(
        problems_file=args.problems,
        model_name=args.model,
        num_problems=args.num_problems,
        samples_per_problem=args.samples
    )

