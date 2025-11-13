"""
Test Case Extractor

Extracts circuit designs from notebooks.
First pass: Run parser/router to check port and syntax.
Second pass: Identify designs with false data (pass SAX but fail routing/DRC).
"""

import ast
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import gdsfactory as gf

logger = logging.getLogger(__name__)


class TestExtractor:
    """Extracts test cases from notebooks."""

    def __init__(self, notebooks_dir: Path, openai_llms_dir: Optional[Path] = None):
        """
        Initialize test extractor.

        Args:
            notebooks_dir: Directory containing notebook files
            openai_llms_dir: Optional directory for OpenAI LLMs notebooks
        """
        self.notebooks_dir = notebooks_dir
        self.openai_llms_dir = openai_llms_dir
        self.extracted_cases = []

    def extract_all(self, parse_first_pass: bool = True) -> List[Dict]:
        """
        Extract all test cases from notebooks.

        Args:
            parse_first_pass: Whether to run parser/router first pass

        Returns:
            List of extracted test cases
        """
        test_cases = []
        
        # Extract from hf_models results
        if self.notebooks_dir.exists():
            notebook_files = list(self.notebooks_dir.glob("*.ipynb"))
            for notebook_file in notebook_files:
                cases = self.extract_from_notebook(notebook_file, parse_first_pass)
                test_cases.extend(cases)
        
        # Extract from openAI_llms if provided
        if self.openai_llms_dir and self.openai_llms_dir.exists():
            notebook_files = list(self.openai_llms_dir.glob("*.ipynb"))
            for notebook_file in notebook_files:
                cases = self.extract_from_notebook(notebook_file, parse_first_pass)
                test_cases.extend(cases)
        
        self.extracted_cases = test_cases
        return test_cases

    def extract_from_notebook(self, notebook_path: Path, parse_first_pass: bool = True) -> List[Dict]:
        """
        Extract test cases from a notebook file.

        Args:
            notebook_path: Path to notebook file
            parse_first_pass: Whether to run parser/router first pass

        Returns:
            List of test cases
        """
        test_cases = []
        
        try:
            with open(notebook_path, 'r') as f:
                notebook = json.load(f)
            
            # Extract code cells
            code_cells = []
            for cell in notebook.get('cells', []):
                if cell.get('cell_type') == 'code':
                    source = ''.join(cell.get('source', []))
                    if source.strip():
                        code_cells.append(source)
            
            # Process each code cell
            for idx, code in enumerate(code_cells):
                # Extract circuit code
                circuit_code = self._extract_circuit_code(code)
                if not circuit_code:
                    continue
                
                # First pass: Parse and check syntax/ports
                if parse_first_pass:
                    parse_result = self._parse_first_pass(circuit_code)
                    if not parse_result[0]:
                        # Skip if parsing fails
                        logger.debug(f"Skipping code cell {idx} from {notebook_path.name}: {parse_result[1]}")
                        continue
                
                # Create test case
                test_case = {
                    "source_file": str(notebook_path),
                    "cell_index": idx,
                    "code": circuit_code,
                    "parsed": parse_first_pass and parse_result[0] if parse_first_pass else None,
                    "parse_error": parse_result[1] if parse_first_pass and not parse_result[0] else None,
                }
                
                test_cases.append(test_case)
                
        except Exception as e:
            logger.error(f"Error extracting from {notebook_path}: {e}")
        
        return test_cases

    def _extract_circuit_code(self, code: str) -> Optional[str]:
        """
        Extract circuit code from cell.

        Args:
            code: Cell code content

        Returns:
            Extracted circuit code or None
        """
        # Look for gdsfactory imports and component creation
        if 'import gdsfactory' not in code and 'import gf' not in code:
            return None
        
        if 'gf.Component()' not in code and 'Component()' not in code:
            return None
        
        # Extract code block (remove markdown if present)
        code = code.strip()
        if code.startswith('```'):
            code = code.split('```')[1]
            if code.startswith('python'):
                code = code[5:]
        
        return code.strip()

    def _parse_first_pass(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        First pass: Parse code and check syntax/ports.

        Args:
            code: Python code

        Returns:
            (is_valid, error_message)
        """
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        # Try to execute and check for port errors
        try:
            ns = {"gf": gf}
            exec(code, ns)
            
            # Try to find component
            component = None
            for var_name in ['r', 'c', 'circuit', 'component']:
                if var_name in ns and isinstance(ns[var_name], gf.Component):
                    component = ns[var_name]
                    break
            
            if component is None:
                return False, "No GDSFactory Component found"
            
            # Check for basic port issues
            if len(component.ports) == 0:
                return False, "No ports exposed"
            
            return True, None
            
        except Exception as e:
            return False, f"Execution error: {str(e)}"

    def identify_false_data_cases(self, test_cases: List[Dict]) -> List[Dict]:
        """
        Identify cases that pass SAX but fail routing/DRC.

        Args:
            test_cases: List of test cases

        Returns:
            List of false data cases
        """
        false_data_cases = []
        
        # Import validators
        try:
            from ..validators.sax_validator import SAXValidator
            from ..validators.pnr_validator import PNRValidator
            from ..validators.drc_validator import DRCValidator
            sax_validator = SAXValidator()
            pnr_validator = PNRValidator()
            drc_validator = DRCValidator()
        except ImportError as e:
            logger.warning(f"Could not import validators, using simplified checks: {e}")
            sax_validator = None
            pnr_validator = None
            drc_validator = None
        
        logger.info(f"Checking {len(test_cases)} test cases for false data (pass SAX but fail routing/DRC)...")
        
        for idx, test_case in enumerate(test_cases):
            code = test_case.get('code')
            if not code:
                continue
            
            # Try to execute and validate
            try:
                ns = {"gf": gf}
                exec(code, ns)
                
                # Find component
                component = None
                for var_name in ['r', 'c', 'circuit', 'component']:
                    if var_name in ns and isinstance(ns[var_name], gf.Component):
                        component = ns[var_name]
                        break
                
                if component is None:
                    logger.debug(f"Test case {idx}: No component found")
                    continue
                
                # Check SAX compilation using validator if available
                if sax_validator:
                    sax_passes, sax_report = sax_validator.validate(component)
                else:
                    sax_passes = self._check_sax_compilation(component)
                    sax_report = {"passed": sax_passes}
                
                if not sax_passes:
                    logger.debug(f"Test case {idx}: SAX compilation failed, skipping")
                    continue
                
                # Check routing/DRC using validators if available
                if pnr_validator:
                    pnr_passes, pnr_report = pnr_validator.validate(component)
                    routing_issues = [] if pnr_passes else [pnr_report.get("error", "P&R validation failed")]
                else:
                    routing_issues = self._check_routing_issues(component)
                    pnr_passes = len(routing_issues) == 0
                
                if drc_validator:
                    # Create temporary GDS file for DRC check
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.gds', delete=False) as tmp:
                        tmp_path = tmp.name
                    try:
                        component.write_gds(tmp_path)
                        drc_passes, drc_report = drc_validator.validate(component, tmp_path)
                        drc_issues = [] if drc_passes else [drc_report.get("error", "DRC validation failed")]
                    finally:
                        import os
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                else:
                    drc_issues = self._check_drc_issues(component)
                    drc_passes = len(drc_issues) == 0
                
                # If SAX passes but routing/DRC fails, it's a false data case
                has_routing_drc_issues = (not pnr_passes) or (not drc_passes)
                
                if sax_passes and has_routing_drc_issues:
                    test_case['sax_passes'] = True
                    test_case['routing_issues'] = routing_issues
                    test_case['drc_issues'] = drc_issues
                    test_case['pnr_passes'] = pnr_passes
                    test_case['drc_passes'] = drc_passes
                    false_data_cases.append(test_case)
                    logger.info(f"Test case {idx}: FALSE DATA CASE - SAX passes but routing/DRC fails")
                    logger.info(f"  P&R passes: {pnr_passes}, DRC passes: {drc_passes}")
                else:
                    logger.debug(f"Test case {idx}: SAX={sax_passes}, P&R={pnr_passes}, DRC={drc_passes}")
                    
            except Exception as e:
                logger.warning(f"Error checking test case {idx}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"Found {len(false_data_cases)} false data cases out of {len(test_cases)} test cases")
        return false_data_cases

    def _check_sax_compilation(self, component: gf.Component) -> bool:
        """Check if component compiles in SAX."""
        try:
            import sax
            netlist = component.get_netlist()
            circuit, _ = sax.circuit(netlist=netlist, models=sax.models.get_models())
            return True
        except:
            return False

    def _check_routing_issues(self, component: gf.Component) -> List[str]:
        """Check for routing issues."""
        issues = []
        
        try:
            refs = list(component.references)
        except AttributeError:
            refs = list(getattr(component, 'insts', []))
        
        # Check if routes exist
        has_routes = False
        for ref in refs:
            try:
                cell_name = ref.cell.name if hasattr(ref, 'cell') else str(ref)
                if any(keyword in cell_name.lower() for keyword in ['route', 'waveguide', 'bend']):
                    has_routes = True
                    break
            except:
                pass
        
        if len(refs) > 1 and not has_routes:
            issues.append("No routing structures detected")
        
        # Check spacing
        if len(refs) >= 2:
            positions = []
            for ref in refs:
                try:
                    bbox = ref.bbox()
                    if bbox:
                        if hasattr(bbox, 'xmin'):
                            x = (bbox.xmin + bbox.xmax) / 2
                            y = (bbox.ymin + bbox.ymax) / 2
                        else:
                            x, y = 0, 0
                        positions.append((x, y))
                except:
                    pass
            
            # Check pairwise spacing
            for i, (x1, y1) in enumerate(positions):
                for x2, y2 in positions[i+1:]:
                    distance = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    if 0 < distance < 20.0:
                        issues.append(f"Spacing violation: {distance:.1f}µm < 20µm")
        
        return issues

    def _check_drc_issues(self, component: gf.Component) -> List[str]:
        """Check for DRC issues."""
        issues = []
        
        # Simplified DRC checks
        # Full DRC would require KLayout
        
        # Check for very small features
        try:
            bbox = component.bbox()
            if bbox:
                if hasattr(bbox, 'width'):
                    width = bbox.width
                    height = bbox.height
                elif hasattr(bbox, 'xmax'):
                    width = bbox.xmax - bbox.xmin
                    height = bbox.ymax - bbox.ymin
                else:
                    return issues
                
                if width < 1.0 or height < 1.0:
                    issues.append("Component dimensions too small")
        except:
            pass
        
        return issues

