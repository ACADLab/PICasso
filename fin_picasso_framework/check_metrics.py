"""
Quick script to check current test metrics and results
"""

import sys
from pathlib import Path
import json
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import metrics calculation
try:
    from hf_inference_workflow.metrics import estimate_pass_at_k
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    print("⚠️  Metrics module not available")

# Check log file
log_file = Path(__file__).parent / "results_framework.log"
if log_file.exists():
    print(f"📊 Analyzing log file: {log_file}")
    print("=" * 70)
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Count problems and samples
    problems_seen = set()
    samples_seen = set()
    phase1_passed = 0
    phase1_failed = 0
    phase2_passed = 0
    phase2_failed = 0
    auto_corrected = 0
    
    for line in lines:
        # Extract problem/sample info
        if "Problem" in line and "Sample" in line:
            match = re.search(r'Problem (\d+).*Sample (\d+)', line)
            if match:
                prob, samp = match.groups()
                problems_seen.add(int(prob))
                samples_seen.add((int(prob), int(samp)))
        
        # Count Phase 1 results
        if "Phase 1 (Raw LLM): ✅ PASSED" in line:
            phase1_passed += 1
        elif "Phase 1 (Raw LLM): ❌ FAILED" in line:
            phase1_failed += 1
        
        # Count Phase 2 results
        if "Phase 2 (Framework): ✅ PASSED" in line:
            phase2_passed += 1
        elif "Phase 2 (Framework): ❌ FAILED" in line:
            phase2_failed += 1
        
        # Count auto-corrections
        if "Auto-correction SUCCESS" in line or "auto-corrected" in line.lower():
            auto_corrected += 1
    
    print(f"📈 Current Progress:")
    print(f"   Problems processed: {len(problems_seen)}")
    print(f"   Samples processed: {len(samples_seen)}")
    print(f"")
    print(f"📊 Phase 1 (Vanilla LLM) Results:")
    print(f"   ✅ Passed: {phase1_passed}")
    print(f"   ❌ Failed: {phase1_failed}")
    if phase1_passed + phase1_failed > 0:
        phase1_rate = phase1_passed / (phase1_passed + phase1_failed) * 100
        print(f"   Pass Rate: {phase1_rate:.1f}%")
    print(f"")
    print(f"📊 Phase 2 (Framework) Results:")
    print(f"   ✅ Passed: {phase2_passed}")
    print(f"   ❌ Failed: {phase2_failed}")
    if phase2_passed + phase2_failed > 0:
        phase2_rate = phase2_passed / (phase2_passed + phase2_failed) * 100
        print(f"   Pass Rate: {phase2_rate:.1f}%")
    print(f"")
    print(f"🔧 Auto-Corrections:")
    print(f"   Successful fixes: {auto_corrected}")
    print(f"")
    
    # Check for errors
    errors = {}
    for line in lines:
        if "ERROR" in line or "FAILED" in line:
            error_type = "Unknown"
            if "ROUTING_COLLISION" in line:
                error_type = "Routing Collision"
            elif "SYNTAX" in line:
                error_type = "Syntax Error"
            elif "PORT" in line:
                error_type = "Port Error"
            elif "EXECUTION" in line:
                error_type = "Execution Error"
            
            errors[error_type] = errors.get(error_type, 0) + 1
    
    if errors:
        print(f"❌ Error Summary:")
        for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            print(f"   {error_type}: {count}")
    
    print("=" * 70)
    print(f"📄 Total log lines: {len(lines)}")
    print(f"📅 Last updated: {log_file.stat().st_mtime}")
    
else:
    print(f"❌ Log file not found: {log_file}")

# Check for CSV results
output_dir = Path(__file__).parent / "output" / "results"
if output_dir.exists():
    csv_files = list(output_dir.glob("*.csv"))
    if csv_files:
        print(f"\n📁 CSV Results Files:")
        for csv_file in csv_files:
            print(f"   {csv_file.name}")
            # Try to read and show summary
            try:
                import pandas as pd
                df = pd.read_csv(csv_file)
                print(f"      Rows: {len(df)}")
                if 'success' in df.columns:
                    success_count = df['success'].sum()
                    print(f"      Successful: {success_count}/{len(df)} ({success_count/len(df)*100:.1f}%)")
            except:
                pass
    else:
        print(f"\n📁 No CSV files found in {output_dir}")

