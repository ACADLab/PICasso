# PICasso TODO: Optimization + Validation Integration

**Target**: Complete all high-priority tasks THIS WEEK (3-5 days)

**Last Updated**: Nov 3, 2025

---

## ✅ **COMPLETED** (As of Nov 3)

### Infrastructure & Integration
- [x] Checkout `deepak_v` branch
- [x] Copy all optimization files from `optimization` branch
  - [x] `s_optimize.py` - Device-level S-matrix optimization
  - [x] `gf_optimize.py` - GDSFactory circuit optimization
  - [x] `netlist_optimize.py` - SAX netlist optimization
  - [x] `optimizie_circuit_loss.py` - SVD-based circuit loss optimization
  - [x] `optical_optimize.py` - High-level optimization interface
  - [x] Demo files (`demo_mzi.py`, `demo_netlist.py`, `custom_models.py`)

### New Modules Created
- [x] `hf_inference_workflow/optimization_integration.py`
  - OptimizationStage class for post-validation optimization
  - Automatic tunable parameter extraction from netlists
  - SAX-based phase optimization
- [x] `hf_inference_workflow/validators/loss_target_validator.py`
  - Target-based insertion loss validation
  - Feedback generation for LLM retry
  - CSV metrics export
- [x] `hf_inference_workflow/config_loss_targets.py`
  - Complete target loss database from Updated_Loss_Values.pptx
  - 20+ circuits with research-based target values
  - Automatic circuit type detection from descriptions

### Configuration Updates
- [x] Enhanced `hf_inference_workflow/config.py`
  - Added optimization settings (max_iter, restarts, timeout)
  - Added loss target validation settings
  - Added local GPU model configuration
  - Model caching directory setup
- [x] Updated `hf_models/hf_gen_data.py`
  - Default to local GPU models (`ENGINE = 'hf'`)
  - Clear documentation of local vs. API inference
- [x] Enhanced `hf_models/hf_agent.py`
  - Multi-GPU auto-detection and logging
  - Model caching support
  - GPU memory monitoring
  - Better error handling

---

## 🔥 **HIGH PRIORITY** (Complete within 2-3 days)

### Core Workflow Integration
- [ ] **Modify `hf_inference_workflow/gen_data_validated.py`** (CRITICAL)
  - [ ] Import optimization modules (OptimizationStage, LossTargetValidator)
  - [ ] Add optimization stage after SAX validation
  - [ ] Add loss target validation after optimization
  - [ ] Update retry handler to include optimization/loss feedback
  - [ ] Add new columns to CSV output:
    - `il_before_db`, `il_after_db`, `il_improvement_db`
    - `loss_target_db`, `meets_loss_target`, `loss_margin_db`
  - [ ] Update progress logging to show optimization status

### Testing & Validation
- [ ] **Test basic optimization workflow** (1-2 hours)
  - [ ] Test MZM design: Generate → Validate → Optimize → Check Loss
  - [ ] Verify optimization runs without errors
  - [ ] Check CSV output has new columns
  - [ ] Verify GDS files are saved correctly
  - [ ] Time each stage (generation, validation, optimization)

- [ ] **GPU Cluster Setup & Testing** (2-4 hours)
  - [ ] Test on GPU cluster with DeepSeek-R1-Distill-Qwen-14B
  - [ ] Verify multi-GPU detection and allocation
  - [ ] Benchmark generation speed (designs per hour)
  - [ ] Test with different models (Qwen2.5-Coder if available)
  - [ ] Monitor GPU memory usage during batch generation

- [ ] **Small-Scale Batch Test** (2-3 hours)
  - [ ] Run 10 designs with full pipeline (validate + optimize)
  - [ ] Analyze success rates:
    - P&R pass rate
    - DRC pass rate
    - SAX pass rate
    - Optimization success rate
    - Loss target compliance rate
  - [ ] Generate metrics report (CSV analysis)
  - [ ] Identify any bottlenecks or failures

---

## 📊 **MEDIUM PRIORITY** (Complete within 3-5 days)

### Advanced Features
- [ ] **Add optimization metrics visualization** (Optional, 2-3 hours)
  - [ ] Create script to plot IL before/after histograms
  - [ ] Generate loss target compliance charts
  - [ ] Plot optimization improvement vs. circuit type
  - [ ] Save visualizations to `output/metrics/`

- [ ] **Enhance retry handler for optimization** (2-3 hours)
  - [ ] Add specific feedback for IL > target
  - [ ] Suggest component-level changes (fewer components, lower-loss couplers)
  - [ ] Track retry reasons in CSV (validation_fail vs loss_target_fail)

- [ ] **Add wavelength-dependent loss analysis** (Optional, 3-4 hours)
  - [ ] Extend optimization to wavelength sweeps
  - [ ] Add flatness metrics (variance across wavelength)
  - [ ] Report bandwidth at target IL threshold

### Full-Scale Testing
- [ ] **Large Batch Test** (4-6 hours)
  - [ ] Run 50-100 designs across all 20 circuit types
  - [ ] Generate comprehensive metrics CSV
  - [ ] Analyze per-circuit-type performance
  - [ ] Identify which circuits need improvement
  - [ ] Document failure modes

---

## 📚 **DOCUMENTATION** (Complete within 1-2 days)

### Core Documentation Files
- [x] `TODO.md` - This file
- [ ] **`FUTURE_WORK.md`** - Long-term roadmap (1 hour)
  - [ ] Research directions
  - [ ] Advanced optimization techniques
  - [ ] Model fine-tuning plans
  - [ ] Scalability improvements

- [ ] **`GPU_CLUSTER_SETUP.md`** - Detailed setup guide (1-2 hours)
  - [ ] Hardware requirements
  - [ ] CUDA/PyTorch installation
  - [ ] Model download and caching
  - [ ] Multi-GPU configuration
  - [ ] Troubleshooting common issues
  - [ ] Performance benchmarks

- [ ] **Update `README.md`** - Add new sections (1 hour)
  - [ ] Optimization framework overview
  - [ ] Loss target validation explanation
  - [ ] GPU cluster quick start
  - [ ] Updated workflow diagram
  - [ ] Performance metrics

### Additional Documentation
- [ ] **`OPTIMIZATION_GUIDE.md`** - Detailed optimization guide (Optional, 1-2 hours)
  - [ ] How the optimization framework works
  - [ ] Tunable parameters and their effects
  - [ ] Optimization algorithms explained
  - [ ] Tips for better optimization results

- [ ] **`METRICS_GUIDE.md`** - Metrics interpretation (Optional, 30 min)
  - [ ] CSV column explanations
  - [ ] How to analyze results
  - [ ] Success criteria definitions

---

## 🎯 **SUCCESS CRITERIA** (End of Week)

### ✅ **Functionality**
- [ ] Full pipeline operational: Generate → P&R → DRC → SAX → Optimize → Loss Check
- [ ] Successfully generate 20+ validated + optimized designs
- [ ] At least 60% of designs meet loss targets after optimization
- [ ] Pipeline runs on GPU cluster without errors

### ✅ **Performance**
- [ ] Generate 20 designs in < 2 hours on GPU cluster
- [ ] 80%+ pass P&R/DRC/SAX validation
- [ ] Average optimization time < 2 minutes per design
- [ ] GPU memory usage < 90% per device

### ✅ **Documentation**
- [ ] Complete and tested TODO.md
- [ ] FUTURE_WORK.md with research directions
- [ ] GPU_CLUSTER_SETUP.md with step-by-step guide
- [ ] Updated README.md with new workflow

### ✅ **Deliverables**
- [ ] Validated + optimized GDS files
- [ ] Comprehensive metrics CSV with IL data
- [ ] Performance benchmarks (timing, success rates)
- [ ] Production-ready codebase on `deepak_v`

---

## 🐛 **KNOWN ISSUES & BLOCKERS**

### Current Issues
- [ ] SAX loss calculation may fail for complex circuits → Fallback to target-only validation
- [ ] Optimization may timeout on very large circuits (>50 components) → Add timeout handling
- [ ] Some circuits have no tunable parameters → Skip optimization gracefully

### Potential Blockers
- [ ] GPU cluster access/configuration
- [ ] Model download bandwidth (DeepSeek is ~28GB)
- [ ] SAX/gplugins compatibility with newer GDSFactory versions

**Mitigation Plan**: Document workarounds in GPU_CLUSTER_SETUP.md, provide fallback options

---

## 📝 **NOTES**

### Timeline
- **Day 1-2**: Complete workflow integration + basic testing
- **Day 3**: GPU cluster setup + batch testing
- **Day 4-5**: Full-scale testing + documentation + polish

### Key Contacts
- **Optimization Framework**: See `s_optimize.py`, `optimizie_circuit_loss.py`
- **Validation**: See `hf_inference_workflow/validators/`
- **GPU Setup**: See `GPU_CLUSTER_SETUP.md` (to be created)

### References
- Loss targets: `Updated_Loss_Values.pptx` → `config_loss_targets.py`
- Optimization demos: `demo_mzi.py`, `demo_netlist.py`
- Workflow docs: `hf_inference_workflow/README.md`

---

**Last updated**: Nov 3, 2025
**Next review**: After core workflow integration complete
