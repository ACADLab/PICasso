#!/bin/bash
# Monitoring script for test run

LOG_FILE="fin_picasso_framework/test_run_monitor.log"
RULES_FILE="fin_picasso_framework/pilot_rules.json"

echo "=========================================="
echo "PICasso Framework Test Monitor"
echo "=========================================="
echo ""

# Check if test is running
if pgrep -f "test_with_model.py" > /dev/null; then
    echo "✅ Test is RUNNING"
    PID=$(pgrep -f "test_with_model.py" | head -1)
    echo "   PID: $PID"
    ps -p $PID -o etime= | awk '{print "   Runtime:", $0}'
else
    echo "❌ Test is NOT running"
fi

echo ""
echo "--- Progress ---"
TOTAL_SAMPLES=$(grep -c "Sample.*/" "$LOG_FILE" 2>/dev/null || echo "0")
echo "Samples started: $TOTAL_SAMPLES"

PASSED=$(grep -c "PASSED" "$LOG_FILE" 2>/dev/null || echo "0")
FAILED=$(grep -c "FAILED" "$LOG_FILE" 2>/dev/null || echo "0")
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [ "$PASSED" -gt 0 ] || [ "$FAILED" -gt 0 ]; then
    TOTAL=$((PASSED + FAILED))
    SUCCESS_RATE=$(echo "scale=1; $PASSED * 100 / $TOTAL" | bc 2>/dev/null || echo "0")
    echo "Success rate: ${SUCCESS_RATE}%"
fi

echo ""
echo "--- Latest Activity ---"
tail -5 "$LOG_FILE" 2>/dev/null | grep -E "Problem|Sample|Attempt|PASSED|FAILED|Pass@" || echo "No recent activity"

echo ""
echo "--- Errors Detected ---"
ERROR_COUNT=$(grep -iE "syntax|error|failed" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
echo "Error mentions: $ERROR_COUNT"

echo ""
echo "--- Pilot Rules ---"
if [ -f "$RULES_FILE" ]; then
    RULE_COUNT=$(python3 -c "import json; f=open('$RULES_FILE'); d=json.load(f); print(len(d.get('custom_patterns', [])))" 2>/dev/null || echo "0")
    echo "✅ Pilot rules file exists"
    echo "   Rules learned: $RULE_COUNT"
    if [ "$RULE_COUNT" -gt 0 ]; then
        echo "   Latest rules:"
        python3 -c "import json; f=open('$RULES_FILE'); d=json.load(f); [print(f'   - {r[:80]}...') for r in d.get('custom_patterns', [])[-3:]]" 2>/dev/null || echo "   (Could not parse)"
    fi
else
    echo "❌ No pilot rules file yet (will be created after first failure)"
fi

echo ""
echo "--- Recent Errors (last 5) ---"
grep -iE "syntax|error|failed|missing|unmatched" "$LOG_FILE" 2>/dev/null | tail -5 || echo "No errors found"

echo ""
echo "=========================================="
echo "Last updated: $(date)"
echo "=========================================="
