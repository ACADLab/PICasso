# Automatic Routing Collision Handling - Implementation Summary

## Problem
The LLM-generated Python code was causing routing collisions when components were placed too close together, resulting in execution errors like:
```
Execution error: Routing collision in Unnamed_0
```

## Solution Implemented

### 1. Enhanced Error Detection (`gen_data_validated.py`)

**Added specific error categorization in `parse_and_execute_code()`:**
- `ROUTING_COLLISION` - Waveguide overlap from insufficient spacing
- `MIRROR_ERROR` - Incorrect mirror() method usage
- `PORT_ERROR` - Invalid or missing port names
- `SYNTAX_ERROR` - Python syntax issues
- `EXECUTION_ERROR` - Generic execution failures

**Returns detailed error messages** that enable targeted retry feedback.

### 2. Intelligent Error Feedback (`get_parsing_error_feedback()`)

**Routing Collision Feedback:**
```
Required Fixes:
  1. INCREASE ALL SPACING: Components must be at least 50µm apart (minimum 30µm)
  2. VERTICAL SEPARATION: For stacked components, use ±40µm or more vertical offset
  3. HORIZONTAL SPACING: Place components 100-200µm apart horizontally
  4. ROUTE PLANNING: Ensure route paths don't cross or overlap
  5. USE LARGER BEND RADIUS: radius=15 (instead of 10) for gentler curves

Example Fix for 8-QAM:
  - MZMs vertically spaced: y-positions at 0, 120, 240 (not 0, 100, 200)
  - MMIs horizontal offset: x=400+ (not 300)
  - Phase shifters with ±50µm vertical offset (not ±30µm)
```

### 3. Enhanced Retry Handler (`retry_handler.py`)

**Updated `format_feedback_for_llm()` to detect and handle routing collisions:**
- Detects `ROUTING_COLLISION` error type from parsing reports
- Provides detailed spacing requirements
- Emphasizes critical nature of spacing issues
- Gives specific numerical guidance (50µm minimum, ±50µm vertical offset, 150µm horizontal)

### 4. Improved Prompt Template (`config.py`)

**Added explicit spacing rules:**
```python
CRITICAL SPACING RULES (prevents routing collisions):
  * Minimum 50µm spacing between ALL components (use 80-150µm for complex designs)
  * For vertical stacking: minimum ±50µm vertical offset between components
  * For horizontal placement: minimum 150µm horizontal separation
  * Use bend radius >= 15µm for all routes (larger is safer)
  * Use route separation >= 15µm in route_bundle calls
```

**Updated example with better spacing:**
```python
ps1.move((100, 50))  # Good vertical spacing (±50µm prevents collisions)
ps2.move((100, -50))  # Good vertical spacing (±50µm prevents collisions)
```

## How It Works

### Automatic Retry Flow:

1. **LLM generates code** → Execution attempted
2. **Routing collision detected** → Error categorized as `ROUTING_COLLISION`
3. **Detailed feedback generated** → Specific spacing requirements provided
4. **Retry with feedback** → LLM receives:
   - Error type and details
   - Specific numerical spacing requirements
   - Example fixes for the specific circuit
   - Updated constraints (50µm minimum, ±50µm vertical, 150µm horizontal)
5. **LLM regenerates with better spacing** → Should now pass execution
6. **If still fails** → Retry up to MAX_RETRY_ATTEMPTS (default 3)

### Key Improvements:

**Before:**
- Generic "Execution error: Routing collision" message
- No specific guidance on fixing
- LLM would retry with similar spacing → repeat failures

**After:**
- Specific error categorization
- Detailed numerical spacing requirements
- Circuit-specific examples (e.g., 8-QAM positioning)
- Emphasis on critical nature of spacing
- Clear before/after guidance

## Testing

### Test with 8-QAM Circuit:
```bash
# Run the demo notebook
jupyter notebook demo_full_framework.ipynb
```

**Expected behavior:**
1. First attempt may have routing collision
2. System detects `ROUTING_COLLISION` error
3. Provides detailed spacing feedback to LLM
4. LLM regenerates with better spacing (50µm+, ±50µm vertical, 150µm horizontal)
5. Second attempt should succeed

### Monitor retry logs:
```python
logger.info(f"Failed to parse/execute code: {error_msg}")  # Shows error type
logger.warning(f"Validation failed at stage: {failed_stage.value}")  # Shows retry trigger
```

## Files Modified

1. **`hf_inference_workflow/gen_data_validated.py`**
   - Enhanced `parse_and_execute_code()` to return (component, error_msg)
   - Added `get_parsing_error_feedback()` for error-specific guidance
   - Updated caller to use detailed error messages in retry feedback

2. **`hf_inference_workflow/retry_handler.py`**
   - Enhanced `format_feedback_for_llm()` with routing collision detection
   - Added specific feedback for ROUTING_COLLISION, MIRROR_ERROR, PORT_ERROR
   - Provides numerical spacing requirements and circuit-specific examples

3. **`hf_inference_workflow/config.py`**
   - Updated PYTHON_PROMPT_TEMPLATE with explicit spacing rules
   - Changed minimum spacing from 20µm → 50µm
   - Added vertical offset requirements (±50µm)
   - Added horizontal separation requirements (150µm)
   - Updated example with better spacing (±30µm → ±50µm)

## Performance Impact

- **No additional API calls** - uses existing retry mechanism
- **Same number of retries** - just better targeted feedback
- **Higher success rate expected** - more specific guidance reduces trial-and-error
- **Better quality layouts** - enforces generous spacing from the start

## Future Enhancements (Optional)

1. **Fallback to router.py**: If collision persists after retries, convert code to use `get_route()` instead of `route_bundle()`
2. **Automated spacing analyzer**: Pre-analyze component positions before execution
3. **Dynamic spacing adjustment**: Automatically increase spacing based on circuit complexity
4. **Learning from failures**: Track which spacing values work best for different circuit types

## Configuration

Current settings in `config.py`:
```python
MAX_RETRY_ATTEMPTS = 3  # Maximum retry attempts
SAMPLES_PER_PROBLEM = 2  # Samples generated per problem

# Spacing guidelines in prompt:
MIN_SPACING = 50  # µm (in prompt guidance)
VERTICAL_OFFSET = ±50  # µm (in prompt guidance)
HORIZONTAL_SEPARATION = 150  # µm (in prompt guidance)
```

Adjust these values if needed for your PDK requirements.
