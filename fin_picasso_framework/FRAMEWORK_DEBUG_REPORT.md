# Framework Debug Report

## Current Issues Identified

### 1. ❌ **Pilot Prompt Updater NOT Being Used**
**Problem**: `PilotPromptUpdater` is initialized but never called in the generation loop.

**Location**: `gen_data_validated.py:1245`
- Created: `pilot_prompt_updater = PilotPromptUpdater() if ENABLE_DYNAMIC_PILOT_UPDATES else None`
- **But never used** in `generate_with_validation()` or retry logic

**Impact**: 
- Pilot rules are not being updated dynamically
- Errors are not being learned from
- Same mistakes repeat across iterations

**Fix Needed**: 
- Call `pilot_prompt_updater.analyze_failures()` after pass@3 failures
- Use `pilot_prompt_updater.get_updated_pilot_prompt()` to get updated prompt
- Integrate updated prompt into retry logic

### 2. ⚠️ **API Rate Limiting Issues**
**Problem**: Kimi2 API hitting rate limits (429) and timeouts (504)

**Current Status**:
- Retry logic exists (3 retries with exponential backoff)
- But may need longer delays for rate limits
- No rate limit detection/backoff strategy

**Fix Needed**:
- Add specific handling for 429 errors with longer backoff
- Implement request queuing/throttling
- Add rate limit detection and adaptive delays

### 3. ✅ **Code Extraction Working**
**Status**: Code extraction from markdown/reasoning blocks is working correctly.

**Evidence**: Generated code files show proper extraction from `<think>` blocks.

### 4. ⚠️ **Unicode/Code Cleaning**
**Status**: Code cleaning function exists and is being called.

**Location**: `gen_data_validated.py:779` - `_clean_generated_code(code)`

**Need to Verify**: 
- Check if unicode issues are actually occurring
- Verify cleaning is catching all cases

### 5. ❌ **No Pass@3 Failure Analysis**
**Problem**: After 3 samples fail, framework should analyze patterns but doesn't.

**Expected Behavior**:
- After pass@3 (3 samples all fail), call `pilot_prompt_updater.analyze_failures()`
- Update pilot rules based on common errors
- Apply updates for next problem

**Current Behavior**: No analysis happens after pass@3 failures.

### 6. ⚠️ **Feedback Generator Integration**
**Status**: `FeedbackGenerator` is being used in retry logic.

**Location**: `gen_data_validated.py:731-740`

**Need to Verify**:
- Is feedback detailed enough?
- Are examples being included?
- Is feedback helping LLM fix errors?

## Current Test Results

### Checkpoint Summary (from monitor):
```
pilot       :   5 pass,   5 fail ( 50.0% pass rate)
pnr         :   1 pass,   0 fail (100.0% pass rate)
drc         :   1 pass,   0 fail (100.0% pass rate)
sax         :   0 pass,   1 fail (  0.0% pass rate)
```

### Observations:
1. **Pilot validation catching 50% of errors** - Good, but could be better
2. **P&R and DRC passing** - Framework validation working
3. **SAX failing** - Need to check why (likely missing models or routing issues)

## Recommended Fixes

### Priority 1: Integrate Pilot Prompt Updater
1. Add failure tracking per problem
2. After pass@3, analyze failures
3. Update pilot rules
4. Use updated prompt for next problem

### Priority 2: Improve Rate Limiting
1. Add 429-specific handling with longer backoff
2. Implement request throttling
3. Add rate limit detection

### Priority 3: Verify Code Quality
1. Check for unicode issues in generated code
2. Verify code cleaning is comprehensive
3. Check if prompts are causing issues

### Priority 4: Enhance Feedback
1. Review feedback quality
2. Add more examples
3. Verify feedback is actionable

## Next Steps

1. **Fix pilot prompt updater integration** (CRITICAL)
2. **Add rate limiting improvements**
3. **Review and enhance feedback quality**
4. **Monitor SAX failures and fix root cause**


