#!/bin/bash
# Run Framework Test with DeepSeek-R1 or Kimi2
# This script activates the correct environment and runs the test

set -e

echo "=========================================="
echo "PICasso Framework Test Runner"
echo "=========================================="

# Check if picasso environment exists
if conda env list | grep -q "^picasso "; then
    echo "✅ Found picasso conda environment"
    echo "Activating picasso environment..."
    eval "$(conda shell.bash hook)"
    conda activate picasso
else
    echo "⚠️  picasso environment not found, using current environment"
fi

# Check Python and gdsfactory
echo ""
echo "Checking environment..."
python -c "import gdsfactory as gf; print(f'✅ gdsfactory version: {gf.__version__}')" || {
    echo "❌ gdsfactory not available"
    echo "Please install: pip install gdsfactory"
    exit 1
}

# Get model from argument or use default
MODEL=${1:-deepseek_r1}
NUM_PROBLEMS=${2:-1}
SAMPLES=${3:-1}

echo ""
echo "Configuration:"
echo "  Model: $MODEL"
echo "  Problems: $NUM_PROBLEMS"
echo "  Samples per problem: $SAMPLES"
echo ""

# Run the test
echo "Starting framework test..."
echo "=========================================="
python fin_picasso_framework/test_with_model.py \
    --model "$MODEL" \
    --problems "$NUM_PROBLEMS" \
    --samples "$SAMPLES" \
    2>&1 | tee framework_test_run.log

echo ""
echo "=========================================="
echo "Test complete!"
echo "Check results in:"
echo "  - framework_test_run.log (full log)"
echo "  - framework_test.log (framework log)"
echo "  - fin_picasso_framework/output/benchmark_results/ (results)"
echo "=========================================="


