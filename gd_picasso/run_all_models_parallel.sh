#!/bin/bash
# Run all models in parallel for PICasso framework testing
# Each model runs in a separate background process with its own log file

# Don't exit on error - we want to start all models even if one fails
set +e

echo "=========================================="
echo "PICasso Framework - Parallel Model Execution"
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

# Set API keys from environment (should already be set)
echo ""
echo "Checking API keys..."
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY not set"
fi
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️  DEEPSEEK_API_KEY not set"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set"
fi
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  GEMINI_API_KEY not set"
fi
if [ -z "$HF_TOKEN" ] && [ -z "$HF_API_TOKEN" ]; then
    echo "⚠️  HF_TOKEN or HF_API_TOKEN not set"
fi

# Create output directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="output/parallel_runs_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Models to run (based on API access test results)
# Accessible models:
# - OpenAI: gpt-4o, gpt-5, o3-mini, o3
# - DeepSeek API: deepseek-r1-api, deepseek-v3-api
# - Anthropic: claude-sonnet-4.5
# - Gemini: gemini-2.5-pro (2.0-flash-exp has quota issues)
# - HuggingFace: kimi-thinking, llama-3.1-70b, qwen-2.5-32b
MODELS=(
    "gpt-4o"
    "gpt-5"
    "o3-mini"
    "claude-sonnet-4.5"
    "deepseek-r1-api"
    "deepseek-v3-api"
    "kimi-thinking"
    "llama-3.1-70b"
    "qwen-2.5-32b"
)
# Note: gemini-2.5-pro has quota limits (2 requests/min free tier) - removed for now

# Configuration
PROBLEMS_FILE="problems_parsed.txt"
NUM_PROBLEMS=36
SAMPLES=5  # Default: 5 samples per problem
# No PHASE flag = runs both vanilla AND picasso phases

echo "Configuration:"
echo "  Problems: $NUM_PROBLEMS (all problems)"
echo "  Samples per problem: $SAMPLES"
echo "  Phase: BOTH (vanilla + picasso)"
echo "  Models: ${#MODELS[@]}"
echo "  Output: JSON + CSV"
echo ""

# Function to run a single model
run_model() {
    local model=$1
    local log_file="$OUTPUT_DIR/${model}_run.log"
    
    echo "Starting $model..."
    echo "  Log: $log_file"
    
    # Check if model process is already running
    if [ -f "$OUTPUT_DIR/${model}.pid" ]; then
        local old_pid=$(cat "$OUTPUT_DIR/${model}.pid" 2>/dev/null)
        if ps -p "$old_pid" > /dev/null 2>&1; then
            echo "  ⚠️  Model $model already running with PID $old_pid"
            echo "  Skipping (delete $OUTPUT_DIR/${model}.pid to restart)"
            return 1
        fi
    fi
    
    # Run both vanilla and picasso phases (no --vanilla-only or --picasso-only flag)
    python test_with_llm.py \
        --model "$model" \
        --problems "$PROBLEMS_FILE" \
        --num-problems "$NUM_PROBLEMS" \
        --samples "$SAMPLES" \
        > "$log_file" 2>&1 &
    
    local pid=$!
    
    # Wait a moment to check if process started successfully
    sleep 1
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo "  ❌ Failed to start $model (process died immediately)"
        echo "  Check log: $log_file"
        return 1
    fi
    
    echo "  PID: $pid"
    echo "$pid" > "$OUTPUT_DIR/${model}.pid"
    echo ""
    
    return 0
}

# Run all models in parallel
PIDS=()
FAILED_MODELS=()
for model in "${MODELS[@]}"; do
    if run_model "$model"; then
        # Get the PID from the pid file
        if [ -f "$OUTPUT_DIR/${model}.pid" ]; then
            pid=$(cat "$OUTPUT_DIR/${model}.pid" 2>/dev/null)
            if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
                PIDS+=($pid)
            fi
        fi
    else
        FAILED_MODELS+=("$model")
    fi
    # Small delay to avoid overwhelming the system
    sleep 2
done

# Save PIDs to file
if [ ${#PIDS[@]} -gt 0 ]; then
    printf '%s\n' "${PIDS[@]}" > "$OUTPUT_DIR/all_pids.txt"
fi

# Report any failures
if [ ${#FAILED_MODELS[@]} -gt 0 ]; then
    echo "⚠️  Failed to start ${#FAILED_MODELS[@]} model(s): ${FAILED_MODELS[*]}"
    echo ""
fi

echo "=========================================="
echo "All models started!"
echo "=========================================="
echo "Total models: ${#MODELS[@]}"
echo "PIDs saved to: $OUTPUT_DIR/all_pids.txt"
echo "Logs directory: $OUTPUT_DIR"
echo ""
echo "To monitor progress:"
echo "  tail -f $OUTPUT_DIR/*_run.log"
echo ""
echo "To check status:"
echo "  ps -p \$(cat $OUTPUT_DIR/all_pids.txt | tr '\n' ',')"
echo ""
echo "To stop all processes:"
echo "  kill \$(cat $OUTPUT_DIR/all_pids.txt)"
echo ""

# Check initial status
echo ""
echo "Initial status check..."
COMPLETED_PIDS=()
REMAINING_PIDS=()
for pid in "${PIDS[@]}"; do
    if ps -p "$pid" > /dev/null 2>&1; then
        REMAINING_PIDS+=($pid)
    else
        COMPLETED_PIDS+=($pid)
    fi
done

if [ ${#COMPLETED_PIDS[@]} -gt 0 ]; then
    echo "✅ ${#COMPLETED_PIDS[@]} process(es) already completed: ${COMPLETED_PIDS[*]}"
fi
if [ ${#REMAINING_PIDS[@]} -gt 0 ]; then
    echo "⏳ ${#REMAINING_PIDS[@]} process(es) still running: ${REMAINING_PIDS[*]}"
fi
echo ""

# Ask if user wants to wait
read -p "Wait for all processes to complete? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Waiting for remaining processes..."
    
    # Wait for processes that are still running
    for pid in "${REMAINING_PIDS[@]}"; do
        if ps -p "$pid" > /dev/null 2>&1; then
            wait $pid
            echo "Process $pid completed"
        fi
    done
    
    echo ""
    echo "=========================================="
    echo "All processes completed!"
    echo "=========================================="
    echo "Total completed: ${#PIDS[@]} processes"
else
    echo "Processes running in background. Check logs in $OUTPUT_DIR"
    echo ""
    echo "To check status later:"
    echo "  ps -p \$(cat $OUTPUT_DIR/all_pids.txt | tr '\n' ',')"
fi

