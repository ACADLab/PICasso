#!/usr/bin/env python3
"""Real-time monitoring script for PICasso benchmark test."""

import pandas as pd
from pathlib import Path
import time
import sys

RAW_CSV = Path('hf_inference_workflow/output/results/raw_llm_results.csv')
FRAMEWORK_CSV = Path('hf_inference_workflow/output/results/framework_results.csv')
LOG_FILE = Path('/tmp/picasso_test.log')

def monitor():
    iteration = 0
    max_iterations = 360  # 1 hour at 10s intervals
    
    try:
        while iteration < max_iterations:
            # Clear screen (works on most terminals)
            print('\033[2J\033[H', end='')
            
            print('='*70)
            print('PICASSO BENCHMARK MONITORING DASHBOARD')
            print('='*70)
            print(f'Refresh: {iteration + 1}/{max_iterations} (every 10s)')
            print('='*70)
            print()
            
            # Phase 1: Raw LLM Results
            if RAW_CSV.exists():
                try:
                    raw_df = pd.read_csv(RAW_CSV)
                    print('📊 PHASE 1: RAW LLM (Baseline)')
                    print(f'  Total Samples: {len(raw_df)}')
                    if 'success' in raw_df.columns:
                        success = raw_df['success'].sum()
                        print(f'  Success: {success} / {len(raw_df)} ({success/len(raw_df)*100:.1f}%)')
                    print()
                except Exception as e:
                    print(f'📊 PHASE 1: Error reading CSV: {e}')
                    print()
            else:
                print('📊 PHASE 1: No data yet')
                print()
            
            # Phase 2: Framework Results
            if FRAMEWORK_CSV.exists():
                try:
                    fw_df = pd.read_csv(FRAMEWORK_CSV)
                    print('🚀 PHASE 2: PICASSO FRAMEWORK')
                    print(f'  Total Samples: {len(fw_df)}')
                    
                    if 'success' in fw_df.columns:
                        success = fw_df['success'].sum()
                        print(f'  Success: {success} / {len(fw_df)} ({success/len(fw_df)*100:.1f}%)')
                    
                    if 'auto_corrected' in fw_df.columns:
                        auto = fw_df['auto_corrected'].sum()
                        print(f'  Auto-Corrected: {auto}')
                    
                    print()
                    print('  Validation Stages:')
                    for col, name in [
                        ('pnr_passed', 'PNR'),
                        ('drc_passed', 'DRC'),
                        ('sax_passed', 'SAX'),
                        ('functional_passed', 'Functional'),
                        ('loss_target_met', 'Loss Target')
                    ]:
                        if col in fw_df.columns:
                            passed = fw_df[col].sum()
                            total = len(fw_df)
                            print(f'    {name}: {passed} / {total} ({passed/total*100:.1f}%)')
                    
                    print()
                except Exception as e:
                    print(f'🚀 PHASE 2: Error reading CSV: {e}')
                    print()
            else:
                print('🚀 PHASE 2: No data yet')
                print()
            
            # Show recent log activity
            if LOG_FILE.exists():
                try:
                    with open(LOG_FILE, 'r') as f:
                        lines = f.readlines()
                        recent = lines[-10:] if len(lines) > 10 else lines
                        print('📝 Recent Activity:')
                        for line in recent:
                            if any(keyword in line for keyword in ['PASSED', 'FAILED', 'Auto-correction', 'Problem']):
                                # Extract relevant info
                                if 'Problem' in line and 'Sample' in line:
                                    print(f'  {line.strip()[-80:]}')
                                elif 'Auto-correction' in line:
                                    print(f'  🔧 {line.strip()[-80:]}')
                                elif 'PASSED' in line or 'FAILED' in line:
                                    status = '✅' if 'PASSED' in line else '❌'
                                    print(f'  {status} {line.strip()[-80:]}')
                        print()
                except:
                    pass
            
            print('='*70)
            print('Press Ctrl+C to stop monitoring')
            print('='*70)
            
            time.sleep(10)
            iteration += 1
            
    except KeyboardInterrupt:
        print('\n\n✅ Monitoring stopped by user')

if __name__ == '__main__':
    monitor()


