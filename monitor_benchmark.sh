#!/bin/bash
# Monitor benchmark progress

echo "==================================================================="
echo "BENCHMARK MONITOR"
echo "==================================================================="
echo "Started at: $(date)"
echo ""

while true; do
    clear
    echo "==================================================================="
    echo "BENCHMARK PROGRESS - $(date)"
    echo "==================================================================="

    # Check if process is running
    if pgrep -f "run_full_benchmark_36.py" > /dev/null; then
        echo "✅ Benchmark is RUNNING"
    else
        echo "⚠️  Benchmark is NOT running"
        echo ""
        echo "Last 50 lines of log:"
        tail -50 benchmark_run_final.log 2>/dev/null || echo "No log file found"
        break
    fi

    echo ""
    echo "-------------------------------------------------------------------"
    echo "LOG FILE STATUS:"
    echo "-------------------------------------------------------------------"
    ls -lh benchmark_run_final.log 2>/dev/null || echo "Log file not found"

    echo ""
    echo "-------------------------------------------------------------------"
    echo "LATEST OUTPUT (last 30 lines):"
    echo "-------------------------------------------------------------------"
    tail -30 benchmark_run_final.log 2>/dev/null || echo "No output yet..."

    echo ""
    echo "-------------------------------------------------------------------"
    echo "CSV FILES:"
    echo "-------------------------------------------------------------------"
    ls -lh hf_inference_workflow/output/results/*.csv 2>/dev/null | tail -5 || echo "No CSV files yet"

    echo ""
    echo "Press Ctrl+C to stop monitoring"
    echo "Next update in 30 seconds..."
    sleep 30
done
