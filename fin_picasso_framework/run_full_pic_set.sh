#!/bin/bash
# Run Full PIC Set with Kimi2 Model
# This script runs the entire PIC set with monitoring

set -e

echo "=========================================="
echo "PICasso Framework - Full PIC Set Run"
echo "=========================================="
echo "Model: Kimi2 (moonshotai/Kimi-K2-Thinking:novita)"
echo "Samples: 3 per problem (pass@3)"
echo "=========================================="
echo ""

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

# Check HF_TOKEN or HF_API_TOKEN
if [ -z "$HF_TOKEN" ] && [ -z "$HF_API_TOKEN" ]; then
    echo "⚠️  HF_TOKEN or HF_API_TOKEN environment variable not set"
    echo "Please set it: export HF_API_TOKEN=your_token_here"
    echo "Or: export HF_TOKEN=your_token_here"
    exit 1
fi

# Export token if not already set
if [ -z "$HF_API_TOKEN" ] && [ -n "$HF_TOKEN" ]; then
    export HF_API_TOKEN="$HF_TOKEN"
fi

# Create output directory with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="fin_picasso_framework/output/full_pic_set_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""

# Run the test
echo "Starting full PIC set generation..."
echo "This will take a while - monitor progress in the log files"
echo "=========================================="
echo ""

# Run in background and save PID
python fin_picasso_framework/test_with_model.py \
    --model kimi2 \
    --samples 3 \
    2>&1 | tee "${OUTPUT_DIR}/full_run.log" &
    
PID=$!
echo "Process started with PID: $PID"
echo "Monitor with: tail -f ${OUTPUT_DIR}/full_run.log"
echo "Or use: python fin_picasso_framework/monitor_test.py"
echo ""

# Wait for process
wait $PID
EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Full PIC set generation complete!"
else
    echo "⚠️  Generation completed with exit code: $EXIT_CODE"
fi
echo "=========================================="
echo "Results saved to:"
echo "  - ${OUTPUT_DIR}/full_run.log (full log)"
echo "  - fin_picasso_framework/output/benchmark_results/ (results)"
echo "  - framework_test.log (framework log)"
echo ""
echo "Check progress with:"
echo "  python fin_picasso_framework/monitor_test.py"
echo "=========================================="

