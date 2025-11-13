"""Centralized configuration for PICasso Framework."""

import os
from pathlib import Path

# ============================================================================
# Project Paths
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
FRAMEWORK_ROOT = Path(__file__).parent

# Test case paths
HF_MODELS_RESULTS_DIR = PROJECT_ROOT / "hf_models" / "hf_model_results"
OPENAI_LLMS_DIR = PROJECT_ROOT / "openAI_llms"
TEST_9_FILE = PROJECT_ROOT / "test_problems.txt"  # Adjust if test_9 is in different file
PROBLEMS_FILE = PROJECT_ROOT / "Pic_set_enhanced.txt"  # Default problems file (36 problems)
# Fallback to test_problems.txt if enhanced version doesn't exist
if not PROBLEMS_FILE.exists():
    PROBLEMS_FILE = PROJECT_ROOT / "test_problems.txt"

# Output directories
OUTPUT_DIR = FRAMEWORK_ROOT / "output"
GDS_OUTPUT_DIR = OUTPUT_DIR / "gds_files"
CSV_OUTPUT_DIR = OUTPUT_DIR / "results"
TEST_OUTPUT_DIR = OUTPUT_DIR / "test_results"

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
GDS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Module Enable/Disable Flags
# ============================================================================

# Input Quality Module
ENABLE_INPUT_VALIDATION = True
ENABLE_PROMPT_ENHANCEMENT = True

# Port Matching Module
ENABLE_PORT_MATCHING = True
ENABLE_COMPONENT_SPEC_LOADING = True

# SAX Models Module
ENABLE_SAX_MODEL_MANAGEMENT = True
ENABLE_SAX_KNOWLEDGE_INJECTION = True

# Early Validation Module
ENABLE_EARLY_NETLIST_VALIDATION = True
ENABLE_NETLIST_CONVERSION = True

# Functionality Module
ENABLE_PORT_DECLARATION_CHECK = True
ENABLE_SILICON_EFFICIENCY_CHECK = True
ENABLE_FUNCTIONAL_VALIDATION = True

# Pilot System
ENABLE_PILOT_VALIDATION = True
ENABLE_RESTRICTION_LOADING = True

# Testing Module
ENABLE_TEST_EXTRACTION = True
ENABLE_FRAMEWORK_TESTING = True

# ============================================================================
# Validation Thresholds
# ============================================================================

# P&R Validation
MIN_COMPONENT_SPACING = 20.0  # Minimum spacing between components (µm)
MAX_LAYOUT_AREA = 500000.0    # Maximum acceptable layout area (µm²)
MAX_ROUTE_LENGTH = 2000.0     # Maximum individual route length (µm)

# DRC Validation
ENABLE_DRC_CHECK = True
DRC_SCRIPT_PATH = None

# SAX Validation
ENABLE_SAX_CHECK = True
SAX_TIMEOUT = 30

# Port Declaration Validation
REQUIRE_EXACT_PORT_MATCH = True  # Require exact port count match
ALLOW_EXTRA_PORTS = False        # Allow extra ports beyond specification

# Silicon Efficiency
MAX_UNCONNECTED_COMPONENTS = 0    # Maximum allowed unconnected components
MAX_EXCESS_SILICON_RATIO = 0.1   # Maximum ratio of excess silicon area

# ============================================================================
# Port Matching Configuration
# ============================================================================

# GDSFactory version detection
AUTO_DETECT_GDSFACTORY_VERSION = True
DEFAULT_GDSFACTORY_VERSION = "9.9.4"

# Port name mappings (for version compatibility)
PORT_NAME_MAPPINGS = {
    "I1": "o1",
    "I2": "o2",
    "O1": "o1",
    "O2": "o2",
}

# ============================================================================
# SAX Model Configuration
# ============================================================================

# SAX model creation
AUTO_CREATE_SAX_MODELS = True
SAX_MODEL_CACHE_DIR = FRAMEWORK_ROOT / "sax_models" / "cache"
SAX_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# SAX knowledge injection
INJECT_SAX_KNOWLEDGE_TO_LLM = True
SAX_KNOWLEDGE_FORMAT = "component_reference"  # or "usage_examples"

# ============================================================================
# Early Validation Configuration
# ============================================================================

# Netlist validation
CHECK_ROUTING_FEASIBILITY = True
CHECK_PLACEMENT_CONSTRAINTS = True
MIN_NETLIST_SPACING = 20.0  # Minimum spacing from netlist placements

# Netlist conversion
SUPPORT_JSON_NETLIST = True
SUPPORT_YAML_NETLIST = True
AUTO_ROUTE_ON_CONVERSION = True

# ============================================================================
# Pilot System Configuration
# ============================================================================

PILOT_MIN_SPACING_UM = 100.0
PILOT_MIN_VERTICAL_SPACING_UM = 60.0
PILOT_MIN_BEND_RADIUS_UM = 15.0
PILOT_LEARNING_THRESHOLD = 3

# ============================================================================
# Testing Configuration
# ============================================================================

# Test extraction
EXTRACT_FROM_NOTEBOOKS = True
EXTRACT_FROM_OPENAI_LLMS = True
PARSE_FIRST_PASS = True  # Run parser/router first pass
IDENTIFY_FALSE_DATA = True  # Identify designs that pass SAX but fail routing/DRC

# Framework testing
TARGET_CATCH_RATE = 1.0  # Target catch rate for false data cases (1.0 = 100%)

# ============================================================================
# Result Saving and Checkpoint Configuration
# ============================================================================

# Enable result saving
ENABLE_RESULT_SAVING = True
ENABLE_CHECKPOINTS = True

# Result saving paths
BENCHMARK_RESULTS_DIR = OUTPUT_DIR / "benchmark_results"
RAW_LLM_DIR = BENCHMARK_RESULTS_DIR / "raw_llm"
FRAMEWORK_PROCESSED_DIR = BENCHMARK_RESULTS_DIR / "framework_processed"
CHECKPOINTS_DIR = BENCHMARK_RESULTS_DIR / "checkpoints"

# Create directories
BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RAW_LLM_DIR.mkdir(parents=True, exist_ok=True)
FRAMEWORK_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Error Handling and Robustness Configuration
# ============================================================================

# Enable error extraction and enhanced feedback
ENABLE_ERROR_EXTRACTION = True
ENABLE_ENHANCED_FEEDBACK = True

# Enable robustness verification
ENABLE_ROBUSTNESS_CHECK = True
ROBUSTNESS_CHECK_AFTER_PASS_AT_K = 3  # Check robustness after pass@3 failures

# Enable dynamic pilot updates
ENABLE_DYNAMIC_PILOT_UPDATES = True
TARGET_CATCH_RATE = 1.0  # 100% catch rate for routing/DRC issues
TEST_WITH_TEST_9 = True  # Use test_9 for initial testing

# ============================================================================
# LLM Configuration
# ============================================================================

# API Configuration
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Model selection
DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"
OPENAI_MODEL = "gpt-4o-mini"

# Generation parameters
SAMPLES_PER_PROBLEM = 3
MAX_RETRY_ATTEMPTS = 2  # Reduced from 3 to force better first attempts (PhIDO-inspired)
MODEL_PARAMS = {
    "max_new_tokens": 2048,
    "temperature": 0.3,
    "top_p": 0.95,
    "do_sample": True,
}

# ============================================================================
# Optimization Configuration
# ============================================================================

ENABLE_DEVICE_OPTIMIZATION = True
ENABLE_OPTIMIZATION = True
OPTIMIZATION_MAX_ITER = 400
OPTIMIZATION_RESTARTS = 8

# Loss Target Validation
ENABLE_LOSS_TARGET_CHECK = True
LOSS_TOLERANCE_DB = 1.0

# Functional Validation
ENABLE_FUNCTIONAL_VALIDATION = True

# Auto-Correction
ENABLE_AUTO_CORRECTION = True
AUTO_CORRECT_MAX_ATTEMPTS = 1

# YAML Netlist Validation (after Python execution)
ENABLE_EARLY_NETLIST_VALIDATION = True
MIN_NETLIST_SPACING = 80.0  # Minimum spacing in microns for YAML netlist validation

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_LEVEL = "INFO"
LOG_FILE = OUTPUT_DIR / "framework.log"

