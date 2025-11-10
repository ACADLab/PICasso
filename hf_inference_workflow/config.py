"""Configuration for HuggingFace Inference Workflow."""

import os
from pathlib import Path

# ============================================================================
# API Configuration
# ============================================================================

# OpenAI API Key - RECOMMENDED for best results
# Get your key from: https://platform.openai.com/api-keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

# OpenAI Model Selection
OPENAI_MODEL = "gpt-4o-mini"  # Cost-optimized model for code generation
# Alternative: "gpt-3.5-turbo" (even cheaper), "gpt-4o" (more capable but pricier)

# HuggingFace API Token - Cloud inference option
# Token loaded from hf_token.txt file
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "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")

# Model selection - Recommended models for code generation
# NOTE: Most models require proper token permissions (see above)
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

# Alternative models (try these if one doesn't work):
# DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"  # Smaller, faster
# DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"  # General purpose
# DEFAULT_MODEL = "microsoft/Phi-3-mini-4k-instruct"  # Compact model

# Models confirmed NOT available on serverless API:
# DEFAULT_MODEL = "deepseek-ai/deepseek-coder-6.7b-instruct"
# DEFAULT_MODEL = "bigcode/starcoder2-7b"
# DEFAULT_MODEL = "bigcode/starcoder2-15b"

# ============================================================================
# Generation Parameters
# ============================================================================

SAMPLES_PER_PROBLEM = 3      # Number of design samples to generate per problem (pass@3 benchmarking)
MAX_RETRY_ATTEMPTS = 3       # Maximum retry attempts for failed validations
REFINE_ROUNDS = 0            # Additional refinement rounds (set to 0 for efficiency)

# Two-Phase Tracking (for benchmarking raw LLM vs framework)
ENABLE_TWO_PHASE_TRACKING = True  # Track raw LLM baseline vs framework results separately

# Rate Limiting (for OpenAI API)
REQUEST_DELAY = 12.0          # Delay between API requests in seconds (for 5 RPM limit: 60s/5 = 12s)
                              # Adjust based on your tier: Tier 1=12s, Tier 2=6s, Tier 3=1s

# Model generation parameters
MODEL_PARAMS = {
    "max_new_tokens": 2048,
    "temperature": 0.3,       # Lower for more deterministic code
    "top_p": 0.95,
    "do_sample": True,
}

# ============================================================================
# Validation Configuration
# ============================================================================

# P&R Validation thresholds
MIN_COMPONENT_SPACING = 20.0  # Minimum spacing between components (µm)
MAX_LAYOUT_AREA = 500000.0    # Maximum acceptable layout area (µm²)
MAX_ROUTE_LENGTH = 2000.0     # Maximum individual route length (µm)

# DRC Validation
ENABLE_DRC_CHECK = True       # Enable/disable KLayout DRC checking
DRC_SCRIPT_PATH = None        # Path to custom DRC script (None = use default)

# SAX Validation
ENABLE_SAX_CHECK = True       # Enable/disable SAX compilation check
SAX_TIMEOUT = 30              # Timeout for SAX compilation (seconds)

# ============================================================================
# File Paths
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
PROBLEMS_FILE = PROJECT_ROOT / "problems.txt"
COMPONENTS_FILE = PROJECT_ROOT / "components.txt"

# Output directories
OUTPUT_DIR = PROJECT_ROOT / "hf_inference_workflow" / "output"
GDS_OUTPUT_DIR = OUTPUT_DIR / "gds_files"  # Legacy directory
CSV_OUTPUT_DIR = OUTPUT_DIR / "results"

# New directory structure for OpenAI workflow
GDS_FIRST_ATTEMPT_DIR = OUTPUT_DIR / "gds_first_attempt"  # All first attempts
PIC_SET_DIR = OUTPUT_DIR / "PIC_set"                      # Final clean dataset
GDS_CLEAN_DIR = PIC_SET_DIR / "gds_clean"                 # Validated clean GDS
CODE_CLEAN_DIR = PIC_SET_DIR / "code_clean"               # Python code for clean GDS

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GDS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GDS_FIRST_ATTEMPT_DIR.mkdir(parents=True, exist_ok=True)
PIC_SET_DIR.mkdir(parents=True, exist_ok=True)
GDS_CLEAN_DIR.mkdir(parents=True, exist_ok=True)
CODE_CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = OUTPUT_DIR / "generation.log"

# ============================================================================
# Component Knowledge Injection (NEW)
# ============================================================================

# Enable component specification injection to prevent port mismatch errors
ENABLE_COMPONENT_INJECTION = True

def load_component_specs():
    """
    Load GDSFactory component specifications from components.txt.
    This prevents LLM from generating invalid port names or incorrect API usage.
    """
    components_path = PROJECT_ROOT / "components.txt"
    if components_path.exists():
        with open(components_path, 'r') as f:
            return f.read()
    return ""

# Load component specs at module import (cached)
COMPONENT_SPECS = load_component_specs() if ENABLE_COMPONENT_INJECTION else ""

# ============================================================================
# Two-Phase Prompts: Vanilla LLM (Phase 1) vs Framework (Phase 2)
# ============================================================================

# Phase 1: Vanilla LLM prompt WITHOUT component knowledge injection
# Used only for the first attempt to establish baseline performance
VANILLA_LLM_PROMPT = """
Write me ONLY complete Python code (no extra prose) for the problem above.
Write the python code to instantiate the circuit in GDSFactory 9.9.4.

Follow the following structure for creating the circuit:
  1. Instantiate all components (with settings)
  2. Move parts to avoid overlap (DRC-safe with minimum 20µm spacing)
  3. Connect ports with route_bundle (NOT route_single) for clean routing
  4. Expose external ports

Restrictions (immutable across problems):
  - Use GDSFactory library components only
  - Ensure all optical ports connected
  - No comments / extraneous text
  - Ports labelled o1, o2, … clockwise
  - Do not create custom names for any models/components, use the id's specified in the problem
  - Use route_bundle for coordinated routing (prevents messy layouts)
  - Use single quotes around strings, avoid double quotes like ""xx""

Use the following example for your reference:
import gdsfactory as gf

r = gf.Component()

mmi_splitter = r.add_ref(gf.components.mmi1x2())
mmi_splitter.move((0,0))

mmi_combiner = r.add_ref(gf.components.mmi2x1())
mmi_combiner.move((200, 0))

ps1 = r.add_ref(gf.components.straight_heater_metal(length=10))
ps1.move((100, 50))

ps2 = r.add_ref(gf.components.straight_heater_metal(length=10))
ps2.move((100, -50))

gf.routing.route_bundle(
    r,
    [mmi_splitter.ports['o2'], mmi_splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=10,
    separation=10
)

gf.routing.route_bundle(
    r,
    [ps1.ports['o2'], ps2.ports['o2']],
    [mmi_combiner.ports['o1'], mmi_combiner.ports['o2']],
    cross_section='strip',
    radius=10,
    separation=10
)

r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

r.draw_ports()
r.plot()
"""

# ============================================================================
# Prompt Templates (from existing gen_data.py)
# ============================================================================

JSON_PROMPT_TEMPLATE = """
Write me ONLY a complete JSON photonic netlist (no extra prose) for the problem above.
The JSON must contain top-level keys "instance", "connections", "ports", and "models".

You must adhere to the following restrictions:
    - Ensure all optical ports are connected
    - Do not include any comments
    - Ports are labeled o1, o2, o3, ... such that the bottom-left port is o1, then ports are labelled moving clockwise

Follow the following JSON netlist template:
<<< JSON Netlist Template >>>
{
"netlist":{
    "instances": {
    "<component_name1>": "<component>",
    "<component_name2>": {'component': '<component>', 'settings': {'<parameter>': <value>}}
    ...
    },
    "connections": {
    "<component_name>,<port>": "<component_name>,<port>",
    ...
    },
    "ports": {
    "<port_name>": "<component_name>,<port>",
    ...
    }
},
"models":{
    "<component>": "<ref>",
    ...
}
}
"""

PYTHON_PROMPT_TEMPLATE = f"""
You are a professional Photonic Integrated Circuit (PIC) designer with expertise in GDSFactory.
Your task is to generate Python code based on the circuit design requirements provided.

{'--- AVAILABLE GDSFACTORY COMPONENTS REFERENCE ---' if ENABLE_COMPONENT_INJECTION else ''}
{'Use ONLY the following components with their EXACT port names and API signatures:' if ENABLE_COMPONENT_INJECTION else ''}
{'<warning>' if ENABLE_COMPONENT_INJECTION else ''}
{COMPONENT_SPECS if ENABLE_COMPONENT_INJECTION else ''}
{'</warning>' if ENABLE_COMPONENT_INJECTION else ''}
{'--- END COMPONENTS REFERENCE ---' if ENABLE_COMPONENT_INJECTION else ''}

IMPORTANT RESTRICTIONS (to avoid common mistakes):
  1. Component Selection:
     - Use ONLY GDSFactory library components (gf.components.*)
     - Verify component port names from the reference above
     - Use the exact component IDs specified in the problem statement

  2. Port Naming and Connection:
     - Check available ports using the component reference
     - Common mistake: Assuming port names like 'o3' exist when they don't
     - MMI ports: typically 'o1', 'o2' (outputs), check reference for exact names
     - All optical ports MUST be connected (no dangling ports)

  3. Component Mirroring (CRITICAL ERROR TO AVOID):
     - WRONG: gf.components.mmi1x2().mirror()  # Cell objects don't have mirror()
     - CORRECT: ref = r.add_ref(gf.components.mmi1x2()); ref.mirror()
     - Always call mirror() AFTER add_ref(), on the ComponentReference

  4. Spacing Rules (prevents ROUTING_COLLISION):
     - Minimum 80µm spacing between components (150µm for complex designs)
     - Vertical stacking: Use ±60µm or more vertical offset
     - Horizontal placement: 150-200µm separation
     - Bend radius: ≥ 15µm (20-30µm for safety)
     - Route separation in route_bundle: ≥ 15µm

  5. Parameters and Settings:
     - Use default values unless explicitly specified in the problem
     - If parameter difference specified (e.g., ΔL = 10µm), set one to default, adjust other
     - Default unit: microns (µm)

  6. Code Format:
     - Use single quotes for strings (not double quotes)
     - No comments or explanations in code
     - Follow the structure: instantiate → move → route → add_ports

Your response MUST consist of TWO sections:

<analysis>
Provide a detailed step-by-step analysis of how you will implement the circuit.
Think through:
  1. What components are needed? (check component reference for exact names)
  2. What are their port names? (verify from reference, don't guess)
  3. How should they be arranged spatially? (spacing requirements)
  4. How should ports be connected? (routing strategy)
  5. What parameters need to be set? (use defaults unless specified)
  6. Any special considerations? (mirroring, flipping, complex routing)
</analysis>

<result>
Provide ONLY the complete, executable Python code (no explanations, no markdown).
The code must follow this structure:

import gdsfactory as gf

r = gf.Component()

# 1. Instantiate components with settings
component1 = r.add_ref(gf.components.xxx(...))
component1.move((x1, y1))

component2 = r.add_ref(gf.components.yyy(...))
component2.move((x2, y2))

# 2. Route connections
gf.routing.route_bundle(
    r,
    [source_ports],
    [dest_ports],
    cross_section='strip',
    radius=15,
    separation=15
)

# 3. Expose external ports
r.add_port('o1', port=component1.ports['xxx'])
r.add_port('o2', port=component2.ports['yyy'])

# 4. Finalize
r.draw_ports()
r.plot()
</result>

REFERENCE EXAMPLE:
<analysis>
We need to create a Mach-Zehnder Modulator with:
  1. One splitter (MMI 1×2)
  2. Two phase shifters (straight_heater_metal)
  3. One combiner (MMI 2×1, needs mirroring for correct orientation)

Component arrangement:
  - Splitter at (0, 0)
  - Phase shifters at (100, 50) and (100, -50) - vertical separation 100µm prevents collision
  - Combiner at (250, 0) - horizontal separation 250µm provides safe routing space

Port connections:
  - Splitter o2, o3 → Phase shifter inputs
  - Phase shifter outputs → Combiner o2, o1 (note reversed order after mirroring)

Critical: Combiner needs mirror() called AFTER add_ref() to match port orientation.
</analysis>

<result>
import gdsfactory as gf

r = gf.Component()

mmi_splitter = r.add_ref(gf.components.mmi1x2())
mmi_splitter.move((0,0))

mmi_combiner = r.add_ref(gf.components.mmi2x1())
mmi_combiner.mirror()
mmi_combiner.move((250, 0))

ps1 = r.add_ref(gf.components.straight_heater_metal(length=10))
ps1.move((100, 50))

ps2 = r.add_ref(gf.components.straight_heater_metal(length=10))
ps2.move((100, -50))

gf.routing.route_bundle(
    r,
    [mmi_splitter.ports['o2'], mmi_splitter.ports['o3']],
    [ps1.ports['o1'], ps2.ports['o1']],
    cross_section='strip',
    radius=15,
    separation=15
)

gf.routing.route_bundle(
    r,
    [ps1.ports['o2'], ps2.ports['o2']],
    [mmi_combiner.ports['o2'], mmi_combiner.ports['o1']],
    cross_section='strip',
    radius=15,
    separation=15
)

r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

r.draw_ports()
r.plot()
</result>
"""

# ============================================================================
# Optimization Configuration (NEW)
# ============================================================================

# TWO-LEVEL OPTIMIZATION:
#   Level 1 (Device): Optimize component geometries (width, length, gap, radius)
#                     to match target insertion losses from literature using SAX
#   Level 2 (Circuit): Optimize phase shifters and couplings for minimum insertion loss

# Enable device-level optimization (Level 1)
ENABLE_DEVICE_OPTIMIZATION = True  # Optimize component geometries to match target losses

# Enable circuit-level optimization (Level 2)
ENABLE_OPTIMIZATION = True         # Optimize phase shifters and coupling parameters

# Optimization parameters
OPTIMIZATION_MAX_ITER = 400      # Maximum iterations for optimizer (Nelder-Mead)
OPTIMIZATION_RESTARTS = 8        # Number of random restarts for global optimization
OPTIMIZATION_TIMEOUT = 120       # Timeout for optimization (seconds)

# Loss Target Validation
ENABLE_LOSS_TARGET_CHECK = True  # Enable checking against target loss values
LOSS_TOLERANCE_DB = 1.0          # Allowed tolerance above target (dB)

# Functional Validation (NEW - Like VHDL/SPICE Testbenches)
ENABLE_FUNCTIONAL_VALIDATION = True  # Enable functional testing using SAX simulation
                                      # Tests circuit behavior (e.g., 8-QAM produces 8 states)
                                      # Similar to VHDL testbenches or SPICE simulation checks

# Optimization retry policy
RETRY_ON_LOSS_TARGET_FAIL = True  # Retry with LLM feedback if loss target not met
MAX_LOSS_OPTIMIZATION_ATTEMPTS = 2  # Max attempts to meet loss target via LLM retry

# ============================================================================
# Local GPU Model Configuration (NEW)
# ============================================================================

# Inference Mode Selection
USE_LOCAL_GPU_MODELS = False      # True = local GPU models, False = API inference
                                  # API inference is used when:
                                  #   - Local GPU is unavailable or has compatibility issues
                                  #   - Simpler setup without local model dependencies
                                  #   - Access to latest hosted models

# Local Model Selection (for USE_LOCAL_GPU_MODELS=True)
LOCAL_MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"
# Alternative local models:
# LOCAL_MODEL_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct"  # Excellent code quality, needs 2×A100
# LOCAL_MODEL_NAME = "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"  # Memory-efficient

# GPU Configuration
AUTO_DEVICE_MAP = True            # Automatic GPU device mapping (multi-GPU support)
TORCH_DTYPE = "float16"           # "float16" (faster) or "float32" (more accurate)
MAX_GPU_MEMORY_GB = None          # Max GPU memory per device (None = auto)

# Model Caching
CACHE_DIR = PROJECT_ROOT / ".model_cache"  # Directory for model weights
CACHE_DIR.mkdir(parents=True, exist_ok=True)
