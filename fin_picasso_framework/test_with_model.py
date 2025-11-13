"""
Test Framework with DeepSeek-R1 or Kimi2

Runs a small test set through the framework with the specified model.
Monitors progress and saves results.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

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

from fin_picasso_framework.gen_data_validated import (
    load_problems,
    run_validated_generation
)
from fin_picasso_framework.config import (
    SAMPLES_PER_PROBLEM,
    MAX_RETRY_ATTEMPTS
)

# Try to import HF agent
try:
    from hf_inference_workflow.hf_api_client import HFInferenceAgent
    HF_AGENT_AVAILABLE = True
except ImportError:
    HF_AGENT_AVAILABLE = False
    print("WARNING: HFInferenceAgent not available")

# Try to import OpenAI agent
try:
    from hf_inference_workflow.openai_api_client import OpenAIInferenceAgent
    OPENAI_AGENT_AVAILABLE = True
except ImportError:
    OPENAI_AGENT_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('framework_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_model_options():
    """Get available model options."""
    models = {
        'deepseek_r1': {
            'type': 'hf_api',
            'name': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B',
            'description': 'DeepSeek-R1 via HuggingFace API'
        },
        'deepseek_r1_local': {
            'type': 'hf_local',
            'name': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B',
            'description': 'DeepSeek-R1 via Local GPU'
        },
        'kimi2': {
            'type': 'hf_api',
            'name': 'moonshotai/Kimi-K2-Thinking',  # Kimi2 via HuggingFace API (base name, provider handled separately)
            'description': 'Kimi2 Thinking via HuggingFace API',
            'api_key_env': 'HF_TOKEN',  # Use HF_TOKEN environment variable
            'provider': 'novita'  # Provider tag for Kimi2
        },
        'deepseek_r1_api': {
            'type': 'openai',
            'name': 'deepseek-chat',  # DeepSeek-R1 via DeepSeek API
            'description': 'DeepSeek-R1 via DeepSeek API',
            'api_base': 'https://api.deepseek.com/v1'
        },
        'gpt4o_mini': {
            'type': 'openai',
            'name': 'gpt-4o-mini',
            'description': 'GPT-4o-mini via OpenAI API'
        }
    }
    return models


def create_agent(model_key: str) -> Optional[object]:
    """
    Create inference agent for specified model.
    
    Args:
        model_key: Model key ('deepseek_r1', 'kimi2', etc.)
        
    Returns:
        Agent instance or None
    """
    models = get_model_options()
    
    if model_key not in models:
        logger.error(f"Unknown model key: {model_key}")
        logger.info(f"Available models: {list(models.keys())}")
        return None
    
    model_info = models[model_key]
    logger.info(f"Creating agent for: {model_info['description']}")
    
    if model_info['type'] == 'hf_api':
        if not HF_AGENT_AVAILABLE:
            logger.error("HFInferenceAgent not available")
            return None
        try:
            # Handle custom API key for Kimi2
            api_key_env = model_info.get('api_key_env')
            import os
            if api_key_env:
                # Try the specified env var first, then fallback to HF_API_TOKEN
                api_key = os.environ.get(api_key_env) or os.environ.get('HF_API_TOKEN')
                if api_key:
                    # Create agent with custom token and provider if specified
                    provider = model_info.get('provider')
                    if provider:
                        agent = HFInferenceAgent(model=model_info['name'], api_token=api_key, provider=provider)
                    else:
                        agent = HFInferenceAgent(model=model_info['name'], api_token=api_key)
                    logger.info(f"Using API token from {api_key_env} or HF_API_TOKEN")
                    if provider:
                        logger.info(f"Using provider: {provider}")
                else:
                    logger.error(f"Environment variable {api_key_env} or HF_API_TOKEN not set")
                    logger.error(f"Available env vars: {[k for k in os.environ.keys() if 'HF' in k or 'TOKEN' in k]}")
                    return None
            else:
                # For other models, try HF_API_TOKEN
                api_key = os.environ.get('HF_API_TOKEN')
                if api_key:
                    agent = HFInferenceAgent(model=model_info['name'], api_token=api_key)
                else:
                    agent = HFInferenceAgent(model=model_info['name'])
            logger.info(f"✅ Created HF API agent with model: {model_info['name']}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create HF API agent: {e}")
            return None
    
    elif model_info['type'] == 'hf_local':
        # For local GPU, we'd need to use hf_models/hf_agent.py
        logger.warning("Local GPU models require different setup - using API instead")
        if not HF_AGENT_AVAILABLE:
            logger.error("HFInferenceAgent not available")
            return None
        try:
            agent = HFInferenceAgent(model=model_info['name'])
            logger.info(f"✅ Created HF API agent (fallback) with model: {model_info['name']}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create HF API agent: {e}")
            return None
    
    elif model_info['type'] == 'openai':
        if not OPENAI_AGENT_AVAILABLE:
            logger.error("OpenAIInferenceAgent not available")
            return None
        try:
            import os
            # Check environment variable first, then fallback to config
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                from hf_inference_workflow.config import OPENAI_API_KEY as config_key
                api_key = config_key
                if api_key and api_key != "ENTER_YOUR_OPENAI_KEY_HERE":
                    logger.info("Using API key from config.py")
                else:
                    logger.error("No OPENAI_API_KEY found in environment or config.py")
                    return None
            else:
                logger.info("Using OPENAI_API_KEY from environment variable")
            
            # Handle custom API base for DeepSeek or Kimi
            api_base = model_info.get('api_base')
            if api_base:
                # For custom API bases, we might need to modify the agent
                # For now, try with standard OpenAI agent
                logger.info(f"Using custom API base: {api_base}")
                agent = OpenAIInferenceAgent(api_key=api_key, model=model_info['name'])
            else:
                agent = OpenAIInferenceAgent(api_key=api_key, model=model_info['name'])
            logger.info(f"✅ Created OpenAI agent with model: {model_info['name']}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create OpenAI agent: {e}")
            return None
    
    return None


def run_test(model_key: str = 'deepseek_r1', num_problems = None, samples_per_problem: int = 1, vanilla_mode: bool = False):
    """
    Run framework test with specified model.
    
    Args:
        model_key: Model to use ('deepseek_r1', 'kimi2', etc.)
        num_problems: Number of problems to test (default: 2)
        samples_per_problem: Samples per problem (default: 1 for quick test)
    """
    logger.info("=" * 70)
    logger.info("PICASSO FRAMEWORK TEST WITH MODEL")
    logger.info("=" * 70)
    logger.info(f"Model: {model_key}")
    logger.info(f"Problems: {num_problems}")
    logger.info(f"Samples per problem: {samples_per_problem}")
    logger.info("=" * 70)
    
    # Create agent
    logger.info("\nStep 1: Creating inference agent...")
    agent = create_agent(model_key)
    if agent is None:
        logger.error("Failed to create agent. Exiting.")
        return
    
    # Load problems
    logger.info("\nStep 2: Loading problems...")
    
    # Check if num_problems is a file path (string) or number
    if isinstance(num_problems, str) and Path(num_problems).exists():
        # It's a file path
        problems_file = Path(num_problems)
        logger.info(f"Loading problems from specified file: {problems_file}")
    elif isinstance(num_problems, str):
        # Try to find file in parent directory
        problems_file = Path(__file__).parent.parent / num_problems
        if not problems_file.exists():
            logger.error(f"Problems file not found: {num_problems}")
            return
        logger.info(f"Loading problems from: {problems_file}")
    else:
        # Use default file search order
        problems_file = Path(__file__).parent.parent / "Pic_set_enhanced.txt"
        if not problems_file.exists():
            problems_file = Path(__file__).parent.parent / "Pic_set.txt"
        if not problems_file.exists():
            problems_file = Path(__file__).parent.parent / "test_problems.txt"
        if not problems_file.exists():
            problems_file = Path(__file__).parent.parent / "problems.txt"
        
        if not problems_file.exists():
            logger.error(f"Problems file not found: {problems_file}")
            return
        logger.info(f"Loading problems from default file: {problems_file}")
    
    problems = load_problems(str(problems_file))
    logger.info(f"Loaded {len(problems)} problems")
    
    # Always test with 4 problems for debugging (as requested)
    TEST_WITH_4_PROBLEMS = True  # Set to True to always test with 4 problems
    
    if TEST_WITH_4_PROBLEMS:
        test_problems = problems[:4] if len(problems) >= 4 else problems
        logger.info(f"🧪 DEBUG MODE: Testing with {len(test_problems)} problems (limited to 4 for debugging)")
    elif isinstance(num_problems, str) and num_problems.isdigit():
        num_problems = int(num_problems)
        test_problems = problems[:num_problems]
        logger.info(f"Testing with {len(test_problems)} problems (limited from {len(problems)} total)")
    elif isinstance(num_problems, int) and num_problems is not None:
        test_problems = problems[:num_problems]
        logger.info(f"Testing with {len(test_problems)} problems (limited from {len(problems)} total)")
    else:
        test_problems = problems
        logger.info(f"Testing with ALL {len(test_problems)} problems")
    
    # Load prompt template
    logger.info("\nStep 3: Loading prompt template...")
    try:
        from hf_inference_workflow.config import PYTHON_PROMPT_TEMPLATE
        prompt_template = PYTHON_PROMPT_TEMPLATE
        logger.info("✅ Loaded prompt template")
    except ImportError:
        logger.warning("Could not load prompt template, using default")
        prompt_template = "You are a professional Photonic Integrated Circuit (PIC) designer."
    
    # Override samples per problem for quick test
    import fin_picasso_framework.config as config
    original_samples = config.SAMPLES_PER_PROBLEM
    config.SAMPLES_PER_PROBLEM = samples_per_problem
    
    # Configure vanilla mode if requested
    if vanilla_mode:
        logger.info("=" * 70)
        logger.info("VANILLA MODE ENABLED - Disabling framework features")
        logger.info("=" * 70)
        config.ENABLE_AUTO_CORRECTION = False
        config.ENABLE_EARLY_NETLIST_VALIDATION = False
        config.ENABLE_DYNAMIC_PILOT_UPDATES = False
        logger.info("  - Auto-correction: DISABLED")
        logger.info("  - YAML validation: DISABLED")
        logger.info("  - Dynamic pilot updates: DISABLED")
        logger.info("=" * 70)
    
    try:
        # Run generation
        logger.info("\nStep 4: Running framework generation...")
        logger.info("=" * 70)
        
        output_csv = f"framework_test_{model_key}_{'vanilla' if vanilla_mode else 'framework'}_{len(test_problems)}problems.csv"
        run_validated_generation(
            agent=agent,
            problems=test_problems,
            prompt_template=prompt_template,
            csv_name=output_csv
        )
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Results saved to: {output_csv}")
        logger.info(f"Check logs in: framework_test.log")
        logger.info(f"Check checkpoints in: fin_picasso_framework/output/benchmark_results/checkpoints/")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
    finally:
        # Restore original samples
        config.SAMPLES_PER_PROBLEM = original_samples


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test PICasso framework with specified model")
    parser.add_argument(
        '--model',
        type=str,
        default='kimi2',
        choices=['deepseek_r1', 'deepseek_r1_local', 'kimi2', 'gpt4o_mini'],
        help='Model to use (default: kimi2)'
    )
    parser.add_argument(
        '--problems',
        type=str,
        default=None,
        help='Number of problems to test (int) OR path to problems file (str) (default: None = all problems from default file)'
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=3,
        help='Samples per problem (default: 3 for pass@3)'
    )
    parser.add_argument(
        '--vanilla',
        action='store_true',
        help='Run in vanilla mode (no framework features, no auto-correction)'
    )
    
    args = parser.parse_args()
    
    # Show available models
    models = get_model_options()
    logger.info("Available models:")
    for key, info in models.items():
        logger.info(f"  {key}: {info['description']}")
    logger.info("")
    
    # Run test
    run_test(
        model_key=args.model,
        num_problems=args.problems,
        samples_per_problem=args.samples,
        vanilla_mode=getattr(args, 'vanilla', False)
    )


if __name__ == "__main__":
    main()

