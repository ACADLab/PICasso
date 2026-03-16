# Iterative YAML-Based Routing/Placement Fixes

## Implementation

### New Module: `yaml_routing_fixer.py`
- **Function**: `fix_routing_and_placement_iterative()`
- **Strategy**: 3 iterations with increasing spacing multipliers
- **Process**:
  1. Extract netlist from component
  2. Convert to YAML
  3. Apply spacing multiplier (1.5x, 2.0x, 2.5x)
  4. Rebuild using `gf.read.from_yaml()` (automatic routing)
  5. Test if routing collision resolved
  6. If not, increase spacing and retry

### Integration
- **Location**: `gen_data_validated.py` - After Python execution, before validation
- **Trigger**: Runs for every pass@k attempt when component is created
- **Iterations**: 3 iterations per attempt
- **Spacing Multipliers**: 1.5x → 2.0x → 2.5x

## Prompt Updates

### Base Pilot Restrictions Added
- **Port Connection Limitations**: Warns about "More than two connected optical ports" error
- **Solution**: Connect ports one-to-one, use intermediate routing
- **Spacing Guidelines**: 200um+ for dense layouts
- **Framework Auto-Fix**: Mentions iterative YAML-based fixes

### Prompt Template Updates
- Added warning about multi-port connection limitations
- Added guidance on avoiding fan-out connections
- Added note about framework's automatic iterative fixes

## Testing Configuration

- **Problems**: 4 problems (for debugging)
- **Samples**: 3 per problem
- **Model**: DeepSeek-R1
- **Auto-terminate**: If framework doesn't work after 4 problems, process terminates

## Expected Behavior

1. **After Python Execution**:
   - Component created successfully
   - YAML iterative fixes triggered (3 iterations)
   - Spacing increased: 1.5x → 2.0x → 2.5x
   - Routing collision resolved if possible

2. **Log Messages**:
   - "🔄 Attempting iterative YAML-based routing/placement fixes (3 iterations)..."
   - "🔄 YAML routing/placement fix iteration 1/3 (spacing: 1.5x)"
   - "✅ Iteration X successful - routing collision resolved!"
   - Or: "⚠️ Iteration X still has routing issues"

3. **Pilot Prompt**:
   - Includes base restrictions about port limitations
   - Includes learned rules from failures
   - Updated after each pass@k failure

## Debugging

To check if pilot prompt is updated:
- Look for "=== PILOT RESTRICTIONS ===" in logs
- Check "=== LEARNED RULES ===" section
- Verify base restrictions about multi-port connections are present

