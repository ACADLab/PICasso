"""
Test Script for HF Inference Workflow

Run this to verify everything is set up correctly.
"""

import sys
from pathlib import Path

def test_imports():
    """Test that all required packages are installed."""
    print("Testing imports...")

    try:
        import gdsfactory as gf
        print("  ✅ gdsfactory")
    except ImportError as e:
        print(f"  ❌ gdsfactory: {e}")
        return False

    try:
        import pandas as pd
        print("  ✅ pandas")
    except ImportError as e:
        print(f"  ❌ pandas: {e}")
        return False

    try:
        from huggingface_hub import InferenceClient
        print("  ✅ huggingface_hub")
    except ImportError as e:
        print(f"  ❌ huggingface_hub: {e}")
        return False

    try:
        from tqdm import tqdm
        print("  ✅ tqdm")
    except ImportError as e:
        print(f"  ❌ tqdm: {e}")
        return False

    # Optional imports
    try:
        import sax
        print("  ✅ sax (optional)")
    except ImportError:
        print("  ⚠️  sax (optional - SAX validation will be skipped)")

    try:
        import jax
        print("  ✅ jax (optional)")
    except ImportError:
        print("  ⚠️  jax (optional - required for SAX)")

    return True


def test_config():
    """Test configuration."""
    print("\nTesting configuration...")

    try:
        from config import HF_API_TOKEN, DEFAULT_MODEL

        if HF_API_TOKEN == "ENTER_YOUR_HF_TOKEN_HERE":
            print("  ⚠️  HF_API_TOKEN not set - please configure it")
            print("     Set via environment: export HF_API_TOKEN=your_token")
            print("     Or edit config.py")
            return False
        else:
            print(f"  ✅ HF_API_TOKEN configured (length: {len(HF_API_TOKEN)})")

        print(f"  ✅ Model: {DEFAULT_MODEL}")
        return True

    except Exception as e:
        print(f"  ❌ Config error: {e}")
        return False


def test_validators():
    """Test validators can be imported."""
    print("\nTesting validators...")

    try:
        from validators import PNRValidator, DRCValidator, SAXValidator
        print("  ✅ PNRValidator")
        print("  ✅ DRCValidator")
        print("  ✅ SAXValidator")

        # Test initialization
        pnr = PNRValidator()
        drc = DRCValidator()
        sax = SAXValidator()
        print("  ✅ Validators initialize successfully")

        return True
    except Exception as e:
        print(f"  ❌ Validator error: {e}")
        return False


def test_hf_api():
    """Test HuggingFace API connection."""
    print("\nTesting HuggingFace API connection...")

    try:
        from hf_api_client import HFInferenceAgent
        from config import HF_API_TOKEN

        if HF_API_TOKEN == "ENTER_YOUR_HF_TOKEN_HERE":
            print("  ⚠️  Skipping API test - token not configured")
            return False

        print("  Creating agent...")
        agent = HFInferenceAgent()

        print("  Testing simple query...")
        response = agent.ASK_LLM(
            "You are a helpful assistant.",
            "Say 'API works' if you can read this."
        )

        print(f"  ✅ API response received (length: {len(response)})")
        print(f"     Preview: {response[:100]}...")

        return True

    except Exception as e:
        print(f"  ❌ API test failed: {e}")
        return False


def test_gdsfactory():
    """Test GDSFactory basic functionality."""
    print("\nTesting GDSFactory...")

    try:
        import gdsfactory as gf

        # Create simple component
        c = gf.Component()
        mmi = c << gf.components.mmi1x2()

        print("  ✅ Component creation works")

        # Test bbox access (DBox compatibility)
        bbox = mmi.bbox()
        if hasattr(bbox, 'xmin'):
            print("  ✅ DBox format detected (new GDSFactory)")
        else:
            print("  ✅ Tuple format detected (old GDSFactory)")

        return True

    except Exception as e:
        print(f"  ❌ GDSFactory test failed: {e}")
        return False


def test_file_structure():
    """Test that all required files exist."""
    print("\nChecking file structure...")

    required_files = [
        "config.py",
        "hf_api_client.py",
        "gen_data_validated.py",
        "retry_handler.py",
        "validators/__init__.py",
        "validators/pnr_validator.py",
        "validators/drc_validator.py",
        "validators/sax_validator.py",
        "requirements.txt",
        "README.md",
        "QUICKSTART.md"
    ]

    all_exist = True
    for filepath in required_files:
        path = Path(filepath)
        if path.exists():
            print(f"  ✅ {filepath}")
        else:
            print(f"  ❌ {filepath} - MISSING")
            all_exist = False

    return all_exist


def main():
    """Run all tests."""
    print("="*60)
    print("HF Inference Workflow - Test Suite")
    print("="*60)

    results = {}

    # Run tests
    results['File Structure'] = test_file_structure()
    results['Imports'] = test_imports()
    results['Configuration'] = test_config()
    results['GDSFactory'] = test_gdsfactory()
    results['Validators'] = test_validators()
    results['HF API'] = test_hf_api()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())

    print("\n" + "="*60)
    if all_passed:
        print("🎉 All tests passed! You're ready to generate designs!")
        print("\nNext steps:")
        print("  1. Review config.py settings")
        print("  2. Run: python gen_data_validated.py")
        print("  3. Check output/results/ for CSV results")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Missing imports: pip install -r requirements.txt")
        print("  - API token: export HF_API_TOKEN=your_token")
        print("  - Optional deps: pip install sax jax (if needed)")
    print("="*60)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
