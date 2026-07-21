#!/bin/bash
# Run all four Complexity 3 problems and collect results.

set -e

PYTHON=/opt/homebrew/bin/python3.11
SCRIPT=test_with_llm.py
PROBLEMS=problems_parsed.txt
SAMPLES=3
MODEL=gpt-4o-mini

cd "$(dirname "$0")"
source ../.env && export OPENAI_API_KEY

echo "======================================================"
echo "C3 Benchmark — 4 problems, ${SAMPLES} samples each"
echo "======================================================"

for TASK in 6 11 20 25; do
  echo ""
  echo ">>> Task ${TASK}"
  $PYTHON $SCRIPT \
    --model $MODEL \
    --problems $PROBLEMS \
    --start-problem $TASK \
    --num-problems $TASK \
    --samples $SAMPLES \
    --compare
done

echo ""
echo "======================================================"
echo "All C3 problems complete."
echo "======================================================"
