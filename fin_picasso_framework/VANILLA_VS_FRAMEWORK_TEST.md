# Vanilla vs Framework Comparison Test

## Test Configuration

- **Model**: DeepSeek-R1
- **Problems File**: `test_problems.txt` (8 problems)
- **Samples per problem**: 3
- **Test Mode**: Two-phase comparison

## Phase 1: Vanilla LLM (No Framework)

### Features DISABLED:
- ❌ Auto-correction: OFF
- ❌ YAML validation: OFF  
- ❌ Dynamic pilot updates: OFF
- ✅ Component injection: ON (for Phase 1 baseline tracking)
- ✅ Pilot validation: ON (syntax check only)

### What This Tests:
- Raw LLM capability without framework assistance
- Baseline pass@k calculation
- What errors occur without auto-correction

### Expected Behavior:
- LLM generates code
- Code executes (or fails)
- No automatic fixes applied
- Results saved for comparison

## Phase 2: PICasso Framework (With All Features)

### Features ENABLED:
- ✅ Auto-correction: ON
- ✅ YAML validation: ON
- ✅ Component injection: ON
- ✅ Pilot validation: ON (full checks)
- ✅ Dynamic pilot updates: ON

### What This Tests:
- Framework's ability to fix vanilla failures
- Improvement in pass@k with framework
- Auto-correction effectiveness

### Expected Behavior:
- LLM generates code
- Framework detects errors
- Auto-correction fixes issues
- YAML validation catches routing problems
- Results saved for comparison

## Comparison Metrics

### Pass@k Calculation:
- **Pass@1**: Success rate on first attempt
- **Pass@3**: Success rate within 3 attempts
- **Pass@5**: Success rate within 5 attempts (if applicable)

### Success Criteria:
- Component created successfully
- P&R validation passed
- DRC validation passed (if KLayout available)
- SAX validation passed

## Running the Tests

### Vanilla Test:
```bash
python fin_picasso_framework/test_with_model.py \
    --model deepseek_r1 \
    --problems test_problems.txt \
    --samples 3 \
    --vanilla
```

### Framework Test:
```bash
python fin_picasso_framework/test_with_model.py \
    --model deepseek_r1 \
    --problems test_problems.txt \
    --samples 3
```

### Both Tests (Automated):
```bash
./fin_picasso_framework/run_comparison_tests.sh
```

## Results

Results are saved to:
- `fin_picasso_framework/results_vanilla.log` - Vanilla test output
- `fin_picasso_framework/results_framework.log` - Framework test output
- `fin_picasso_framework/output/results/` - CSV results files

## Analysis

After both tests complete, compare:
1. **Pass@k rates**: Vanilla vs Framework
2. **Error types**: What errors occur in vanilla that framework fixes
3. **Auto-correction success**: How many issues were auto-fixed
4. **YAML validation impact**: How many routing issues caught early

