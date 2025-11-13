"""
Live Monitor for Framework Test

Continuously monitors test progress and displays status updates.
"""

import time
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def monitor_live(refresh_interval=5):
    """Monitor test progress in real-time."""
    base_dir = Path(__file__).parent / "output" / "benchmark_results"
    
    print("=" * 70)
    print("PICASSO FRAMEWORK LIVE MONITOR")
    print("=" * 70)
    print("Press Ctrl+C to stop monitoring")
    print("=" * 70)
    print()
    
    last_counts = {}
    
    try:
        while True:
            # Clear screen (works on most terminals)
            print("\033[2J\033[H", end="")
            
            print("=" * 70)
            print(f"PICASSO FRAMEWORK LIVE MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 70)
            print()
            
            # Count checkpoints by stage and status
            stage_counts = defaultdict(lambda: {'pass': 0, 'fail': 0, 'total': 0})
            problem_samples = defaultdict(set)
            
            for stage_dir in ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']:
                stage_path = base_dir / "checkpoints" / stage_dir
                if not stage_path.exists():
                    continue
                
                for checkpoint_file in stage_path.glob("*.json"):
                    try:
                        with open(checkpoint_file, 'r') as f:
                            data = json.load(f)
                            status = data.get('status', 'unknown')
                            problem_idx = data.get('problem_idx')
                            sample_idx = data.get('sample_idx')
                            
                            if status in ['pass', 'fail']:
                                stage_counts[stage_dir][status] += 1
                                stage_counts[stage_dir]['total'] += 1
                            
                            if problem_idx is not None and sample_idx is not None:
                                problem_samples[stage_dir].add((problem_idx, sample_idx))
                    except:
                        pass
            
            # Print summary
            print("CHECKPOINT SUMMARY:")
            print("-" * 70)
            total_problems = set()
            for stage in ['pilot', 'pnr', 'drc', 'sax', 'functional', 'optimization']:
                counts = stage_counts[stage]
                total = counts['total']
                if total > 0:
                    pass_pct = (counts['pass'] / total * 100) if total > 0 else 0
                    unique = len(problem_samples[stage])
                    total_problems.update(problem_samples[stage])
                    print(f"{stage:12s}: {counts['pass']:3d} pass, {counts['fail']:3d} fail ({pass_pct:5.1f}% pass) | {unique:3d} unique problem/sample pairs")
                else:
                    print(f"{stage:12s}: No checkpoints yet")
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
            
            # Show recent activity
            print()
            print("RECENT ACTIVITY:")
            print("-" * 70)
            
            # Get most recent checkpoint
            all_checkpoints = []
            for stage_dir in ['pilot', 'pnr', 'drc', 'sax']:
                stage_path = base_dir / "checkpoints" / stage_dir
                if stage_path.exists():
                    for checkpoint_file in stage_path.glob("*.json"):
                        try:
                            with open(checkpoint_file, 'r') as f:
                                data = json.load(f)
                                data['file'] = checkpoint_file
                                all_checkpoints.append(data)
                        except:
                            pass
            
            if all_checkpoints:
                # Sort by timestamp
                all_checkpoints.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                for cp in all_checkpoints[:5]:  # Show last 5
                    timestamp = cp.get('timestamp', 'N/A')
                    stage = cp.get('stage', 'unknown')
                    problem = cp.get('problem_idx', '?')
                    sample = cp.get('sample_idx', '?')
                    attempt = cp.get('attempt', '?')
                    status = cp.get('status', 'unknown')
                    status_symbol = "✅" if status == 'pass' else "❌"
                    print(f"{status_symbol} {timestamp[:19]} | Problem {problem}, Sample {sample}, Attempt {attempt} | {stage} | {status}")
            
            print()
            print("=" * 70)
            print(f"Refreshing every {refresh_interval} seconds... (Ctrl+C to stop)")
            
            # Check for changes
            current_counts = {k: v['total'] for k, v in stage_counts.items()}
            if current_counts != last_counts:
                print("🔄 Activity detected - counts changed!")
                last_counts = current_counts
            
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        print("=" * 70)


if __name__ == "__main__":
    import sys
    refresh = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    monitor_live(refresh)


