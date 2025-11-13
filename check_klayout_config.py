#!/usr/bin/env python3
"""
Check KLayout configuration and setup for DRC validation.
"""

import subprocess
import sys
import os
from pathlib import Path


def check_klayout_executable():
    """Check if klayout executable is in PATH."""
    print("🔍 Checking for klayout executable...")
    
    # Try common locations
    possible_paths = [
        "/Applications/klayout.app/Contents/MacOS/klayout",  # macOS app bundle
        "/usr/local/bin/klayout",  # Homebrew
        "/opt/homebrew/bin/klayout",  # Homebrew Apple Silicon
        "klayout",  # In PATH
    ]
    
    for path in possible_paths:
        try:
            result = subprocess.run(
                [path, "-v"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ Found klayout at: {path}")
                version = result.stdout.strip() or result.stderr.strip()
                print(f"   Version: {version.split()[0] if version else 'Unknown'}")
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    print("⚠️  klayout executable not found in PATH")
    return None


def check_klayout_python_api():
    """Check if klayout Python API is available."""
    print("\n🔍 Checking for klayout Python API...")
    
    try:
        import klayout.db as pya
        print("✅ klayout Python API is available")
        print(f"   Module path: {pya.__file__}")
        return True
    except ImportError as e:
        print(f"⚠️  klayout Python API not available: {e}")
        print("   You can install it with: pip install klayout")
        return False


def check_drc_configuration():
    """Check DRC configuration in config.py."""
    print("\n🔍 Checking DRC configuration...")
    
    config_path = Path(__file__).parent / "hf_inference_workflow" / "config.py"
    
    if not config_path.exists():
        print(f"⚠️  Config file not found: {config_path}")
        return
    
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Check ENABLE_DRC_CHECK
    if "ENABLE_DRC_CHECK = True" in content:
        print("✅ DRC checking is ENABLED in config.py")
    elif "ENABLE_DRC_CHECK = False" in content:
        print("⚠️  DRC checking is DISABLED in config.py")
        print("   To enable, set: ENABLE_DRC_CHECK = True")
    
    # Check DRC_SCRIPT_PATH
    if "DRC_SCRIPT_PATH = None" in content:
        print("ℹ️  DRC_SCRIPT_PATH is None (will use basic DRC checks)")
    else:
        print("ℹ️  Custom DRC script path is set")


def suggest_klayout_setup():
    """Suggest how to set up klayout."""
    print("\n📋 KLayout Setup Recommendations:")
    print("\n1. Install klayout Python API (recommended):")
    print("   pip install klayout")
    print("\n2. Or install full KLayout application:")
    print("   macOS: brew install --cask klayout")
    print("   Or download from: https://www.klayout.de/build.html")
    print("\n3. Update config.py to point to klayout executable:")
    print("   In hf_inference_workflow/validators/drc_validator.py")
    print("   Set klayout_executable='/path/to/klayout'")


def fix_config_for_klayout(klayout_path):
    """Suggest configuration update."""
    print(f"\n🔧 To use klayout executable at {klayout_path}:")
    print("\nOption 1: Update DRCValidator initialization in your code:")
    print(f'   drc_validator = DRCValidator(klayout_executable="{klayout_path}")')
    print("\nOption 2: Set environment variable:")
    print(f'   export KLAYOUT_PATH="{klayout_path}"')


def main():
    print("="*70)
    print("KLayout Configuration Checker for PICasso")
    print("="*70)
    
    klayout_path = check_klayout_executable()
    has_python_api = check_klayout_python_api()
    check_drc_configuration()
    
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    
    if klayout_path or has_python_api:
        print("✅ KLayout is available for DRC validation")
        if klayout_path:
            print(f"   Executable: {klayout_path}")
        if has_python_api:
            print("   Python API: Available")
            
        if klayout_path and not has_python_api:
            print("\n💡 Tip: Install klayout Python API for better integration:")
            print("   pip install klayout")
    else:
        print("⚠️  KLayout is not available")
        suggest_klayout_setup()
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()


