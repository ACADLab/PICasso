#!/usr/bin/env python3
"""
Quick script to check benchmark progress
"""

import os
import sys
from pathlib import Path
import time

print("=" * 70)
print("BENCHMARK PROGRESS CHECK")
print("=" * 70)
print()

# Check if process is running
import subprocess
result = subprocess.run(['pgrep', '-f', 'run_full_benchmark_36.py'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print("✅ Benchmark process is RUNNING")
    pids = result.stdout.strip().split('\n')
    print(f"   PIDs: {', '.join(pids)}")
else:
    print("⚠️  Benchmark process is NOT running")
    sys.exit(1)

print()

# Check log file
log_file = Path("benchmark_run_final.log")
if log_file.exists():
    size = log_file.stat().st_size
    print(f"📄 Log file: {size} bytes")
    if size > 0:
        print("\nLatest log lines:")
        print("-" * 70)
        with open(log_file) as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    else:
        print("   (empty - output buffered)")
else:
    print("📄 Log file: Not created yet")

print()

# Check CSV files
csv_dir = Path("hf_inference_workflow/output/results")
if csv_dir.exists():
    csv_files = list(csv_dir.glob("*.csv"))
    if csv_files:
        print(f"📊 CSV Files: {len(csv_files)} found")
        # Show most recent
        csv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        for f in csv_files[:3]:
            size = f.stat().st_size
            mtime = time.ctime(f.stat().st_mtime)
            print(f"   {f.name}: {size} bytes (modified: {mtime})")

            # Try to count rows
            try:
                with open(f) as file:
                    lines = len(file.readlines())
                    print(f"      → {lines-1} data rows")
            except:
                pass
    else:
        print("📊 CSV Files: None created yet")
else:
    print("📊 CSV Files: Output directory not found")

print()
print("=" * 70)
print("Check complete. Re-run this script to see updates.")
print("=" * 70)
