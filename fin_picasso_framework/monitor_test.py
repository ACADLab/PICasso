"""
Monitor Framework Test Progress

Shows real-time status of running tests, checkpoints, and results.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def monitor_test_progress():
    """Monitor test progress by checking checkpoints and results."""
    base_dir = Path(__file__).parent / "output" / "benchmark_results"
    
    print("=" * 70)
    print("PICASSO FRAMEWORK TEST MONITOR")
    print("=" * 70)
    print(f"Monitoring: {base_dir}")
    print()
    
    # Count checkpoints by stage and status
    stage_counts = defaultdict(lambda: {'pass': 0, 'fail': 0})
    
    for stage_dir in ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']:
        stage_path = base_dir / "checkpoints" / stage_dir
        if not stage_path.exists():
            continue
        
        for checkpoint_file in stage_path.glob("*.json"):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    status = data.get('status', 'unknown')
                    if status in ['pass', 'fail']:
                        stage_counts[stage_dir][status] += 1
            except:
                pass
    
    # Print summary
    print("CHECKPOINT SUMMARY:")
    print("-" * 70)
    for stage in ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']:
        counts = stage_counts[stage]
        total = counts['pass'] + counts['fail']
        if total > 0:
            pass_pct = (counts['pass'] / total * 100) if total > 0 else 0
            print(f"{stage:12s}: {counts['pass']:3d} pass, {counts['fail']:3d} fail ({pass_pct:5.1f}% pass rate)")
    print()
    
    # Count raw LLM code files
    raw_code_dir = base_dir / "raw_llm" / "code"
    if raw_code_dir.exists():
        raw_count = len(list(raw_code_dir.glob("*.py")))
        print(f"Raw LLM code files: {raw_count}")
    
    # Count framework processed files
    framework_code_dir = base_dir / "framework_processed" / "code"
    if framework_code_dir.exists():
        framework_count = len(list(framework_code_dir.glob("*.py")))
        print(f"Framework processed files: {framework_count}")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    monitor_test_progress()


