#!/bin/bash
# Run Full PIC Set with Kimi2 Model
# This script runs the entire PIC set (9 problems, 3 samples each = 27 total) with monitoring

set -e

echo "=========================================="
echo "PICasso Framework - Full PIC Set Run"
echo "=========================================="
echo "Model: Kimi2 (moonshotai/Kimi-K2-Thinking:novita)"
echo "Problems: ALL 9 problems"
echo "Samples: 3 per problem (pass@3)"
echo "Total: 27 generations"
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

# Set HF_API_TOKEN if provided
if [ -n "$1" ]; then
    export HF_API_TOKEN="$1"
    echo "✅ Using provided HF_API_TOKEN"
elif [ -z "$HF_API_TOKEN" ] && [ -z "$HF_TOKEN" ]; then
    echo "⚠️  HF_API_TOKEN or HF_TOKEN not set"
    echo "Usage: $0 [HF_API_TOKEN]"
    echo "Or set: export HF_API_TOKEN=your_token"
    exit 1
fi

# Export token if HF_TOKEN is set but HF_API_TOKEN is not
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
echo "Starting full PIC set generation with Kimi2..."
echo "This will take a while - monitor progress in the log files"
echo "=========================================="
echo ""

# Run in background and save PID
nohup python fin_picasso_framework/test_with_model.py \
    --model kimi2 \
    --samples 3 \
    2>&1 | tee "${OUTPUT_DIR}/full_run.log" &
    
PID=$!
echo "Process started with PID: $PID"
echo "Log file: ${OUTPUT_DIR}/full_run.log"
echo ""
echo "Monitor progress with:"
echo "  tail -f ${OUTPUT_DIR}/full_run.log"
echo "  python fin_picasso_framework/monitor_test.py"
echo "  python fin_picasso_framework/monitor_live.py"
echo ""
echo "To stop: kill $PID"
echo "=========================================="

# Save PID to file
echo $PID > "${OUTPUT_DIR}/.pid"

echo "Waiting for initial startup..."
sleep 5

# Check if process is still running
if ps -p $PID > /dev/null; then
    echo "✅ Process is running (PID: $PID)"
    echo ""
    echo "You can now:"
    echo "  1. Monitor live: python fin_picasso_framework/monitor_live.py"
    echo "  2. Check logs: tail -f ${OUTPUT_DIR}/full_run.log"
    echo "  3. Check status: python fin_picasso_framework/monitor_test.py"
    echo ""
    echo "The process will continue running in the background."
    echo "Check ${OUTPUT_DIR}/full_run.log for completion status."
else
    echo "❌ Process failed to start. Check ${OUTPUT_DIR}/full_run.log for errors."
    exit 1
fi


