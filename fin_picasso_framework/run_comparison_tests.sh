#!/bin/bash
# Run Vanilla vs Framework Comparison Tests

set -e

cd "$(dirname "$0")/.."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate picasso

export OPENAI_API_KEY="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"

MODEL="deepseek_r1"
PROBLEMS_FILE="test_problems.txt"
SAMPLES=3

echo "======================================================================"
echo "PICASSO FRAMEWORK - VANILLA vs FRAMEWORK COMPARISON"
echo "======================================================================"
echo "Model: $MODEL"
echo "Problems: $PROBLEMS_FILE"
echo "Samples per problem: $SAMPLES"
echo "======================================================================"

# ============================================================================
# PHASE 1: VANILLA LLM (No Framework Features)
# ============================================================================
echo ""
echo "======================================================================"
echo "PHASE 1: VANILLA LLM TEST (No Framework, No Auto-Correction)"
echo "======================================================================"
echo "Features DISABLED:"
echo "  - Auto-correction: OFF"
echo "  - YAML validation: OFF"
echo "  - Component injection: OFF (for Phase 1 baseline)"
echo "  - Pilot validation: ON (syntax check only)"
echo "======================================================================"

# Disable framework features
export VANILLA_MODE=1
export ENABLE_AUTO_CORRECTION=0
export ENABLE_EARLY_NETLIST_VALIDATION=0

python fin_picasso_framework/test_with_model.py \
    --model "$MODEL" \
    --problems "$PROBLEMS_FILE" \
    --samples "$SAMPLES" \
    --vanilla \
    2>&1 | tee fin_picasso_framework/results_vanilla.log

echo ""
echo "✅ Vanilla test complete. Results saved to: fin_picasso_framework/results_vanilla.log"
echo ""

# ============================================================================
# PHASE 2: FRAMEWORK MODE (With All Features)
# ============================================================================
echo "======================================================================"
echo "PHASE 2: PICASSO FRAMEWORK TEST (With All Features)"
echo "======================================================================"
echo "Features ENABLED:"
echo "  - Auto-correction: ON"
echo "  - YAML validation: ON"
echo "  - Component injection: ON"
echo "  - Pilot validation: ON (full checks)"
echo "  - Dynamic pilot updates: ON"
echo "======================================================================"

# Enable framework features
unset VANILLA_MODE
export ENABLE_AUTO_CORRECTION=1
export ENABLE_EARLY_NETLIST_VALIDATION=1

python fin_picasso_framework/test_with_model.py \
    --model "$MODEL" \
    --problems "$PROBLEMS_FILE" \
    --samples "$SAMPLES" \
    2>&1 | tee fin_picasso_framework/results_framework.log

echo ""
echo "✅ Framework test complete. Results saved to: fin_picasso_framework/results_framework.log"
echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo "======================================================================"
echo "COMPARISON COMPLETE"
echo "======================================================================"
echo "Vanilla results: fin_picasso_framework/results_vanilla.log"
echo "Framework results: fin_picasso_framework/results_framework.log"
echo "======================================================================"

