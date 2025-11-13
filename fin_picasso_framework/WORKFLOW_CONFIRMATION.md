# PICasso Framework Workflow Confirmation

## ✅ Confirmed Workflow

### **Phase 1: Vanilla LLM (Pass@3)**
- **Samples**: 3 attempts per problem (pass@3)
- **Prompt**: `VANILLA_LLM_PROMPT` (no component injection, no pilot prompt, no framework enhancements)
- **Purpose**: Baseline comparison - raw LLM performance
- **Tracking**: Results saved separately in `RAW_LLM_RESULTS`
- **Retries**: NO retries for Phase 1 (first attempt only)

### **Phase 2: Framework (Pass@3 with Retries)**
- **Samples**: 3 attempts per problem (pass@3)
- **Prompt**: Framework-enhanced prompt with:
  - ✅ **Pilot prompt** (pre-execution validation rules)
  - ✅ **Component injection** (with SAX information)
  - ✅ **Smart error feedback** (enhanced feedback generator)
  - ✅ **Dynamic pilot prompt updates** (after pass@3 failures)
- **Retries**: Up to 3 retries per sample (MAX_RETRY_ATTEMPTS = 3)
- **Tracking**: Results saved separately in `FRAMEWORK_RESULTS`

### **Validation Stages (In Order)**

1. **Pilot Validation** (Pre-execution)
   - ✅ Syntax checks
   - ✅ Mirror errors
   - ✅ Spacing violations
   - ✅ Port errors
   - ✅ Non-existent components (e.g., mmi2x1)
   - ✅ Routing errors

2. **Code Execution** (Parse & Execute)
   - ✅ Parse Python code
   - ✅ Execute to create GDSFactory component
   - ✅ Handle execution errors

3. **Place & Route (P&R) Validation**
   - ✅ Component overlap detection
   - ✅ Routing collision detection
   - ✅ Port alignment checks
   - ✅ Minimum spacing validation

4. **DRC (Design Rule Check)**
   - ✅ KLayout DRC validation
   - ✅ Foundry design rules
   - ✅ Manufacturing constraints

5. **SAX Validation** ✅ **ENABLED**
   - ✅ SAX compilation check
   - ✅ Routing correctness
   - ✅ Port alignment in SAX netlist
   - ✅ Missing model detection

6. **Functional Validation**
   - ✅ Port declaration checks
   - ✅ Circuit behavior verification
   - ✅ Specification matching

7. **Optimization** (If enabled)
   - ✅ Device-level optimization
   - ✅ Circuit-level optimization
   - ✅ Loss target validation

### **Pilot Prompt Updates**

- **Trigger**: After all 3 samples fail for a problem (pass@3 complete failure)
- **Action**: 
  - Analyze failure patterns
  - Update pilot rules dynamically
  - Apply updated prompt for subsequent problems
- **Verification**: Robustness check after updates

### **Configuration**

```python
# From config.py
SAMPLES_PER_PROBLEM = 3          # Pass@3
MAX_RETRY_ATTEMPTS = 3           # 3 retries per sample in Phase 2
ENABLE_TWO_PHASE_TRACKING = True # Track Phase 1 vs Phase 2 separately
ENABLE_SAX_CHECK = True          # ✅ SAX enabled
ENABLE_FUNCTIONAL_VALIDATION = True
ENABLE_OPTIMIZATION = True
ENABLE_DYNAMIC_PILOT_UPDATES = True
```

## Workflow Diagram

```
For each problem:
  For each sample (1 to 3):
    
    ┌─────────────────────────────────────┐
    │  PHASE 1: Vanilla LLM (attempt 0)  │
    │  - No component injection           │
    │  - No pilot prompt                  │
    │  - No framework enhancements        │
    │  - NO RETRIES                       │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  Pilot Validation                   │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  Code Execution                     │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  P&R Validation                     │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  DRC Validation                     │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  SAX Validation ✅                  │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  Functional Validation              │
    └─────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────┐
    │  Optimization (if enabled)          │
    └─────────────────────────────────────┘
    
    If failed → PHASE 2 (attempts 1-3):
    
    ┌─────────────────────────────────────┐
    │  PHASE 2: Framework (attempts 1-3)  │
    │  - Component injection (with SAX)   │
    │  - Pilot prompt                     │
    │  - Smart error feedback             │
    │  - Up to 3 retries                  │
    └─────────────────────────────────────┘
              ↓
    [Same validation stages as above]
    
    After all 3 samples for problem:
      If all failed → Update pilot prompt
      → Use updated prompt for next problem
```

## Key Points

1. ✅ **Phase 1 (Vanilla)**: Pass@3, NO retries, baseline comparison
2. ✅ **Phase 2 (Framework)**: Pass@3, up to 3 retries per sample, with all enhancements
3. ✅ **Validation Order**: Pilot → Execute → P&R → DRC → SAX → Functional → Optimization
4. ✅ **SAX Enabled**: `ENABLE_SAX_CHECK = True`
5. ✅ **Pilot Updates**: After pass@3 failures, updates apply to next problem
6. ✅ **Component Injection**: Includes SAX information and creation instructions
7. ✅ **Smart Feedback**: Enhanced feedback generator with detailed examples

## Status: ✅ CONFIRMED

The workflow matches your description exactly!


