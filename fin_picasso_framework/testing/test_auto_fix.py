"""
Test Auto-Fix Capabilities

This script tests the framework's ability to automatically fix false code examples.
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
framework_dir = Path(__file__).parent.parent
parent_dir = framework_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    import gdsfactory as gf
    _gdsfactory_available = True
except ImportError:
    _gdsfactory_available = False
    print("ERROR: gdsfactory not available")
    sys.exit(1)

from fin_picasso_framework.testing.test_extractor import TestExtractor
from fin_picasso_framework.validators.pnr_validator import PNRValidator
from fin_picasso_framework.validators.sax_validator import SAXValidator
from fin_picasso_framework.auto_fix.routing_fixer import RoutingFixer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_auto_fix_on_false_codes():
    """Test auto-fix on false code examples."""
    
    # Extract false code cases
    extractor = TestExtractor()
    test_cases = extractor.extract_all()
    false_cases = extractor.identify_false_data_cases(test_cases)
    
    logger.info(f"Found {len(false_cases)} false code cases to test")
    
    # Initialize validators
    pnr_validator = PNRValidator()
    sax_validator = SAXValidator()
    routing_fixer = RoutingFixer()
    
    results = []
    
    for idx, test_case in enumerate(false_cases[:3]):  # Test first 3
        code = test_case.get('code')
        if not code:
            continue
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing Case {idx + 1}: {test_case.get('notebook', 'unknown')}")
        logger.info(f"{'='*70}")
        
        # Try to execute original code
        try:
            ns = {"gf": gf}
            exec(code, ns)
            
            component = None
            for var_name in ['r', 'c', 'circuit', 'component']:
                if var_name in ns and isinstance(ns[var_name], gf.Component):
                    component = ns[var_name]
                    break
            
            if component is None:
                logger.warning(f"Case {idx + 1}: No component found")
                continue
            
            # Validate original
            sax_passes, sax_report = sax_validator.validate(component)
            pnr_passes, pnr_report = pnr_validator.validate(component)
            
            logger.info(f"Original Code:")
            logger.info(f"  SAX: {'PASS' if sax_passes else 'FAIL'}")
            logger.info(f"  P&R: {'PASS' if pnr_passes else 'FAIL'}")
            if not pnr_passes:
                logger.info(f"  P&R Errors: {pnr_report.get('errors', [])}")
            
            # Try auto-fix
            logger.info(f"\nAttempting auto-fix...")
            fixed_code = routing_fixer.fix_missing_routes(code, component)
            
            if fixed_code != code:
                logger.info(f"  Auto-fix modified code")
                # Try to execute fixed code
                try:
                    ns2 = {"gf": gf}
                    exec(fixed_code, ns2)
                    
                    fixed_component = None
                    for var_name in ['r', 'c', 'circuit', 'component']:
                        if var_name in ns2 and isinstance(ns2[var_name], gf.Component):
                            fixed_component = ns2[var_name]
                            break
                    
                    if fixed_component:
                        sax_passes_fixed, _ = sax_validator.validate(fixed_component)
                        pnr_passes_fixed, pnr_report_fixed = pnr_validator.validate(fixed_component)
                        
                        logger.info(f"Fixed Code:")
                        logger.info(f"  SAX: {'PASS' if sax_passes_fixed else 'FAIL'}")
                        logger.info(f"  P&R: {'PASS' if pnr_passes_fixed else 'FAIL'}")
                        
                        results.append({
                            'case': idx + 1,
                            'original_sax': sax_passes,
                            'original_pnr': pnr_passes,
                            'fixed_sax': sax_passes_fixed,
                            'fixed_pnr': pnr_passes_fixed,
                            'fixed_code': fixed_code if pnr_passes_fixed else None
                        })
                    else:
                        logger.warning(f"  Could not extract fixed component")
                except Exception as e:
                    logger.error(f"  Error executing fixed code: {e}")
            else:
                logger.info(f"  Auto-fix did not modify code (may need manual fixes)")
                results.append({
                    'case': idx + 1,
                    'original_sax': sax_passes,
                    'original_pnr': pnr_passes,
                    'fixed_sax': None,
                    'fixed_pnr': None,
                    'fixed_code': None,
                    'note': 'Auto-fix did not modify code'
                })
            
        except Exception as e:
            logger.error(f"Case {idx + 1}: Error executing code: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            continue
    
    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("SUMMARY")
    logger.info(f"{'='*70}")
    
    fixed_count = sum(1 for r in results if r.get('fixed_pnr') is True)
    logger.info(f"Cases tested: {len(results)}")
    logger.info(f"Successfully fixed: {fixed_count}")
    
    return results


if __name__ == "__main__":
    results = test_auto_fix_on_false_codes()
    
    # Save results
    output_file = Path(__file__).parent.parent / "test_output" / "auto_fix_results.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("Auto-Fix Test Results\n")
        f.write("=" * 70 + "\n\n")
        for r in results:
            f.write(f"Case {r['case']}:\n")
            f.write(f"  Original: SAX={r['original_sax']}, P&R={r['original_pnr']}\n")
            if r.get('fixed_pnr') is not None:
                f.write(f"  Fixed: SAX={r['fixed_sax']}, P&R={r['fixed_pnr']}\n")
            if r.get('fixed_code'):
                f.write(f"  Fixed code available\n")
            f.write("\n")
    
    logger.info(f"\nResults saved to: {output_file}")


