"""
Test gd_picasso Framework with LLM Inference

Runs the full PIC set (36 problems) through the gd_picasso framework using LLM inference.
Uses YAML DSL format for direct netlist generation.
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
    VANILLA_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    ENABLE_YAML_PILOT_VALIDATION,
    ENABLE_DRC_CHECK,
    ENABLE_LVS_CHECK,
    ENABLE_SAX_CHECK,
    ENABLE_AUTO_CORRECTION,
    MAX_RETRY_ATTEMPTS,
    OUTPUT_DIR
)
from gd_picasso.metrics import (
    compute_metrics_for_circuit,
    compute_comparison_metrics
)
from gd_picasso.validators.yaml_pilot_validator import YAMLPilotValidator
from gd_picasso.validators.drc_validator import DRCValidator
from gd_picasso.validators.lvs_validator import LVSValidator
from gd_picasso.validators.sax_validator import SAXValidator
from gd_picasso.utils.yaml_routing_fixer import fix_routing_and_placement_iterative
from gd_picasso.validators.silicon_efficiency_validator import SiliconEfficiencyValidator
from gd_picasso.validators.port_connection_validator import PortConnectionValidator
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

# Try to import new agent classes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gd_picasso_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Try to import new agent classes
try:
    from gd_picasso.agents.deepseek_agent import DeepSeekInferenceAgent
    DEEPSEEK_AGENT_AVAILABLE = True
except ImportError:
    DEEPSEEK_AGENT_AVAILABLE = False
    logger.warning("DeepSeek agent not available")

try:
    from gd_picasso.agents.anthropic_agent import AnthropicInferenceAgent
    ANTHROPIC_AGENT_AVAILABLE = True
except ImportError:
    ANTHROPIC_AGENT_AVAILABLE = False
    logger.warning("Anthropic agent not available")

try:
    from gd_picasso.agents.gemini_agent import GeminiInferenceAgent
    GEMINI_AGENT_AVAILABLE = True
except ImportError:
    GEMINI_AGENT_AVAILABLE = False
    logger.warning("Gemini agent not available")


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
    
    # Parse problems (handles both "TASK N" and "Problem N" format)
    lines = content.split('\n')
    current_problem = None
    
    for line in lines:
        line = line.strip()
        # Check for TASK N or Problem N format
        if line.startswith('TASK ') or line.startswith('Problem '):
            # Save previous problem
            if current_problem:
                problems.append(current_problem)
            
            # Start new problem
            # Extract problem number and name
            parts = line.split(' - ', 1)  # TASK N - Name format
            if len(parts) == 2:
                problem_header = parts[0].strip()
                problem_name = parts[1].strip()
            else:
                # Try Problem N: Name format
                parts = line.split(':', 1)
                if len(parts) == 2:
                    problem_header = parts[0].strip()
                    problem_name = parts[1].strip()
                else:
                    problem_header = line
                    problem_name = ""
            
            # Extract problem number
            if problem_header.startswith('TASK '):
                problem_id = problem_header.replace('TASK ', '').split()[0]
            elif problem_header.startswith('Problem '):
                problem_id = problem_header.replace('Problem ', '').split()[0]
            else:
                problem_id = str(len(problems) + 1)
            
            # Extract complexity if present
            complexity = None
            if '[Complexity' in problem_name:
                complexity_part = problem_name.split('[Complexity')[1].split(']')[0].strip()
                complexity = int(complexity_part) if complexity_part.isdigit() else None
                problem_name = problem_name.split('[')[0].strip()
            
            current_problem = {
                'id': problem_id,
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
        model_name: Model name ('gpt-4o', 'gpt-4o-mini', 'deepseek-r1', 'kimi2', etc.)
        
    Returns:
        Agent instance or None
    """
    # Model name mapping (short names -> full HuggingFace model IDs)
    MODEL_MAPPING = {
        # DeepSeek (HuggingFace)
        'deepseek-r1': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B',
        'deepseek-coder': 'deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct',
        # Kimi models
        'kimi2': 'moonshotai/Kimi-K2-Thinking',
        'kimi': 'moonshotai/Kimi-K2-Thinking',
        'kimi-v2': 'moonshotai/Kimi-V2',
        'kimi-thinking': 'moonshotai/Kimi-K2-Thinking',
        # Llama models
        'llama-3.1-70b': 'meta-llama/Llama-3.1-70B-Instruct',
        # Qwen models
        'qwen-2.5-32b': 'Qwen/Qwen2.5-32B-Instruct',
        # Mistral models
        'mistral-large': 'mistralai/Mistral-Large-2407',
        # Phi models
        'phi-4': 'microsoft/Phi-4-mini',
    }
    
    # Check if it's a DeepSeek API model
    if model_name in ['deepseek-r1-api', 'deepseek-v3-api']:
        if not DEEPSEEK_AGENT_AVAILABLE:
            logger.error("DeepSeekInferenceAgent not available")
            return None
        
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            logger.error("DEEPSEEK_API_KEY environment variable not set")
            return None
        
        try:
            # Map model names to DeepSeek API model names
            deepseek_model_map = {
                'deepseek-r1-api': 'deepseek-chat',
                'deepseek-v3-api': 'deepseek-reasoner'
            }
            deepseek_model = deepseek_model_map.get(model_name, 'deepseek-chat')
            agent = DeepSeekInferenceAgent(api_key=api_key, model=deepseek_model)
            logger.info(f"✅ Created DeepSeek API agent with model: {deepseek_model}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create DeepSeek API agent: {e}")
            return None
    
    # Check if it's an Anthropic Claude model
    elif model_name in ['claude-sonnet-4.5', 'claude-sonnet-4-20250514'] or model_name.startswith('claude-'):
        if not ANTHROPIC_AGENT_AVAILABLE:
            logger.error("AnthropicInferenceAgent not available")
            return None
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set")
            return None
        
        try:
            # Map model names to Anthropic API model names
            anthropic_model_map = {
                'claude-sonnet-4.5': 'claude-sonnet-4-20250514',
                'claude-sonnet-4-20250514': 'claude-sonnet-4-20250514'
            }
            anthropic_model = anthropic_model_map.get(model_name, model_name)
            agent = AnthropicInferenceAgent(api_key=api_key, model=anthropic_model)
            logger.info(f"✅ Created Anthropic agent with model: {anthropic_model}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Anthropic agent: {e}")
            return None
    
    # Check if it's a Google Gemini model
    elif model_name in ['gemini-2.5-pro', 'gemini-2.0-flash-exp'] or model_name.startswith('gemini-'):
        if not GEMINI_AGENT_AVAILABLE:
            logger.error("GeminiInferenceAgent not available")
            return None
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable not set")
            return None
        
        try:
            # Use model name as-is for Gemini
            agent = GeminiInferenceAgent(api_key=api_key, model=model_name)
            logger.info(f"✅ Created Gemini agent with model: {model_name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create Gemini agent: {e}")
            return None
    
    # Check if it's a GPT model (OpenAI) - including GPT-5 and o3
    elif model_name.startswith('gpt') or model_name.startswith('o3'):
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
    
    # Check if it's a HuggingFace model (but not DeepSeek API models)
    elif (model_name in MODEL_MAPPING or '/' in model_name or 
          model_name.startswith('kimi') or model_name.startswith('llama') or
          model_name.startswith('qwen') or model_name.startswith('mistral') or
          model_name.startswith('phi')):
        if not HF_AGENT_AVAILABLE:
            logger.error("HFInferenceAgent not available")
            return None
        
        # Get HuggingFace API token from environment variables only
        api_token = os.getenv('HF_TOKEN') or os.getenv('HF_API_TOKEN')
        
        if not api_token:
            logger.error("HF_TOKEN or HF_API_TOKEN environment variable not set")
            logger.error("Please set your HuggingFace API token. Get it from: https://huggingface.co/settings/tokens")
            return None
        
        # Map short name to full model ID
        if model_name in MODEL_MAPPING:
            full_model_name = MODEL_MAPPING[model_name]
        else:
            full_model_name = model_name
        
        # Handle provider tags (e.g., kimi2:novita)
        provider = None
        if ':' in full_model_name:
            parts = full_model_name.split(':')
            full_model_name = parts[0]
            provider = parts[1]
        
        # For kimi models, try alternative providers if novita is having issues
        # Known alternative providers: fal-ai, together, etc.
        # If kimi model and no provider specified, try fal-ai as fallback
        if (full_model_name.startswith('moonshotai/Kimi') or 
            'kimi' in model_name.lower()) and not provider:
            # Try fal-ai provider as alternative to novita (often more stable)
            provider = 'fal-ai'
            logger.info(f"Using fal-ai provider for {full_model_name} (alternative to novita)")
        
        try:
            # Add timeout and provider parameters to prevent indefinite hangs
            # Pass provider directly to agent initialization
            agent = HFInferenceAgent(
                api_token=api_token, 
                model=full_model_name, 
                timeout=30.0,
                provider=provider  # Pass provider directly
            )
            logger.info(f"✅ Created HuggingFace agent with model: {full_model_name}" + (f" (provider: {provider})" if provider else ""))
            return agent
        except Exception as e:
            logger.error(f"Failed to create HuggingFace agent: {e}")
            return None
    
    else:
        logger.error(f"Unknown model: {model_name}")
        logger.error("Supported models:")
        logger.error("  - OpenAI: gpt-4o, gpt-5, o3-mini, o3")
        logger.error("  - DeepSeek API: deepseek-r1-api, deepseek-v3-api")
        logger.error("  - Anthropic: claude-sonnet-4.5")
        logger.error("  - Google: gemini-2.5-pro, gemini-2.0-flash-exp")
        logger.error("  - HuggingFace: deepseek-r1, kimi-v2, kimi-thinking, llama-3.1-70b, qwen-2.5-32b, mistral-large, phi-4")
        logger.error("  - Or use full HuggingFace model ID")
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


def save_results(
    model_name: str,
    phase: str,
    problem_id: str,
    sample_idx: int,
    yaml_output: str,
    component: Optional[gf.Component],
    metrics: Dict,
    output_base: Path = None
) -> Dict[str, Path]:
    """
    Save results for a single sample.
    
    Args:
        model_name: Model name (e.g., 'gpt-4o')
        phase: 'vanilla' or 'picasso'
        problem_id: Problem ID
        sample_idx: Sample index (1-based)
        yaml_output: YAML DSL string
        component: GDSFactory component (if built successfully)
        metrics: Metrics dictionary
        output_base: Base output directory (default: OUTPUT_DIR)
    
    Returns:
        Dictionary with paths to saved files
    """
    if output_base is None:
        output_base = OUTPUT_DIR
    
    # Create directory structure: {model}_results/{phase}/problem_{id}/sample_{idx}/
    result_dir = output_base / f"{model_name}_results" / phase / f"problem_{problem_id}" / f"sample_{sample_idx}"
    result_dir.mkdir(parents=True, exist_ok=True)
    
    saved_files = {}
    
    # Save YAML
    yaml_path = result_dir / "circuit.yaml"
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_output)
    saved_files['yaml'] = yaml_path
    
    # Save GDS if component exists
    if component is not None:
        gds_path = result_dir / "circuit.gds"
        try:
            component.write_gds(str(gds_path))
            saved_files['gds'] = gds_path
        except Exception as e:
            logger.warning(f"Failed to save GDS: {e}")
    
    # Save metrics
    metrics_path = result_dir / "metrics.txt"
    with open(metrics_path, 'w', encoding='utf-8') as f:
        f.write(f"Sample {sample_idx} Metrics:\n")
        f.write(f"  Structural Pass: {metrics.get('structural_pass', False)}\n")
        f.write(f"  Functional Pass: {metrics.get('functional_pass', False)}\n")
        f.write(f"  DRC Pass: {metrics.get('drc_passed', False)}\n")
        f.write(f"  LVS Pass: {metrics.get('lvs_passed', False)}\n")
        f.write(f"  Optimization Done: {metrics.get('optimization_done', False)}\n")
        f.write(f"\n")
        if 'pass_at_k' in metrics:
            f.write(f"  Pass@k: {metrics.get('pass_at_k', 0.0):.3f}\n")
        if phase == "vanilla":
            if 'spec_at_k_structural' in metrics:
                f.write(f"  Spec@k_structural: {metrics.get('spec_at_k_structural', 0.0):.3f}\n")
        else:
            if 'spec_at_k_full' in metrics:
                f.write(f"  Spec@k_full: {metrics.get('spec_at_k_full', 0.0):.3f}\n")
            if 'spec_at_k_structural' in metrics:
                f.write(f"  Spec@k_structural: {metrics.get('spec_at_k_structural', 0.0):.3f}\n")
        if 'opt_eff' in metrics:
            f.write(f"  OptEff: {metrics.get('opt_eff', 0.0):.3f}\n")
        if 'robust_pass' in metrics:
            f.write(f"  RobustPass: {metrics.get('robust_pass', 0.0):.3f}\n")
        if 'robustness_score' in metrics:
            f.write(f"  Overall Robustness Score: {metrics.get('robustness_score', 0.0):.3f}\n")
    saved_files['metrics'] = metrics_path
    
    return saved_files


def get_completed_problems(model_name: str, output_base: Path = None) -> Dict[str, set]:
    """
    Check which problems and phases have already been completed.
    
    Returns:
        Dict with keys 'vanilla' and 'picasso', each containing a set of completed problem IDs
    """
    if output_base is None:
        output_base = OUTPUT_DIR
    
    import csv
    
    csv_path = output_base / f"{model_name}_results" / "metrics.csv"
    
    completed = {'vanilla': set(), 'picasso': set()}
    
    if csv_path.exists():
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    problem_id = row.get('problem_id', '')
                    phase = row.get('phase', '').lower()
                    if problem_id and phase in completed:
                        completed[phase].add(problem_id)
        except Exception as e:
            logger.warning(f"Failed to read existing metrics CSV: {e}")
    
    return completed


def save_aggregated_metrics(
    model_name: str,
    all_results: List[Dict],
    output_base: Path = None,
    append: bool = False
) -> Path:
    """
    Save aggregated metrics CSV.
    
    Args:
        model_name: Model name
        all_results: List of all problem results
        output_base: Base output directory
        append: If True, append to existing CSV. If False, overwrite.
    
    Returns:
        Path to saved CSV file
    """
    if output_base is None:
        output_base = OUTPUT_DIR
    
    import csv
    
    csv_path = output_base / f"{model_name}_results" / "metrics.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists and has header
    file_exists = csv_path.exists()
    has_header = False
    if file_exists:
        with open(csv_path, 'r') as f:
            first_line = f.readline().strip()
            has_header = 'problem_id' in first_line
    
    mode = 'a' if append and file_exists and has_header else 'w'
    
    with open(csv_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header only if creating new file or appending without header
        if mode == 'w' or not has_header:
            writer.writerow([
                'problem_id', 'phase', 'model', 'sample_idx',
                'structural_pass', 'functional_pass', 'drc_passed', 'lvs_passed', 'opt_done',
                'pass_at_k', 'spec_at_k_structural', 'spec_at_k_full', 'spec_at_k', 'opt_eff', 'robust_pass', 'robustness_score'
            ])
        
        # Write only new results (if appending, skip already-written problems)
        written_problems = set()
        if append and file_exists and has_header:
            # Read existing problem IDs and phases (check both to avoid duplicates)
            with open(csv_path, 'r') as f_read:
                reader = csv.DictReader(f_read)
                for row in reader:
                    problem_id = row.get('problem_id', '')
                    phase = row.get('phase', '')
                    written_problems.add((problem_id, phase))
        
        for problem_result in all_results:
            problem_id = problem_result['problem_id']
            phase = problem_result.get('phase', 'unknown')
            
            # Skip if already written (when appending) - check both problem_id and phase
            if append and (problem_id, phase) in written_problems:
                logger.debug(f"Skipping already-written problem {problem_id} phase {phase}")
                continue
            
            # Get problem-level metrics (computed for all samples)
            problem_metrics = problem_result.get('metrics', {})
            
            for sample in problem_result.get('samples', []):
                sample_idx = sample.get('sample_idx', 0)
                
                writer.writerow([
                    problem_id,
                    phase,
                    model_name,
                    sample_idx,
                    sample.get('passed', False),
                    sample.get('functional_pass', False),
                    sample.get('drc_passed', False),
                    sample.get('lvs_passed', False),
                    sample.get('optimization_done', False),
                    problem_metrics.get('pass_at_k', 0.0),
                    problem_metrics.get('spec_at_k_structural', 0.0),
                    problem_metrics.get('spec_at_k_full', 0.0),
                    problem_metrics.get('spec_at_k', 0.0),
                    problem_metrics.get('avg_opt_efficiency', 0.0),
                    problem_metrics.get('robust_pass', 0.0),
                    problem_metrics.get('robustness_score', 0.0),
                ])
    
    logger.info(f"Saved aggregated metrics to: {csv_path}")
    return csv_path


def run_single_problem(
    problem: Dict,
    agent: object,
    prompt_template: str,
    pilot_validator: YAMLPilotValidator,
    drc_validator: DRCValidator,
    lvs_validator: LVSValidator,
    sax_validator: SAXValidator,
    silicon_validator: SiliconEfficiencyValidator,
    port_connection_validator: PortConnectionValidator,
    optimizer: OptimizationIntegration,
    model_name: str,
    phase: str,
    samples_per_problem: int = 5,
    enable_validation: bool = True,
    enable_optimization: bool = True
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
        'phase': phase,
        'samples': [],
        'pass_count': 0,
        'fail_count': 0,
        'metrics': {},  # Will be computed after all samples
    }
    
    for sample_idx in range(samples_per_problem):
        logger.info(f"\n--- Sample {sample_idx + 1}/{samples_per_problem} ---")
        
        sample_result = {
            'sample_idx': sample_idx + 1,
            'passed': False,
            'errors': [],
            'warnings': [],
            'yaml_valid': not enable_validation,  # Skip validation in vanilla = assume valid
            'component_built': False,
            'drc_passed': not enable_validation,  # Skip DRC in vanilla = assume pass
            'lvs_passed': not enable_validation,  # Skip LVS in vanilla = assume pass
            'optimization_done': False
        }
        
        # Step 1: Generate YAML DSL from LLM (with retry logic)
        yaml_output = None
        component = None
        build_error = None
        
        # Vanilla phase: single attempt, no retry
        # PICasso phase: up to MAX_RETRY_ATTEMPTS + 1 attempts
        max_attempts = 1 if phase == "vanilla" else (MAX_RETRY_ATTEMPTS + 1)
        
        for attempt in range(max_attempts):
            try:
                # Prepare prompt
                # For vanilla phase: no retry logic, single attempt
                # For picasso phase: retry with feedback
                if phase == "vanilla" or attempt == 0:
                    # First attempt or vanilla phase
                    system_prompt = prompt_template
                    user_query = f"Problem:\n{problem_desc}\n\nGenerate the YAML DSL netlist:"
                    logger.info("Calling LLM to generate YAML DSL...")
                else:
                    # Retry with feedback (picasso phase only)
                    system_prompt = prompt_template
                    feedback_text = ""
                    if error_msg:
                        feedback_text = f"\n\nERROR from previous attempt:\n{error_msg}\n"
                        if error_details:
                            # Include error message in details for better feedback
                            if isinstance(error_details, dict):
                                error_details['error_message'] = error_msg
                            feedback = pilot_validator.get_feedback(error_details)
                            feedback_text += f"\n{feedback}\n"
                        else:
                            feedback_text += f"\nPlease fix: {error_msg}\n"
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
                    full_prompt = f"{system_prompt}\n\n{user_query}"
                    yaml_output = agent.generate(full_prompt)
                else:
                    raise AttributeError("Agent does not have ASK_LLM, ask_llm, or generate method")
                
                # Clean YAML output (remove markdown code blocks, reasoning tags, and explanatory text)
                import re
                yaml_output = yaml_output.strip()
                
                # Remove <think> tags and content
                yaml_output = re.sub(r'<think>.*?</think>', '', yaml_output, flags=re.DOTALL)
                yaml_output = re.sub(r'<thinking>.*?</thinking>', '', yaml_output, flags=re.DOTALL)
                yaml_output = re.sub(r'<reasoning>.*?</reasoning>', '', yaml_output, flags=re.DOTALL)
                
                # Remove markdown code blocks
                if '```yaml' in yaml_output:
                    # Extract content between ```yaml and ```
                    match = re.search(r'```yaml\s*\n(.*?)```', yaml_output, re.DOTALL)
                    if match:
                        yaml_output = match.group(1).strip()
                elif '```' in yaml_output:
                    # Extract content between ``` and ```
                    match = re.search(r'```\s*\n(.*?)```', yaml_output, re.DOTALL)
                    if match:
                        yaml_output = match.group(1).strip()
                
                # Remove explanatory text before YAML (look for "instances:" as start marker)
                lines = yaml_output.split('\n')
                yaml_start_idx = None
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    # YAML typically starts with "instances:" (required first key)
                    if stripped.startswith('instances:'):
                        yaml_start_idx = i
                        break
                    # Also check for YAML document start
                    if stripped.startswith('---'):
                        yaml_start_idx = i
                        break
                
                if yaml_start_idx is not None and yaml_start_idx > 0:
                    yaml_output = '\n'.join(lines[yaml_start_idx:])
                elif yaml_start_idx is None:
                    # If no "instances:" found, try to find first valid YAML key
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        # Look for YAML key pattern (word: value, not a sentence)
                        if ':' in stripped and not stripped.startswith('#') and len(stripped.split(':')) == 2:
                            # Check if it's not a sentence (no period, reasonable length)
                            if '.' not in stripped and len(stripped) < 100:
                                yaml_start_idx = i
                                break
                    if yaml_start_idx is not None:
                        yaml_output = '\n'.join(lines[yaml_start_idx:])
                
                # Remove explanatory text after YAML (look for end of YAML structure)
                lines = yaml_output.split('\n')
                yaml_end_idx = len(lines)
                for i in range(len(lines) - 1, -1, -1):
                    line = lines[i].strip()
                    if not line or line.startswith('#'):
                        continue
                    # If we hit a line that looks like explanatory text (long sentence, no YAML structure)
                    if len(line) > 100 and ':' not in line and not line.startswith('-') and not line.startswith('  '):
                        yaml_end_idx = i
                        break
                    # If we hit valid YAML structure, stop
                    if ':' in line or line.startswith('-') or (line.startswith('  ') and ':' in line):
                        break
                
                yaml_output = '\n'.join(lines[:yaml_end_idx])
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
            if enable_validation and ENABLE_YAML_PILOT_VALIDATION:
                is_valid, error_msg, error_details = validate_yaml_dsl(yaml_output, pilot_validator)
                if not is_valid:
                    logger.warning(f"YAML pilot validation failed: {error_msg}")
                    if phase == "picasso" and attempt < max_attempts - 1:
                        # Generate detailed feedback for retry
                        if error_details:
                            error_details['error_message'] = error_msg  # Include error message in details
                        feedback_text = pilot_validator.get_feedback(error_details) if error_details else error_msg
                        user_query = f"{problem_desc}\n\nERROR FROM PREVIOUS ATTEMPT:\n{feedback_text}\n\nPlease fix the errors and regenerate the YAML."
                        continue  # Retry with feedback (picasso only)
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
                if phase == "picasso" and attempt < max_attempts - 1:
                    continue  # Retry with feedback (picasso only)
                else:
                    sample_result['errors'].append(f"Component build failed: {build_error}")
                    results['samples'].append(sample_result)
                    results['fail_count'] += 1
                    break
            
            # Success! Component built - now try auto-fixing if needed
            logger.info("✅ Component built from YAML")
            sample_result['component_built'] = True
            
            # Step 3.5: Auto-fix routing collisions
            # Check if component has routing issues by trying to get netlist
            try:
                test_netlist = component.get_netlist()
                # If successful, routing is likely OK
            except Exception as routing_error:
                # Routing collision or port connection error detected
                error_str = str(routing_error)
                if "routing collision" in error_str.lower() or "more than two connected" in error_str.lower():
                    logger.warning(f"⚠️  Routing/port connection issue detected: {routing_error}")
                    logger.info("🔄 Attempting automatic auto-fix (iterative spacing + rotation)...")
                    
                    # Try iterative fixes
                    fixed_component, fix_info = fix_routing_and_placement_iterative(
                        component=component,
                        max_iterations=3,
                        initial_spacing_multiplier=1.5,
                        spacing_increment=0.5,
                        enable_rotation=True,
                        rotation_timeout=120
                    )
                    
                    if fixed_component is not None and fix_info.get("success"):
                        logger.info(f"✅ Auto-fix successful! Method: {fix_info.get('method_used')}")
                        component = fixed_component  # Use fixed component
                        sample_result['auto_fixed'] = True
                        sample_result['fix_method'] = fix_info.get('method_used')
                    else:
                        logger.warning(f"⚠️  Auto-fix failed: {fix_info.get('errors', [])}")
                        sample_result['auto_fixed'] = False
                        # Continue with original component - will fail validation later
            
            break
        
        # If we exhausted retries, continue to next sample
        if component is None:
            # Still save YAML even if build failed
            if yaml_output:
                try:
                    save_results(
                        model_name=model_name,
                        phase=phase,
                        problem_id=problem_id,
                        sample_idx=sample_idx + 1,
                        yaml_output=yaml_output,
                        component=None,
                        metrics=sample_result.get('metrics', {})
                    )
                except:
                    pass
            continue
        
        # Step 4: DRC validation
        if enable_validation and ENABLE_DRC_CHECK:
            drc_passed, drc_report = drc_validator.validate(component)
            sample_result['drc_passed'] = drc_passed
            if not drc_passed:
                logger.warning(f"DRC validation failed: {drc_report.get('violations', 0)} violations")
                sample_result['warnings'].append(f"DRC: {drc_report.get('violations', 0)} violations")
            else:
                logger.info("✅ DRC validation passed")
        
        # Step 5: LVS validation (optional, may be slow)
        if enable_validation and ENABLE_LVS_CHECK:
            try:
                lvs_passed, lvs_report = lvs_validator.validate(component)
                sample_result['lvs_passed'] = lvs_passed
                if not lvs_passed:
                    logger.warning(f"LVS validation failed: {lvs_report.get('errors', [])}")
                    sample_result['warnings'].append(f"LVS: {lvs_report.get('errors', [])}")
                else:
                    logger.info("✅ LVS validation passed")
            except Exception as e:
                logger.warning(f"LVS validation error: {e}")
                sample_result['lvs_passed'] = False
                sample_result['warnings'].append(f"LVS validation failed: {str(e)}")
        
        # Step 5.3: Silicon efficiency validation (extra silicon detection)
        sample_result['silicon_efficient'] = True
        if enable_validation:
            try:
                silicon_efficient, silicon_report = silicon_validator.validate(component)
                sample_result['silicon_efficient'] = silicon_efficient
                sample_result['silicon_report'] = silicon_report
                if not silicon_efficient:
                    logger.warning(f"Silicon efficiency check failed: {silicon_report.get('errors', [])}")
                    if silicon_report.get('unconnected_components'):
                        logger.warning(f"  Unconnected components: {silicon_report['unconnected_components']}")
                else:
                    logger.info("✅ Silicon efficiency check passed")
            except Exception as e:
                logger.warning(f"Silicon efficiency check error: {e}")
                sample_result['silicon_efficient'] = False
        
        # Step 5.4: Port connection validation (same port connections)
        sample_result['port_connections_valid'] = True
        if enable_validation:
            try:
                port_valid, port_report = port_connection_validator.validate(component)
                sample_result['port_connections_valid'] = port_valid
                sample_result['port_connection_report'] = port_report
                if not port_valid:
                    logger.warning(f"Port connection validation failed: {port_report.get('errors', [])}")
                    if port_report.get('same_port_connections'):
                        logger.warning(f"  Same port connections: {port_report['same_port_connections']}")
                else:
                    logger.info("✅ Port connection validation passed")
            except Exception as e:
                logger.warning(f"Port connection validation error: {e}")
                sample_result['port_connections_valid'] = False
        
        # Step 5.5: SAX functional validation
        sample_result['functional_pass'] = False
        if enable_validation and ENABLE_SAX_CHECK:
            try:
                functional_pass, sax_report = sax_validator.validate(component)
                sample_result['functional_pass'] = functional_pass
                sample_result['sax_report'] = sax_report
                if functional_pass:
                    logger.info("✅ SAX functional validation passed")
                else:
                    logger.warning(f"SAX functional validation failed: {sax_report.get('errors', [])}")
            except Exception as e:
                logger.warning(f"SAX validation error: {e}")
                sample_result['functional_pass'] = False
        
        # Step 6: Optimization
        if enable_optimization:
            try:
                opt_result = optimizer.optimize_design(component, circuit_type=problem['name'])
                sample_result['optimization_done'] = opt_result.get('success', False)
                if sample_result['optimization_done']:
                    logger.info("✅ Optimization completed")
            except Exception as e:
                logger.warning(f"Optimization failed: {e}")
                sample_result['warnings'].append(f"Optimization: {str(e)}")
        
        # Calculate metrics
        sample_metrics = {
            'structural_pass': sample_result['passed'],
            'functional_pass': sample_result.get('functional_pass', False),
            'drc_passed': sample_result.get('drc_passed', False),
            'lvs_passed': sample_result.get('lvs_passed', False),
            'optimization_done': sample_result.get('optimization_done', False),
        }
        sample_result['metrics'] = sample_metrics
        
        # Save results
        try:
            saved_files = save_results(
                model_name=model_name,
                phase=phase,
                problem_id=problem_id,
                sample_idx=sample_idx + 1,
                yaml_output=yaml_output if yaml_output else "",
                component=component,
                metrics=sample_metrics
            )
            sample_result['saved_files'] = {k: str(v) for k, v in saved_files.items()}
        except Exception as e:
            logger.warning(f"Failed to save results: {e}")
        
        # Determine if sample passed
        sample_result['passed'] = (
            sample_result['yaml_valid'] and
            sample_result['component_built'] and
            (not enable_validation or sample_result['drc_passed'])
        )
        
        if sample_result['passed']:
            results['pass_count'] += 1
            logger.info(f"✅ Sample {sample_idx + 1} PASSED")
        else:
            results['fail_count'] += 1
            logger.info(f"❌ Sample {sample_idx + 1} FAILED")
        
        results['samples'].append(sample_result)
    
    # Compute problem-level metrics
    problem_metrics = compute_metrics_for_circuit(
        results['samples'],
        k=3,
        compute_robust_pass=False,
        phase=phase
    )
    results['metrics'] = problem_metrics
    
    logger.info(f"\nProblem {problem_id} Summary: {results['pass_count']}/{samples_per_problem} passed")
    logger.info(f"  Spec@k_structural: {problem_metrics.get('spec_at_k_structural', 0.0):.3f}")
    logger.info(f"  Spec@k_full: {problem_metrics.get('spec_at_k_full', 0.0):.3f}")
    
    return results


def run_test(
    problems_file: str = "Pic_set.txt",
    model_name: str = "gpt-4o",
    num_problems: Optional[int] = None,
    samples_per_problem: int = 5,
    vanilla_only: bool = False,
    picasso_only: bool = False,
    start_problem: Optional[int] = None,
    start_phase: Optional[str] = None
):
    """
    Run full test suite with two-phase testing.
    
    Args:
        problems_file: Path to problems file
        model_name: LLM model name
        num_problems: Number of problems to test (None = all)
        samples_per_problem: Number of samples per problem
        vanilla_only: Run only Phase 1 (vanilla LLM)
        picasso_only: Run only Phase 2 (PICasso framework)
        start_problem: Resume from this problem number (1-based)
        start_phase: Resume from this phase ('vanilla' or 'picasso')
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
    sax_validator = SAXValidator()
    silicon_validator = SiliconEfficiencyValidator()
    port_connection_validator = PortConnectionValidator()
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
    
    # Build prompt templates
    # Vanilla prompt (Phase 1 - no injection, no pilot)
    vanilla_prompt_template = VANILLA_PROMPT_TEMPLATE.format(system_prompt=SYSTEM_PROMPT)
    
    # PICasso prompt (Phase 2 - with injection and pilot)
    picasso_prompt_template = YAML_DSL_PROMPT_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        component_injection=component_injection,
        pilot_prompt=base_pilot_prompt
    )
    
    all_results = []
    
    # Check for existing results to enable automatic continuation
    completed_problems = get_completed_problems(model_name)
    logger.info(f"📊 Existing results: {len(completed_problems['vanilla'])} vanilla, {len(completed_problems['picasso'])} picasso problems completed")
    
    # Handle resume functionality
    start_idx = 0
    if start_problem is not None:
        start_idx = max(0, start_problem - 1)  # Convert to 0-based index
        logger.info(f"🔄 Resuming from Problem {start_problem} (index {start_idx})")
        problems = problems[start_idx:]
    
    # Phase 1: Vanilla LLM (if not picasso_only)
    if not picasso_only and (start_phase is None or start_phase == "vanilla"):
        logger.info("\n" + "="*70)
        logger.info("PHASE 1: VANILLA LLM (Baseline)")
        logger.info("="*70)
        
        vanilla_results = []
        for problem in problems:
            problem_id = problem.get('id', '')
            
            # Skip if already completed (unless explicitly resuming)
            if start_problem is None and problem_id in completed_problems['vanilla']:
                logger.info(f"⏭️  Skipping Problem {problem_id} (vanilla) - already completed")
                continue
            
            result = run_single_problem(
                problem=problem,
                agent=agent,
                prompt_template=vanilla_prompt_template,
                pilot_validator=pilot_validator,
                drc_validator=drc_validator,
                lvs_validator=lvs_validator,
                sax_validator=sax_validator,
                silicon_validator=silicon_validator,
                port_connection_validator=port_connection_validator,
                optimizer=optimizer,
                model_name=model_name,
                phase="vanilla",
                samples_per_problem=samples_per_problem,
                enable_validation=False,  # No validation in vanilla
                enable_optimization=False  # No optimization in vanilla
            )
            vanilla_results.append(result)
            all_results.append(result)  # Add immediately
            
            # Update CSV after each problem (incremental save)
            try:
                csv_path = save_aggregated_metrics(model_name, [result], append=True)
                logger.debug(f"Updated metrics CSV after problem {result['problem_id']}")
            except Exception as e:
                logger.warning(f"Failed to update metrics CSV: {e}")
        
        logger.info(f"\nPhase 1 Summary: {sum(r['pass_count'] for r in vanilla_results)}/{len(vanilla_results) * samples_per_problem} passed")
    
    # Phase 2: PICasso Framework (if not vanilla_only)
    if not vanilla_only and (start_phase is None or start_phase == "picasso"):
        logger.info("\n" + "="*70)
        logger.info("PHASE 2: PICASSO FRAMEWORK")
        logger.info("="*70)
        
        picasso_results = []
        for problem in problems:
            problem_id = problem.get('id', '')
            
            # Skip if already completed (unless explicitly resuming)
            if start_problem is None and problem_id in completed_problems['picasso']:
                logger.info(f"⏭️  Skipping Problem {problem_id} (picasso) - already completed")
                continue
            
            result = run_single_problem(
                problem=problem,
                agent=agent,
                prompt_template=picasso_prompt_template,
                pilot_validator=pilot_validator,
                drc_validator=drc_validator,
                lvs_validator=lvs_validator,
                sax_validator=sax_validator,
                silicon_validator=silicon_validator,
                port_connection_validator=port_connection_validator,
                optimizer=optimizer,
                model_name=model_name,
                phase="picasso",
                samples_per_problem=samples_per_problem,
                enable_validation=True,  # Full validation in PICasso
                enable_optimization=True  # Full optimization in PICasso
            )
            picasso_results.append(result)
            all_results.append(result)  # Add immediately
            
            # Update CSV after each problem (incremental save)
            try:
                csv_path = save_aggregated_metrics(model_name, [result], append=True)
                logger.debug(f"Updated metrics CSV after problem {result['problem_id']}")
            except Exception as e:
                logger.warning(f"Failed to update metrics CSV: {e}")
        
        logger.info(f"\nPhase 2 Summary: {sum(r['pass_count'] for r in picasso_results)}/{len(picasso_results) * samples_per_problem} passed")
    
    # Final save of aggregated metrics CSV (ensures completeness)
    # Use append=True to preserve existing results from previous runs
    try:
        csv_path = save_aggregated_metrics(model_name, all_results, append=True)
        logger.info(f"Saved final aggregated metrics to: {csv_path}")
    except Exception as e:
        logger.warning(f"Failed to save final aggregated metrics: {e}")
    
    # Save JSON results
    output_dir = Path(__file__).parent / "output" / "test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"results_{model_name}_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"\nResults saved to: {results_file}")
    
    # Print summary with metrics
    total_passed = sum(r['pass_count'] for r in all_results)
    total_samples = sum(len(r['samples']) for r in all_results)
    pass_rate = (total_passed / total_samples * 100) if total_samples > 0 else 0
    
    # Compute overall metrics
    vanilla_results_list = [r for r in all_results if r.get('phase') == 'vanilla']
    picasso_results_list = [r for r in all_results if r.get('phase') == 'picasso']
    
    logger.info("\n" + "="*70)
    logger.info("FINAL SUMMARY")
    logger.info("="*70)
    logger.info(f"Total problems: {len(problems)}")
    logger.info(f"Total samples: {total_samples}")
    logger.info(f"Total passed: {total_passed}")
    logger.info(f"Pass rate: {pass_rate:.1f}%")
    
    if vanilla_results_list:
        # Aggregate vanilla metrics
        all_vanilla_samples = []
        for r in vanilla_results_list:
            all_vanilla_samples.extend(r.get('samples', []))
        if all_vanilla_samples:
            vanilla_metrics = compute_metrics_for_circuit(all_vanilla_samples, k=3, phase="vanilla")
            logger.info(f"\nPhase 1 (Vanilla) Metrics:")
            logger.info(f"  Spec@k_structural: {vanilla_metrics.get('spec_at_k_structural', 0.0):.3f}")
            logger.info(f"  Spec@k_full: {vanilla_metrics.get('spec_at_k_full', 0.0):.3f}")
    
    if picasso_results_list:
        # Aggregate picasso metrics
        all_picasso_samples = []
        for r in picasso_results_list:
            all_picasso_samples.extend(r.get('samples', []))
        if all_picasso_samples:
            picasso_metrics = compute_metrics_for_circuit(all_picasso_samples, k=3, phase="picasso")
            logger.info(f"\nPhase 2 (PICasso) Metrics:")
            logger.info(f"  Spec@k_structural: {picasso_metrics.get('spec_at_k_structural', 0.0):.3f}")
            logger.info(f"  Spec@k_full: {picasso_metrics.get('spec_at_k_full', 0.0):.3f}")
            logger.info(f"  Avg OptEff: {picasso_metrics.get('avg_opt_efficiency', 0.0):.3f}")
            logger.info(f"  Robustness Score: {picasso_metrics.get('robustness_score', 0.0):.3f}")
    
    logger.info("="*70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test gd_picasso framework with LLM')
    parser.add_argument('--model', type=str, default='gpt-4o', help='Model name (gpt-4o, gpt-4o-mini, etc.)')
    parser.add_argument('--problems', type=str, default='gd_picasso/problems_parsed.txt', help='Problems file path')
    parser.add_argument('--num-problems', type=int, default=None, help='Number of problems to test (None = all)')
    parser.add_argument('--samples', type=int, default=5, help='Samples per problem')
    parser.add_argument('--vanilla-only', action='store_true', help='Run only Phase 1 (vanilla LLM)')
    parser.add_argument('--picasso-only', action='store_true', help='Run only Phase 2 (PICasso framework)')
    parser.add_argument('--start-problem', type=int, default=None, help='Resume from this problem number (1-based)')
    parser.add_argument('--start-phase', type=str, default=None, choices=['vanilla', 'picasso'], help='Resume from this phase')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.vanilla_only and args.picasso_only:
        logger.error("Cannot specify both --vanilla-only and --picasso-only")
        sys.exit(1)
    
    run_test(
        problems_file=args.problems,
        model_name=args.model,
        num_problems=args.num_problems,
        samples_per_problem=args.samples,
        vanilla_only=args.vanilla_only,
        picasso_only=args.picasso_only,
        start_problem=args.start_problem,
        start_phase=args.start_phase
    )

