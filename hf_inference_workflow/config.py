"""Configuration for HuggingFace Inference Workflow."""

import os
from pathlib import Path

# ============================================================================
# API Configuration
# ============================================================================

# HuggingFace API Token - Set via environment variable or replace with your token
# IMPORTANT: Current token returns 404 - needs to be replaced!
#
# To fix:
# 1. Go to https://huggingface.co/settings/tokens/new
# 2. Create "Fine-grained" token
# 3. Enable permission: "Make calls to Inference Providers"
# 4. Replace token below or set HF_API_TOKEN environment variable
#
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

SAMPLES_PER_PROBLEM = 2      # Number of design samples to generate per problem (reduced for 15min runtime)
MAX_RETRY_ATTEMPTS = 3       # Maximum retry attempts for failed validations
REFINE_ROUNDS = 0            # Additional refinement rounds (set to 0 for efficiency)

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
GDS_OUTPUT_DIR = OUTPUT_DIR / "gds_files"
CSV_OUTPUT_DIR = OUTPUT_DIR / "results"

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GDS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = OUTPUT_DIR / "generation.log"

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

PYTHON_PROMPT_TEMPLATE = """
Write me ONLY complete Python code (no extra prose) for the problem above.
Write the python code to instantiate the circuit in GDSFactory 9.9.4.
Follow the following structure for creating the circuit:
  1. Instantiate all components (with settings)
  2. Move parts to avoid overlap (DRC-safe with minimum 20µm spacing)
  3. Connect ports with route_bundle (NOT route_single) for clean routing
  4. Expose external ports

Restrictions (immutable across problems):
  - Only use GDSFactory components & port names
  - Ensure all optical ports connected
  - No comments / extraneous text
  - Ports labelled o1, o2, … clockwise
  - Do not create custom names for any models/components, use the id's specified in the problem
  - Use route_bundle for coordinated routing (prevents messy layouts)
  - Ensure minimum 20µm spacing between components
  - Use bend radius >= 10µm for all routes
  - Use single quotes around strings, avoid double quotes like ""xx""

Use the following example for your reference:
import gdsfactory as gf

r = gf.Component()

mmi_splitter = r.add_ref(gf.components.mmi(inputs=1, outputs=2))
mmi_splitter.move((0,0))

mmi_combiner = r.add_ref(gf.components.mmi(inputs=2, outputs=1))
mmi_combiner.move((200, 0))

ps1 = r.add_ref(gf.components.straight_heater_metal(length=10))
ps1.move((100, 30))

ps2 = r.add_ref(gf.components.straight_heater_metal(length=10))
ps2.move((100, -30))

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
    [mmi_combiner.ports['o2'], mmi_combiner.ports['o1']],
    cross_section='strip',
    radius=10,
    separation=10
)

r.add_port('o1', port=mmi_splitter.ports['o1'])
r.add_port('o2', port=mmi_combiner.ports['o3'])

r.draw_ports()
r.plot()
"""
