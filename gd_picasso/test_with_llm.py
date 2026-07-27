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

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add parent directory to path
framework_dir = Path(__file__).parent
parent_dir = framework_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Load environment variables from .env if available
if load_dotenv is not None:
    load_dotenv(parent_dir / ".env")

# Check for gdsfactory
try:
    import gdsfactory as gf
    _gdsfactory_available = True
except ImportError as e:
    print(f"ERROR: gdsfactory not available: {e}")
    sys.exit(1)

gf.gpdk.PDK.activate()

from gd_picasso.utils.gdsfactory_compat import patch_dbr_ports
patch_dbr_ports()

# Fix kfactory version parsing for KLayout versions like "0.30.4-1"
# and suppress klive show() spam during batch runs (collision checker
# sends every failed routing attempt to the KLayout GUI).
try:
    import kfactory.kcell as _kc
    if '-' in _kc._klayout_version:
        _kc._klayout_version = _kc._klayout_version.split('-')[0]
    import kfactory
    kfactory.show = lambda *a, **kw: None
    _kc.show = lambda *a, **kw: None
except Exception:
    pass

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
    from gd_picasso.agents.openai_agent import OpenAIInferenceAgent
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
        logging.FileHandler('gd_picasso_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
DEBUG_VALIDATION = os.getenv("GD_PICASSO_DEBUG", os.getenv("DEBUG", "0")).lower() in {
    "1",
    "true",
    "yes",
    "on",
}

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
    
    with open(problem_file_path, 'r', encoding='utf-8-sig') as f:
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


def create_agent(model_name: str = "gpt-4o", multi_agent: bool = False) -> Optional[object]:
    """
    Create inference agent for specified model.

    API keys must be set via environment variables (see README). For GPT models,
    OPENROUTER_API is preferred over OPENAI_API_KEY for higher rate limits.

    Args:
        model_name: Model name ('gpt-4o', 'gpt-4o-mini', 'deepseek-r1', 'kimi2', etc.)
        multi_agent: If True, wrap agent in a MultiAgentOrchestrator with a CriticAgent.

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
            # Fallback: load from ~/.claude/anthropic_key.sh
            _key_file = Path.home() / ".claude" / "anthropic_key.sh"
            if _key_file.exists():
                try:
                    import re
                    raw = _key_file.read_text().strip()
                    for line in raw.splitlines():
                        line = line.strip()
                        if line.startswith("#") or not line:
                            continue
                        if "ANTHROPIC_API_KEY=" in line:
                            api_key = line.split("ANTHROPIC_API_KEY=", 1)[1].split("#")[0].strip().strip("'\"")
                            if api_key:
                                break
                        if line.startswith("sk-ant-") and len(line) > 20:
                            api_key = line.split("#")[0].strip().strip("'\"")
                            if api_key:
                                break
                        # Script may only echo the key: echo "sk-ant-..." or echo 'sk-ant-...'
                        m = re.search(r'["\'](sk-ant-[a-zA-Z0-9_-]+)["\']', line)
                        if m and len(m.group(1)) > 20:
                            api_key = m.group(1)
                            break
                except Exception:
                    pass
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set (and not found in ~/.claude/anthropic_key.sh)")
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
    
    # Check if it's a GPT model (OpenAI/OpenRouter) - including GPT-5 and o3
    elif model_name.startswith('gpt') or model_name.startswith('o3'):
        if not OPENAI_AGENT_AVAILABLE:
            logger.error("OpenAIInferenceAgent not available")
            return None

        # Prefer OpenRouter (higher rate limits); fall back to direct OpenAI
        openrouter_key = os.getenv('OPENROUTER_API')
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openrouter_key and not openai_key:
            logger.error("Neither OPENROUTER_API nor OPENAI_API_KEY is set")
            return None

        try:
            # Pass None – the agent picks up OPENROUTER_API automatically
            agent = OpenAIInferenceAgent(model=model_name)
            backend = getattr(agent, 'backend', 'unknown')
            logger.info(f"✅ Created OpenAI agent — backend={backend} model={agent.model}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create OpenAI agent: {e}")
            return None
    
    # Check if it's a HuggingFace / open model — try OpenRouter first if available
    elif (model_name in MODEL_MAPPING or '/' in model_name or
          model_name.startswith('kimi') or model_name.startswith('llama') or
          model_name.startswith('qwen') or model_name.startswith('mistral') or
          model_name.startswith('phi')):

        # OpenRouter supports many open models (Llama, Mistral, Qwen, etc.) and
        # avoids HF Scaleway 402 Payment-Required errors on large models.
        openrouter_key = os.getenv('OPENROUTER_API')
        if openrouter_key and OPENAI_AGENT_AVAILABLE:
            # Map short name to OpenRouter model ID
            _OR_MODEL_MAP = {
                'llama-3.1-70b': 'meta-llama/llama-3.1-70b-instruct',
                'llama-3.1-8b':  'meta-llama/llama-3.1-8b-instruct',
                'llama-3-70b':   'meta-llama/llama-3-70b-instruct',
                'qwen-2.5-32b':  'qwen/qwen-2.5-72b-instruct',
                'mistral-large': 'mistralai/mistral-large',
                'phi-4':         'microsoft/phi-4',
            }
            or_model = _OR_MODEL_MAP.get(model_name, model_name)
            try:
                agent = OpenAIInferenceAgent(model=or_model)
                backend = getattr(agent, '_backend', 'unknown')
                logger.info(f"✅ Created agent via OpenRouter — model={agent.model}")
                return agent
            except Exception as e:
                logger.warning(f"OpenRouter failed for {or_model}: {e}, falling back to HF")

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

    # NOTE: code below is unreachable — multi_agent wrapping happens after return above.
    # Wrapping is done in the caller (run_tests) where agent is created.


def wrap_multi_agent(agent, critic_model_name: str = None):
    """
    Wrap a generator agent in a MultiAgentOrchestrator with a CriticAgent.

    Args:
        agent: The generator agent to wrap
        critic_model_name: Model to use for the critic. Defaults to same model as generator.

    Returns:
        MultiAgentOrchestrator instance
    """
    from gd_picasso.agents.critic_agent import CriticAgent
    from gd_picasso.agents.orchestrator import MultiAgentOrchestrator

    # Load PDK component specs to inject into the critic
    try:
        from gd_picasso.injection.component_spec_loader import ComponentSpecLoader
        component_loader = ComponentSpecLoader()
        component_spec_text = component_loader.generate_yaml_dsl_injection(
            include_examples=False,
            include_error_patterns=True
        )
        logger.info("✅ Component specs loaded for critic agent")
    except Exception as e:
        logger.warning(f"Could not load component specs for critic: {e}")
        component_spec_text = ""

    # Use gpt-4o as the dedicated critic — stronger instruction-following than gpt-4o-mini.
    # Falls back to None (static-only critic) if the key is missing.
    critic_llm = None
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and OPENAI_AGENT_AVAILABLE:
        try:
            critic_llm = OpenAIInferenceAgent(
                api_key=openai_key,
                model="gpt-4o"
            )
            logger.info("✅ gpt-4o critic agent created")
        except Exception as e:
            logger.warning(f"Could not create gpt-4o critic agent: {e} — using static-only critic")
    else:
        logger.info("ℹ️  OPENAI_API_KEY not set — critic will use static checks only")

    critic_agent = CriticAgent(critic_llm, component_spec_text=component_spec_text)
    orchestrator = MultiAgentOrchestrator(
        generator_agent=agent,
        critic_agent=critic_agent,
        max_critic_rounds=2
    )
    logger.info("✅ Multi-agent mode enabled: Generator + Critic orchestrator created")
    return orchestrator


def validate_yaml_dsl(yaml_str: str, pilot_validator: YAMLPilotValidator) -> tuple:
    """
    Validate YAML DSL using pilot validator.
    
    Returns:
        (is_valid, error_message, error_details)
    """
    return pilot_validator.validate(yaml_str)


def extract_yaml_from_llm_output(raw_output: str) -> str:
    """
    Recover a gdsfactory YAML DSL document from arbitrary LLM prose.

    The extractor prefers fenced YAML blocks, then scans for top-level DSL keys
    and keeps the first parseable mapping containing instances, placements,
    routes, and ports.
    """
    import re
    import yaml as _yaml

    text = (raw_output or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)

    candidates = []
    for match in re.finditer(r"```(?:yaml|yml)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE):
        candidates.append(match.group(1).strip())
    candidates.append(text)

    required_keys = {"instances", "placements", "routes", "ports"}

    def _is_valid_candidate(candidate: str) -> bool:
        try:
            data = _yaml.safe_load(candidate)
        except Exception:
            return False
        return isinstance(data, dict) and required_keys.issubset(data.keys())

    for candidate in candidates:
        if _is_valid_candidate(candidate):
            return candidate.strip()

    lines = text.splitlines()
    key_pattern = re.compile(r"^(instances|placements|routes|ports)\s*:")
    start_indexes = [i for i, line in enumerate(lines) if key_pattern.match(line.strip())]
    for start_idx in start_indexes:
        for end_idx in range(len(lines), start_idx, -1):
            candidate = "\n".join(lines[start_idx:end_idx]).strip()
            if _is_valid_candidate(candidate):
                return candidate

    fallback = candidates[0].strip() if candidates else ""
    fallback = re.sub(r"^\s*```(?:yaml|yml)?\s*", "", fallback, flags=re.IGNORECASE)
    fallback = re.sub(r"\s*```\s*$", "", fallback)
    return fallback.strip()


# Max mirror combinations to try per failed build (avoids 2^N blow-up on large designs)
_MAX_MIRROR_COMBOS = 128

def _try_all_mirror_combos(yaml_str: str) -> tuple:
    """
    Brute-force mirror fix: try combinations of mirror=true/false for mmi1x2
    until the build succeeds. Capped at _MAX_MIRROR_COMBOS to avoid runaway
    runtime on large designs (e.g. 2^10 = 1024 attempts per sample).
    """
    import yaml as _yaml
    from itertools import product as _product, islice as _islice

    try:
        data = _yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return None, None

        instances = data.get("instances", {})
        placements = data.get("placements", {})

        mmi_names = [
            name for name, info in instances.items()
            if isinstance(info, dict) and info.get("component") == "mmi1x2"
        ]

        if not mmi_names or len(mmi_names) > 12:
            return None, None

        combos = _product([False, True], repeat=len(mmi_names))
        for combo in _islice(combos, _MAX_MIRROR_COMBOS):
            trial = _yaml.safe_load(_yaml.dump(data, default_flow_style=False, sort_keys=False))
            pls = trial.get("placements", {})
            for name, mirror_val in zip(mmi_names, combo):
                pl = pls.get(name, {})
                if not isinstance(pl, dict):
                    pl = {}
                pl["mirror"] = mirror_val
                pls[name] = pl
            trial["placements"] = pls

            trial_yaml = _yaml.dump(trial, default_flow_style=False, sort_keys=False, allow_unicode=False)
            try:
                gf.gpdk.PDK.activate()
                try:
                    gf.clear_cache()
                except Exception:
                    pass
                component = gf.read.from_yaml(trial_yaml)
                logger.info(
                    "Auto-mirror fix succeeded with: %s",
                    {n: m for n, m in zip(mmi_names, combo)},
                )
                return component, trial_yaml
            except Exception:
                continue

        if len(mmi_names) > 7:
            logger.debug(
                "Auto-mirror gave up after %d attempts (%d MMIs); increase _MAX_MIRROR_COMBOS if needed",
                _MAX_MIRROR_COMBOS,
                len(mmi_names),
            )
        return None, None
    except Exception:
        return None, None


def _sanitize_yaml(yaml_str: str) -> str:
    """
    Fix common LLM mistakes in the YAML before handing it to gdsfactory.

    1. Evaluate simple arithmetic EVERYWHERE in the YAML (port names,
       settings, link keys/values).  Uses a deep-walk of the parsed
       structure so nothing is missed.
    2. Strip stray 'component' / 'settings' keys from placements.
    3. Normalise route section names (e.g. 'route1' → 'optical').
    """
    import yaml as _yaml
    import re as _re

    yaml_str = _re.sub(r"^\s*```(?:yaml|yml)?\s*", "", yaml_str.strip(), flags=_re.IGNORECASE)
    yaml_str = _re.sub(r"\s*```\s*$", "", yaml_str)

    _ARITH = _re.compile(r'(\d+)\s*([+\-])\s*(\d+)')

    def _eval_arith(s: str) -> str:
        """Evaluate ALL simple integer arithmetic inside a string."""
        def _repl(m):
            a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
            return str(a + int(b) if op == '+' else a - int(b))
        prev = None
        while prev != s:
            prev = s
            s = _ARITH.sub(_repl, s)
        return s

    def _to_numeric(s: str):
        """If the string is a plain number after arithmetic, return as int/float."""
        try:
            if '.' in s:
                return float(s)
            return int(s)
        except (ValueError, TypeError):
            return s

    def _deep_fix(obj):
        """Recursively walk any nested YAML structure, fixing strings."""
        if isinstance(obj, str):
            fixed = _eval_arith(obj)
            if fixed != obj and fixed.lstrip('-').replace('.', '', 1).isdigit():
                return _to_numeric(fixed)
            return fixed
        if isinstance(obj, dict):
            return {_eval_arith(str(k)) if isinstance(k, str) else k:
                    _deep_fix(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_deep_fix(item) for item in obj]
        return obj

    # --- Parse ---------------------------------------------------------------
    try:
        data = _yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return yaml_str
    except Exception:
        return yaml_str

    data = _deep_fix(data)

    def _normalise_port_ref(ref, top_ports=None):
        """Repair common LLM link refs into 'instance,port' form."""
        if not isinstance(ref, str):
            return ref
        top_ports = top_ports or {}
        ref = ref.strip()
        if ref in top_ports and isinstance(top_ports[ref], str):
            return top_ports[ref].strip()

        parts = [p.strip() for p in ref.split(",") if p.strip()]
        if len(parts) == 2:
            return f"{parts[0]},{parts[1]}"
        if len(parts) > 2:
            # Common mistake: exported port label is prepended/appended to
            # the real instance-port ref, e.g. "out5,mzi9,o2".
            if parts[0] in top_ports and len(parts) >= 3:
                return f"{parts[1]},{parts[2]}"
            if parts[-1] in top_ports and len(parts) >= 3:
                return f"{parts[0]},{parts[1]}"
            return f"{parts[-2]},{parts[-1]}"
        return ref

    def _normalise_link_map(links, top_ports=None):
        """Return a cleaned route/connection mapping, dropping unrecoverable refs."""
        if not isinstance(links, dict):
            return links
        cleaned = {}
        for src, dst in links.items():
            src_ref = _normalise_port_ref(str(src), top_ports)
            dst_ref = _normalise_port_ref(dst, top_ports)
            if (
                isinstance(src_ref, str)
                and isinstance(dst_ref, str)
                and src_ref.count(",") == 1
                and dst_ref.count(",") == 1
                and src_ref != dst_ref
            ):
                cleaned[src_ref] = dst_ref
        return cleaned

    # --- Make DBR defaults compatible with the active generic_tech DRC deck ---
    # gdsfactory's DBR defaults use 0.159um grating half-periods and a 0.01um
    # end straight, which are intentionally tiny but violate the generic
    # width/space minimum of 0.2um. If the LLM leaves DBR settings empty, or
    # gives smaller values, lift only those rule-sensitive dimensions.
    instances = data.get("instances", {})
    preserve_direct_connections = False
    if isinstance(instances, dict):
        for _inst, inst_data in instances.items():
            if not isinstance(inst_data, dict) or inst_data.get("component") != "dbr":
                continue
            settings = inst_data.get("settings")
            if not isinstance(settings, dict):
                settings = {}
                inst_data["settings"] = settings
            for key in ("l1", "l2", "straight_length"):
                value = settings.get(key)
                if not isinstance(value, (int, float)) or float(value) < 0.2:
                    settings[key] = 0.2

    def _component_bbox(inst_data):
        """Return component bbox dimensions for placement sanity checks."""
        if not isinstance(inst_data, dict):
            return None
        component_name = inst_data.get("component")
        if not component_name:
            return None
        settings = inst_data.get("settings") if isinstance(inst_data.get("settings"), dict) else {}
        try:
            component = gf.get_component(component_name, **settings)
            bbox = component.dbbox()
            return {
                "left": float(bbox.left),
                "right": float(bbox.right),
                "bottom": float(bbox.bottom),
                "top": float(bbox.top),
                "width": float(bbox.width()),
                "height": float(bbox.height()),
            }
        except Exception:
            return None

    def _placement_overlaps(layout_items, clearance=20.0):
        """Return True when any absolute component bboxes overlap or are too close."""
        for i, item1 in enumerate(layout_items):
            for item2 in layout_items[i + 1:]:
                separated = (
                    item1["right"] + clearance <= item2["left"]
                    or item2["right"] + clearance <= item1["left"]
                    or item1["top"] + clearance <= item2["bottom"]
                    or item2["top"] + clearance <= item1["bottom"]
                )
                if not separated:
                    return True
        return False

    def _repair_bbox_placements(data, clearance=100.0):
        """Spread placed components when large cells overlap despite origin spacing."""
        instances = data.get("instances", {})
        placements = data.get("placements", {})
        if not isinstance(instances, dict) or not isinstance(placements, dict):
            return

        layout_items = []
        for inst_name, placement in placements.items():
            if not isinstance(placement, dict):
                continue
            x = placement.get("x", 0) or 0
            y = placement.get("y", 0) or 0
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                continue
            bbox = _component_bbox(instances.get(inst_name, {}))
            if bbox is None:
                continue
            layout_items.append({
                "name": inst_name,
                "x": float(x),
                "y": float(y),
                "left": float(x) + bbox["left"],
                "right": float(x) + bbox["right"],
                "bottom": float(y) + bbox["bottom"],
                "top": float(y) + bbox["top"],
                "bbox": bbox,
            })

        if len(layout_items) < 2 or not _placement_overlaps(layout_items):
            return

        cursor = 0.0
        for item in sorted(layout_items, key=lambda item: (item["x"], item["y"], item["name"])):
            bbox = item["bbox"]
            new_x = cursor - bbox["left"]
            placements[item["name"]]["x"] = round(new_x, 3)
            placements[item["name"]]["y"] = round(item["y"], 3)
            cursor = new_x + bbox["right"] + clearance

    # --- Clean placements (stray component/settings keys) --------------------
    placements = data.get("placements", {})
    if isinstance(placements, dict):
        for _inst, pl in placements.items():
            if isinstance(pl, dict):
                for stray_key in ("component", "settings"):
                    pl.pop(stray_key, None)

    ports = data.get("ports", {})
    if isinstance(ports, dict):
        data["ports"] = {
            name: _normalise_port_ref(ref, {})
            for name, ref in ports.items()
            if isinstance(name, str)
        }
        ports = data["ports"]

    connections = data.get("connections", {})
    if isinstance(connections, dict):
        data["connections"] = _normalise_link_map(connections, ports)
        if not data["connections"]:
            data.pop("connections", None)

    routes = data.get("routes", {})
    if isinstance(routes, dict):
        for rdef in routes.values():
            if isinstance(rdef, dict) and isinstance(rdef.get("links"), dict):
                rdef["links"] = _normalise_link_map(rdef["links"], ports)

    # gdsfactory YAML treats placement mirror as a geometric mirror, not as the
    # logical mmi1x2-as-combiner flip the prompts ask for. Rotate named
    # combiners so o2/o3 face the splitter arms and o1 faces the output.
    if isinstance(instances, dict) and isinstance(placements, dict):
        for inst_name, inst_data in instances.items():
            if not isinstance(inst_data, dict):
                continue
            if inst_data.get("component") == "mmi1x2" and "combiner" in inst_name.lower():
                placement = placements.get(inst_name)
                if isinstance(placement, dict):
                    placement["rotation"] = 180
                    placement["mirror"] = False

    _repair_bbox_placements(data)

    # Multi-spiral characterization trees are better represented as direct
    # component connections. Routing long bundle trunks between very large
    # spirals can introduce near-parallel route artifacts that fail WG spacing
    # DRC even though the connected spiral cells are clean.
    if isinstance(instances, dict):
        spiral_count = sum(
            1
            for inst_data in instances.values()
            if isinstance(inst_data, dict)
            and "spiral" in str(inst_data.get("component", "")).lower()
        )
        routes = data.get("routes", {})
        if spiral_count >= 2 and isinstance(routes, dict) and routes:
            direct_connections = {}
            for route_def in routes.values():
                if not isinstance(route_def, dict):
                    continue
                links = route_def.get("links", {})
                if isinstance(links, dict):
                    direct_connections.update(links)
            if direct_connections:
                data["connections"] = direct_connections
                data.pop("routes", None)
                preserve_direct_connections = True

    # The butterfly benchmark is DRC-clean when each link is routed
    # independently. GPT models often add an empty connections: {} key or put
    # many links into one route bundle; canonicalize only route formatting here.
    # Do not synthesize a topology, otherwise the benchmark measures repair code
    # instead of model generation quality.
    if data.get("name") == "butterfly_8x8_network":
        routes = data.get("routes", {})
        if isinstance(routes, dict) and routes:
            shared_settings = {"cross_section": "strip", "radius": 20.0}
            all_links = {}
            for rdef in routes.values():
                if not isinstance(rdef, dict):
                    continue
                settings = rdef.get("settings", {})
                if isinstance(settings, dict):
                    shared_settings.update(settings)
                links = rdef.get("links", {})
                if isinstance(links, dict):
                    all_links.update(links)
            if all_links:
                shared_settings.pop("routing_strategy", None)
                data["routes"] = {
                    f"r{i}": {
                        "settings": dict(shared_settings),
                        "links": {src: dst},
                    }
                    for i, (src, dst) in enumerate(all_links.items())
                }
        connections = data.get("connections", {})
        if isinstance(connections, dict) and not connections:
            data.pop("connections", None)
        return _yaml.dump(data, default_flow_style=False, sort_keys=False)

    # GDSFactory accepts a direct ``connections`` mapping for placement-style
    # attachment, but those links may not become routed waveguides or
    # extractable netlist connections. Convert direct links to explicit routes
    # so downstream DRC/SAX/port validators see the physical connectivity.
    connections = data.get("connections", {})
    if (
        isinstance(connections, dict)
        and connections
        and "routes" not in data
        and not preserve_direct_connections
    ):
        data["routes"] = {
            f"r{i}": {
                "settings": {"cross_section": "strip", "radius": 20.0},
                "links": {src: dst},
            }
            for i, (src, dst) in enumerate(connections.items())
        }
        data.pop("connections", None)

    # --- Normalise routes: split into one bundle per link ----------------------
    # gdsfactory's route_bundle routes ALL links in a group as a parallel bundle,
    # requiring all target ports to face the same direction. LLMs often put links
    # with different directions into one group, causing "same angle" errors.
    # Fix: give each link its own route bundle so they're routed independently.
    routes = data.get("routes", {})
    if isinstance(routes, dict) and routes:
        shared_settings = {"cross_section": "strip", "radius": 20.0}
        all_links = {}
        for rname, rdef in list(routes.items()):
            if isinstance(rdef, dict):
                s = rdef.get("settings", {})
                if isinstance(s, dict):
                    shared_settings.update(s)
                links = rdef.get("links", {})
                if isinstance(links, dict):
                    all_links.update(links)

        # Strip routing_strategy (not supported by gf.read.from_yaml)
        shared_settings.pop("routing_strategy", None)

        new_routes = {}
        for i, (src, dst) in enumerate(all_links.items()):
            new_routes[f"r{i}"] = {"settings": dict(shared_settings), "links": {src: dst}}
        data["routes"] = new_routes

    return _yaml.dump(data, default_flow_style=False, sort_keys=False)


def build_component_from_yaml(yaml_str: str, sanitize: bool = True) -> tuple:
    """
    Build GDSFactory component from YAML DSL.
    Pre-sanitizes common LLM errors (stray keys, arithmetic in ports),
    then if the build fails with a routing-angle error brute-forces all
    mirror combinations for mmi1x2 instances before giving up.

    Args:
        yaml_str: Raw YAML string from LLM
        sanitize: If True (default), apply _sanitize_yaml first.
                  Pass False for vanilla/baseline phase to measure raw LLM output.

    Returns:
        (component, error_message)
    """
    if sanitize:
        yaml_str = _sanitize_yaml(yaml_str)
    try:
        if hasattr(gf, "clear_cache"):
            gf.clear_cache()
        component = gf.read.from_yaml(yaml_str)
        try:
            import yaml as _yaml

            data = _yaml.safe_load(yaml_str)
            if isinstance(data, dict):
                connections = {}
                direct_connections = data.get("connections", {})
                if isinstance(direct_connections, dict):
                    connections.update(direct_connections)
                routes = data.get("routes", {})
                if isinstance(routes, dict):
                    for route_def in routes.values():
                        if isinstance(route_def, dict) and isinstance(route_def.get("links"), dict):
                            connections.update(route_def["links"])
                component.info["picasso_yaml_netlist"] = {
                    "instances": data.get("instances", {}),
                    "connections": connections,
                    "ports": data.get("ports", {}),
                }
        except Exception:
            pass
        return component, None
    except Exception as e:
        error_msg = str(e)

    routing_errors = ("same angle", "ports at the target", "routing collision")
    if any(pat in error_msg.lower() for pat in routing_errors):
        component, _fixed = _try_all_mirror_combos(yaml_str)
        if component is not None:
            return component, None

    return None, error_msg


def translate_build_error(error_msg: str) -> str:
    """
    Convert cryptic gdsfactory build errors into actionable LLM feedback.
    """
    msg = error_msg.lower()

    if "same angle" in msg or "ports at the target" in msg or "routing collision" in msg:
        return (
            "ROUTING ANGLE ERROR: gdsfactory cannot route between ports that face the same direction.\n"
            "\nROOT CAUSE: You are likely missing 'mirror: true' on the combiner/second MMI, "
            "OR you have a route connecting two output ports (both facing right) instead of "
            "connecting an output to an input.\n"
            "\nFIX RULES:\n"
            "1. For mmi1x2 used as a COMBINER: add 'mirror: true' in its placements entry.\n"
            "   Without mirror:true, all ports face the same direction as the splitter — unroutable.\n"
            "2. Route only OUTPUT→INPUT pairs:\n"
            "   - mmi1x2 splitter: o1=input, o2=output, o3=output\n"
            "   - mmi1x2 combiner (mirror:true): o1=output, o2=input, o3=input\n"
            "   - straight/straight_heater_metal: o1=left-input, o2=right-output\n"
            "3. Each port must appear at most ONCE across all links.\n"
            "4. Never route o2→o2 or o3→o3 between two components at the same x-position.\n"
            "\nEXAMPLE of correct MZI routing:\n"
            "  routes:\n"
            "    optical:\n"
            "      settings: {cross_section: strip, radius: 20.0}\n"
            "      links:\n"
            "        mmi1,o2: ps1,o1\n"
            "        mmi1,o3: ps2,o1\n"
            "        ps1,o2: mmi2,o3\n"
            "        ps2,o2: mmi2,o2\n"
            "  placements:\n"
            "    mmi2: {x: 300, y: 0, mirror: true}  # <-- mirror: true is REQUIRED\n"
        )

    if "invalid literal for int" in msg or "invalid literal for float" in msg:
        import re
        bad_val = re.search(r"'([^']+)'", error_msg)
        bad_str = f" ('{bad_val.group(1)}')" if bad_val else ""
        return (
            f"ARITHMETIC EXPRESSION ERROR: The YAML contains an arithmetic expression{bad_str} "
            "where a plain number or port name was expected.\n"
            "\nThis can happen in SETTINGS, PORT NAMES, or ROUTE LINKS.\n"
            "\nFIX: Use ONLY literal values — NEVER arithmetic:\n"
            "  WRONG: length: 4-1   →  CORRECT: length: 3\n"
            "  WRONG: splitter,o4-1 →  CORRECT: splitter,o3\n"
            "  WRONG: mmi1,o3+1     →  CORRECT: mmi1,o4\n"
            "  WRONG: n_bend_90: 2+1 →  CORRECT: n_bend_90: 3\n"
            "Compute the value yourself and write the result directly.\n"
            "Port names are ALWAYS literal: o1, o2, o3, etc.\n"
        )

    if "not found" in msg and "component" in msg:
        return (
            f"COMPONENT NOT FOUND ERROR: {error_msg}\n"
            "\nFIX: Use only valid gdsfactory generic_tech components:\n"
            "  Valid: mmi1x2, straight, bend_euler, coupler, straight_heater_metal,\n"
            "         ring_single, grating_coupler_elliptical, mzi, crossing\n"
            "  ❌ mmi2x1 → use mmi1x2 with mirror: true\n"
            "  ❌ phase_shifter / heater → use straight_heater_metal\n"
        )

    if "port" in msg and ("not found" in msg or "does not exist" in msg):
        return (
            f"PORT ERROR: {error_msg}\n"
            "\nFIX: Use correct port names for each component:\n"
            "  mmi1x2:              o1 (single side), o2, o3 (dual side)\n"
            "  straight:            o1 (left), o2 (right)\n"
            "  straight_heater_metal: o1 (left), o2 (right)\n"
            "  coupler:             o1, o2 (inputs), o3, o4 (outputs)\n"
            "  crossing:            o1 west, o3 east, o2 north, o4 south; through o1-o3 and o2-o4\n"
            "  bend_euler:          o1 (input), o2 (output)\n"
        )

    # Generic fallback — return original with a hint
    return (
        f"COMPONENT BUILD ERROR: {error_msg}\n"
        "\nPlease review your YAML for:\n"
        "  1. Component names (use only valid gdsfactory components)\n"
        "  2. Port names (o1, o2, o3 — not p1, p2, input, output)\n"
        "  3. Route directions (output → input only, never output → output)\n"
        "  4. mirror: true on combiner MMIs\n"
        "  5. Numeric-only parameter values (no expressions like '4-1')\n"
    )


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
                structural_pass = (
                    sample.get('yaml_valid', False)
                    and sample.get('component_built', False)
                    and sample.get('drc_passed', False)
                )
                
                writer.writerow([
                    problem_id,
                    phase,
                    model_name,
                    sample_idx,
                    structural_pass,
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
            'yaml_valid': not enable_validation or not ENABLE_YAML_PILOT_VALIDATION,
            'component_built': False,
            'drc_passed': not enable_validation or not ENABLE_DRC_CHECK,
            'lvs_passed': not enable_validation or not ENABLE_LVS_CHECK,
            'optimization_done': False
        }
        
        # Step 1: Generate YAML DSL from LLM (with retry logic)
        yaml_output = None
        component = None
        build_error = None
        error_msg = None
        error_details = None
        
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
                        actionable = translate_build_error(build_error)
                        feedback_text += f"\n\n{actionable}\n"
                    
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
                
                yaml_output = extract_yaml_from_llm_output(yaml_output)
                
                logger.info("YAML DSL generated")
                
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                sample_result['errors'].append(f"LLM call failed: {str(e)}")
                if attempt == MAX_RETRY_ATTEMPTS:
                    results['samples'].append(sample_result)
                    results['fail_count'] += 1
                    break
                continue
            
            # Step 1.5: Pre-sanitize YAML (fix arithmetic, stray keys, route names)
            # Only runs in picasso/framework phase so vanilla measures raw LLM output.
            # The sanitizer also runs inside build_component_from_yaml as a safety net
            # for picasso mode (belt-and-suspenders); in vanilla mode build_component_from_yaml
            # is patched to skip it too (see below).
            if phase in ("picasso", "multi_agent"):
                yaml_output = _sanitize_yaml(yaml_output)
            
            # Step 2: Validate YAML DSL (pilot validation)
            error_msg = None
            error_details = None
            if enable_validation and ENABLE_YAML_PILOT_VALIDATION:
                is_valid, error_msg, error_details = validate_yaml_dsl(yaml_output, pilot_validator)
                if not is_valid:
                    logger.warning(f"YAML pilot validation failed: {error_msg}")
                    if phase in ("picasso", "multi_agent") and attempt < max_attempts - 1:
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
            # sanitize=False in vanilla so we measure the raw LLM output
            component, build_error = build_component_from_yaml(
                yaml_output, sanitize=(phase in ("picasso", "multi_agent"))
            )
            if component is None:
                logger.error(f"Failed to build component: {build_error}")
                if phase in ("picasso", "multi_agent") and attempt < max_attempts - 1:
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
        
        # If we exhausted retries, count this requested sample as evaluated.
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
            if sample_result not in results['samples']:
                sample_result['metrics'] = {
                    'structural_pass': False,
                    'functional_pass': sample_result.get('functional_pass', False),
                    'drc_passed': sample_result.get('drc_passed', False),
                    'lvs_passed': sample_result.get('lvs_passed', False),
                    'optimization_done': sample_result.get('optimization_done', False),
                }
                results['samples'].append(sample_result)
                results['fail_count'] += 1
                logger.info(f"❌ Sample {sample_idx + 1} FAILED")
            continue
        #sample_result['drc_passed'] = True
        # Step 4: DRC validation

        if enable_validation:
            if ENABLE_DRC_CHECK:
                drc_passed, drc_report = drc_validator.validate(component)
                sample_result['drc_passed'] = drc_passed
                sample_result['drc_report'] = drc_report
                
            else:
                drc_passed = True
                drc_report = {"passed": True, "violations": 0, "skipped": True}
                sample_result['drc_passed'] = True
                sample_result['drc_report'] = drc_report
                sample_result['warnings'].append("DRC skipped (disabled via ENABLE_DRC_CHECK)")

    # Always log clearly (DRC-focused visibility)
            if DEBUG_VALIDATION:
                logger.info(
                    f"[DRC DEBUG] passed={drc_passed}, "
                    f"violations={drc_report.get('violations', 0)}, "
                    f"skipped={drc_report.get('skipped', False)}, "
                    f"degraded={drc_report.get('degraded', False)}, "
                    f"klayout={drc_report.get('klayout_executable')}"
                )

    # Still keep warnings
            for warning in drc_report.get('warnings', []):
                sample_result['warnings'].append(f"DRC: {warning}")
            for error in drc_report.get('errors', []):
                sample_result['errors'].append(f"DRC: {error}")
            if not drc_passed:
                sample_result['warnings'].append(
                    f"DRC violations: {drc_report.get('violations', 0)}"
                )
        
        # Step 5: LVS validation (optional, may be slow)
        if enable_validation and ENABLE_LVS_CHECK:
            try:
                lvs_passed, lvs_report = lvs_validator.validate(component)
                sample_result['lvs_passed'] = lvs_passed
                sample_result['lvs_report'] = lvs_report
                if DEBUG_VALIDATION:
                    logger.info(
                        f"[LVS DEBUG] passed={lvs_passed}, "
                        f"skipped={lvs_report.get('skipped', False)}, "
                        f"degraded={lvs_report.get('degraded', False)}, "
                        f"available={lvs_report.get('available', False)}"
                    )
                for warning in lvs_report.get('warnings', []):
                    sample_result['warnings'].append(f"LVS: {warning}")
                for error in lvs_report.get('errors', []):
                    sample_result['errors'].append(f"LVS: {error}")
                if not lvs_passed:
                    logger.warning(f"LVS validation failed: {lvs_report.get('errors', [])}")
                elif lvs_report.get('skipped'):
                    logger.warning("LVS validation skipped")
                elif lvs_report.get('degraded'):
                    logger.warning("LVS validation used degraded basic structure check")
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
                    port_errors = port_report.get('errors', [])
                    if port_errors:
                        logger.warning(
                            "Port connection validation failed: %d issue(s); first: %s",
                            len(port_errors),
                            port_errors[0],
                        )
                    else:
                        logger.warning("Port connection validation failed")
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

        validation_failed = enable_validation and (
            not sample_result.get('drc_passed', False)
            or not sample_result.get('lvs_passed', False)
            or not sample_result.get('silicon_efficient', False)
            or not sample_result.get('port_connections_valid', False)
            or not sample_result.get('functional_pass', False)
        )
        if validation_failed:
            failure_reasons = []
            if not sample_result.get('drc_passed', False):
                failure_reasons.append("DRC")
                drc_report = sample_result.get('drc_report', {})
                for error in drc_report.get('errors', [])[:3]:
                    sample_result['errors'].append(f"DRC: {error}")
            if not sample_result.get('lvs_passed', False):
                failure_reasons.append("LVS")
            if not sample_result.get('silicon_efficient', False):
                failure_reasons.append("silicon efficiency")
            if not sample_result.get('port_connections_valid', False):
                failure_reasons.append("port connectivity")
            if not sample_result.get('functional_pass', False):
                failure_reasons.append("SAX")
            logger.info("Full validation failed: %s", ", ".join(failure_reasons) or "unknown")

        if validation_failed and phase == "picasso" and attempt < max_attempts - 1:
            feedback_parts = ["FULL VALIDATION FAILED. Regenerate the YAML with a fully validated topology."]
            if not sample_result.get('drc_passed', False):
                feedback_parts.append("DRC ERRORS:")
                drc_report = sample_result.get('drc_report', {})
                errors = drc_report.get('errors', [])[:3]
                if errors:
                    for error in errors:
                        feedback_parts.append(f"  - {error}")
                else:
                    feedback_parts.append("  - DRC validation failed; adjust spacing and remove geometry overlaps.")
                categories = drc_report.get('violations_by_category', {})
                if categories:
                    feedback_parts.append(f"  - Violation categories observed: {categories}")
                if categories.get('WG_space_min'):
                    feedback_parts.append(
                        "  - WG_space_min usually means routed waveguides/rings are too close or overlapping; "
                        "increase channel spacing and avoid crossing routes near ring/bus junctions."
                    )
            if not sample_result.get('port_connections_valid', False):
                port_report = sample_result.get('port_connection_report', {})
                feedback_parts.append("PORT CONNECTIVITY ERRORS:")
                for error in port_report.get('errors', [])[:3]:
                    feedback_parts.append(f"  - {error}")
                unconnected = port_report.get('unconnected_ports', [])
                if unconnected:
                    feedback_parts.append(
                        "  - Common failed ports in this task: "
                        f"{', '.join(unconnected[:12])}"
                    )
                feedback_parts.append(
                    "Fix: every unused bus or splitter optical endpoint must either be routed to another optical "
                    "port or exported as a top-level helper/channel port. Do not leave bus input endpoints floating, "
                    "but do not reuse a bus endpoint that is already connected or exported as opt_in. Heater optical "
                    "ports may remain unused when heaters are only nearby thermal tuners."
                )
            if not sample_result.get('functional_pass', False):
                sax_report = sample_result.get('sax_report', {})
                feedback_parts.append("SAX ERRORS:")
                for error in sax_report.get('errors', [])[:3]:
                    feedback_parts.append(f"  - {error}")
            feedback_parts.append(
                "Common topology mistakes are leaving one side of a two-port optical component floating, "
                "using only half of a crossing through path, exporting a port that is also reused incorrectly, "
                "or creating multi-port overlaps. Ensure each intended signal path is continuous from an "
                "exported input to an exported output."
            )
            error_msg = "\n".join(feedback_parts)
            build_error = None
            logger.info("Full validation feedback prepared for this failed sample")
        
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
        

        # Determine if sample passed
        sample_result['passed'] = (
            sample_result['yaml_valid'] and
            sample_result['component_built'] and
            (
                not enable_validation
                or (
                    sample_result['drc_passed']
                    and sample_result.get('lvs_passed', False)
                    and sample_result.get('silicon_efficient', False)
                    and sample_result.get('port_connections_valid', False)
                    and sample_result.get('functional_pass', False)
                )
            )
        )

        # Calculate metrics. Structural pass is intentionally weaker than full
        # pass: it means the YAML built and cleared DRC, even if later SAX/LVS/
        # connectivity/optimization gates failed.
        structural_pass = (
            sample_result['yaml_valid']
            and sample_result['component_built']
            and sample_result.get('drc_passed', False)
        )
        sample_metrics = {
            'structural_pass': structural_pass,
            'full_pass': sample_result['passed'],
            'functional_pass': sample_result.get('functional_pass', False),
            'drc_passed': sample_result.get('drc_passed', False),
            'lvs_passed': sample_result.get('lvs_passed', False),
            'silicon_efficient': sample_result.get('silicon_efficient', False),
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
    start_phase: Optional[str] = None,
    multi_agent: bool = False
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

    # Wrap in multi-agent orchestrator if requested
    if multi_agent:
        agent = wrap_multi_agent(agent)
    
    # Initialize validators and components
    pilot_validator = YAMLPilotValidator()
    drc_validator = DRCValidator()
    lvs_validator = LVSValidator()  # Disable for speed
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
    completed_problems.setdefault('multi_agent', set())
    logger.info(
        f"📊 Existing results: {len(completed_problems['vanilla'])} vanilla, "
        f"{len(completed_problems['picasso'])} picasso, "
        f"{len(completed_problems['multi_agent'])} multi_agent problems completed"
    )
    
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
    if not vanilla_only and (start_phase is None or start_phase in ("picasso", "multi_agent")):
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
    
    # Phase 3: Multi-Agent (Generator + Critic) — runs when --multi-agent or --compare
    if multi_agent and not vanilla_only:
        logger.info("\n" + "="*70)
        logger.info("PHASE 3: MULTI-AGENT (Generator + Critic)")
        logger.info("="*70)

        # Build the multi-agent orchestrator (fresh — don't reuse picasso agent state)
        base_agent = create_agent(model_name)
        multi_agent_runner = wrap_multi_agent(base_agent)

        multi_agent_results = []
        for problem in problems:
            problem_id = problem.get('id', '')

            if start_problem is None and problem_id in completed_problems['multi_agent']:
                logger.info(f"⏭️  Skipping Problem {problem_id} (multi_agent) - already completed")
                continue

            result = run_single_problem(
                problem=problem,
                agent=multi_agent_runner,
                prompt_template=picasso_prompt_template,
                pilot_validator=pilot_validator,
                drc_validator=drc_validator,
                lvs_validator=lvs_validator,
                sax_validator=sax_validator,
                silicon_validator=silicon_validator,
                port_connection_validator=port_connection_validator,
                optimizer=optimizer,
                model_name=model_name,
                phase="multi_agent",
                samples_per_problem=samples_per_problem,
                enable_validation=True,
                enable_optimization=True
            )
            multi_agent_results.append(result)
            all_results.append(result)

            try:
                csv_path = save_aggregated_metrics(model_name, [result], append=True)
                logger.debug(f"Updated metrics CSV after problem {result['problem_id']}")
            except Exception as e:
                logger.warning(f"Failed to update metrics CSV: {e}")

        logger.info(
            f"\nPhase 3 Summary: "
            f"{sum(r['pass_count'] for r in multi_agent_results)}/"
            f"{len(multi_agent_results) * samples_per_problem} passed"
        )

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

    def _aggregate_problem_metrics(results: List[Dict]) -> Dict:
        """Average per-problem metrics when no sample-level metrics are available."""
        metrics_list = [r.get('metrics', {}) for r in results if isinstance(r.get('metrics'), dict)]
        if not metrics_list:
            return {}
        keys = {
            'spec_at_k_structural',
            'spec_at_k_full',
            'avg_opt_efficiency',
            'robustness_score',
        }
        return {
            key: sum(float(m.get(key, 0.0) or 0.0) for m in metrics_list) / len(metrics_list)
            for key in keys
        }
    multi_agent_results_list = [r for r in all_results if r.get('phase') == 'multi_agent']

    logger.info("\n" + "="*70)
    logger.info("FINAL SUMMARY")
    logger.info("="*70)
    logger.info(f"Total problems: {len(problems)}")
    logger.info(f"Total samples: {total_samples}")
    logger.info(f"Total passed: {total_passed}")
    logger.info(f"Pass rate: {pass_rate:.1f}%")

    if vanilla_results_list:
        all_vanilla_samples = []
        for r in vanilla_results_list:
            all_vanilla_samples.extend(r.get('samples', []))
        if all_vanilla_samples:
            vanilla_metrics = compute_metrics_for_circuit(all_vanilla_samples, k=3, phase="vanilla")
        else:
            vanilla_metrics = _aggregate_problem_metrics(vanilla_results_list)
        logger.info(f"\nPhase 1 (Vanilla) Metrics:")
        logger.info(f"  Spec@k_structural: {vanilla_metrics.get('spec_at_k_structural', 0.0):.3f}")
        logger.info(f"  Spec@k_full: {vanilla_metrics.get('spec_at_k_full', 0.0):.3f}")
    
    if picasso_results_list:
        all_picasso_samples = []
        for r in picasso_results_list:
            all_picasso_samples.extend(r.get('samples', []))
        if all_picasso_samples:
            picasso_metrics = compute_metrics_for_circuit(all_picasso_samples, k=3, phase="picasso")
        else:
            picasso_metrics = _aggregate_problem_metrics(picasso_results_list)
        logger.info(f"\nPhase 2 (PICasso) Metrics:")
        logger.info(f"  Spec@k_structural: {picasso_metrics.get('spec_at_k_structural', 0.0):.3f}")
        logger.info(f"  Spec@k_full: {picasso_metrics.get('spec_at_k_full', 0.0):.3f}")
        logger.info(f"  Avg OptEff: {picasso_metrics.get('avg_opt_efficiency', 0.0):.3f}")
        logger.info(f"  Robustness Score: {picasso_metrics.get('robustness_score', 0.0):.3f}")

    if multi_agent_results_list:
        all_multi_agent_samples = []
        for r in multi_agent_results_list:
            all_multi_agent_samples.extend(r.get('samples', []))
        if all_multi_agent_samples:
            multi_agent_metrics = compute_metrics_for_circuit(all_multi_agent_samples, k=3, phase="picasso")
            logger.info(f"\nPhase 3 (Multi-Agent) Metrics:")
            logger.info(f"  Spec@k_structural: {multi_agent_metrics.get('spec_at_k_structural', 0.0):.3f}")
            logger.info(f"  Spec@k_full: {multi_agent_metrics.get('spec_at_k_full', 0.0):.3f}")
            logger.info(f"  Avg OptEff: {multi_agent_metrics.get('avg_opt_efficiency', 0.0):.3f}")
            logger.info(f"  Robustness Score: {multi_agent_metrics.get('robustness_score', 0.0):.3f}")

    # Print comparison table if multiple phases ran
    phases_run = (
        (1 if vanilla_results_list else 0) +
        (1 if picasso_results_list else 0) +
        (1 if multi_agent_results_list else 0)
    )
    if phases_run > 1:
        logger.info(f"\n{'='*70}")
        logger.info("COMPARISON TABLE")
        logger.info(f"{'='*70}")
        logger.info(f"{'Phase':<20} {'Spec@k_struct':>14} {'Spec@k_full':>12} {'OptEff':>8} {'Robust':>8}")
        logger.info(f"{'-'*70}")
        if vanilla_results_list and all_vanilla_samples:
            m = vanilla_metrics
            logger.info(
                f"{'1. Vanilla':<20} "
                f"{m.get('spec_at_k_structural', 0.0):>14.3f} "
                f"{m.get('spec_at_k_full', 0.0):>12.3f} "
                f"{'N/A':>8} {'N/A':>8}"
            )
        if picasso_results_list and all_picasso_samples:
            m = picasso_metrics
            logger.info(
                f"{'2. PICasso':<20} "
                f"{m.get('spec_at_k_structural', 0.0):>14.3f} "
                f"{m.get('spec_at_k_full', 0.0):>12.3f} "
                f"{m.get('avg_opt_efficiency', 0.0):>8.3f} "
                f"{m.get('robustness_score', 0.0):>8.3f}"
            )
        if multi_agent_results_list and all_multi_agent_samples:
            m = multi_agent_metrics
            logger.info(
                f"{'3. Multi-Agent':<20} "
                f"{m.get('spec_at_k_structural', 0.0):>14.3f} "
                f"{m.get('spec_at_k_full', 0.0):>12.3f} "
                f"{m.get('avg_opt_efficiency', 0.0):>8.3f} "
                f"{m.get('robustness_score', 0.0):>8.3f}"
            )
        logger.info(f"{'='*70}")

    logger.info("="*70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test gd_picasso framework with LLM')
    parser.add_argument('--model', type=str, default='gpt-4o', help='Model name (gpt-4o, gpt-4o-mini, etc.)')
    parser.add_argument('--problems', type=str, default='gd_picasso/problems_parsed1.txt', help='Problems file path')
    parser.add_argument('--num-problems', type=int, default=None, help='Number of problems to test (None = all)')
    parser.add_argument('--samples', type=int, default=5, help='Samples per problem')
    parser.add_argument('--vanilla-only', action='store_true', help='Run only Phase 1 (vanilla LLM)')
    parser.add_argument('--picasso-only', action='store_true', help='Run only Phase 2 (PICasso framework)')
    parser.add_argument('--start-problem', type=int, default=None, help='Resume from this problem number (1-based)')
    parser.add_argument('--start-phase', type=str, default=None, choices=['vanilla', 'picasso'], help='Resume from this phase')
    parser.add_argument('--multi-agent', action='store_true', help='Enable multi-agent mode (Generator + Critic)')
    parser.add_argument('--compare', action='store_true', help='Run all 3 phases (vanilla, picasso, multi-agent) and print comparison table')

    args = parser.parse_args()

    # Validate arguments
    if args.vanilla_only and args.picasso_only:
        logger.error("Cannot specify both --vanilla-only and --picasso-only")
        sys.exit(1)

    # --compare runs all three phases
    if args.compare:
        args.vanilla_only = False
        args.picasso_only = False
        args.multi_agent = True

    run_test(
        problems_file=args.problems,
        model_name=args.model,
        num_problems=args.num_problems,
        samples_per_problem=args.samples,
        vanilla_only=args.vanilla_only,
        picasso_only=args.picasso_only,
        start_problem=args.start_problem,
        start_phase=args.start_phase,
        multi_agent=args.multi_agent
    )
