"""
Simple Framework Test

Quick test to verify framework modules work correctly.
"""

import sys
from pathlib import Path

# Add framework to path
framework_dir = Path(__file__).parent
sys.path.insert(0, str(framework_dir.parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from fin_picasso_framework.config import PROJECT_ROOT
        print("✅ Config imported")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.input_quality import InputValidator, PromptEnhancer
        print("✅ Input quality module imported")
    except Exception as e:
        print(f"❌ Input quality import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.port_matching import PortMatcher, ComponentSpecLoader
        print("✅ Port matching module imported")
    except Exception as e:
        print(f"❌ Port matching import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.sax_models import SAXModelManager, SAXKnowledgeBase
        print("✅ SAX models module imported")
    except Exception as e:
        print(f"❌ SAX models import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.early_validation import NetlistValidator, NetlistConverter
        print("✅ Early validation module imported")
    except Exception as e:
        print(f"❌ Early validation import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.functionality import PortDeclarationValidator, SiliconEfficiencyChecker
        print("✅ Functionality module imported")
    except Exception as e:
        print(f"❌ Functionality import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.pilot import PilotValidatorEnhanced, RestrictionLoader
        print("✅ Pilot module imported")
    except Exception as e:
        print(f"❌ Pilot import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.testing import TestExtractor, FrameworkTestSuite, TestResultsAnalyzer
        print("✅ Testing module imported")
    except Exception as e:
        print(f"❌ Testing import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.core import FrameworkPipeline, PICassoFramework
        print("✅ Core module imported")
    except Exception as e:
        print(f"❌ Core import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.validators import PNRValidator, DRCValidator, SAXValidator
        print("✅ Validators imported")
    except Exception as e:
        print(f"❌ Validators import failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.optimizers import DeviceOptimizer
        print("✅ Optimizers imported")
    except Exception as e:
        print(f"❌ Optimizers import failed: {e}")
        return False
    
    print("\n✅ All imports successful!")
    return True


def test_basic_functionality():
    """Test basic functionality of key modules."""
    print("\nTesting basic functionality...")
    
    try:
        from fin_picasso_framework.input_quality import InputValidator
        validator = InputValidator()
        is_valid, issues = validator.validate("Create an MZM with mmi1x2 splitter")
        print(f"✅ Input validator works: valid={is_valid}, issues={len(issues)}")
    except Exception as e:
        print(f"❌ Input validator test failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.port_matching import PortMatcher
        matcher = PortMatcher()
        version = matcher.get_version()
        print(f"✅ Port matcher works: version={version}")
    except Exception as e:
        print(f"❌ Port matcher test failed: {e}")
        return False
    
    try:
        from fin_picasso_framework.pilot import RestrictionLoader
        loader = RestrictionLoader()
        restrictions = loader.generate_restriction_text()
        print(f"✅ Restriction loader works: generated {len(restrictions)} chars")
    except Exception as e:
        print(f"❌ Restriction loader test failed: {e}")
        return False
    
    print("\n✅ Basic functionality tests passed!")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("PICASSO FRAMEWORK SIMPLE TEST")
    print("=" * 70)
    
    imports_ok = test_imports()
    if imports_ok:
        functionality_ok = test_basic_functionality()
        if functionality_ok:
            print("\n" + "=" * 70)
            print("✅ ALL TESTS PASSED - Framework is ready!")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("⚠️ Some functionality tests failed")
            print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ Import tests failed - check module structure")
        print("=" * 70)


