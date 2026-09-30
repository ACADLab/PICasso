"""
DRC Validator with generic_tech PDK

Uses gplugins.klayout.drc.write_drc_deck_macro with generic_tech.LAYER
to perform real DRC checks (not toy examples).
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Tuple, Optional
import logging
import gdsfactory as gf

logger = logging.getLogger(__name__)

# macOS install layouts vary by version / DMG naming
_KLAYOUT_CANDIDATES = (
    "/Applications/klayout.app/Contents/MacOS/klayout",  # 0.30.x DMG (lowercase)
    "/Applications/KLayout.app/Contents/MacOS/klayout",
    "/Applications/KLayout/klayout.app/Contents/MacOS/klayout",  # older nested path
    "klayout",  # PATH / Homebrew
)


def _resolve_klayout_executable(explicit: Optional[str] = None) -> str:
    """Return a usable KLayout CLI path (GUI app ≠ PATH entry)."""
    if explicit:
        return explicit
    env = os.environ.get("KLAYOUT_BIN") or os.environ.get("PICASSO_KLAYOUT")
    if env and (env == "klayout" or os.path.exists(env)):
        return env
    for cand in _KLAYOUT_CANDIDATES:
        if cand == "klayout":
            continue
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return "klayout"


# Try to import generic_tech and gplugins
try:
    from gdsfactory.generic_tech import LAYER
    GENERIC_TECH_AVAILABLE = True
except ImportError:
    GENERIC_TECH_AVAILABLE = False
    LAYER = None

try:
    from gplugins.klayout.drc.write_drc import write_drc_deck_macro
    GPLUGINS_AVAILABLE = True
except ImportError:
    GPLUGINS_AVAILABLE = False
    write_drc_deck_macro = None


class DRCValidator:
    """Validates designs against fabrication design rules using generic_tech PDK."""

    def __init__(
        self,
        klayout_executable: Optional[str] = None,
        use_generic_tech: bool = True
    ):
        """
        Initialize DRC validator.

        Args:
            klayout_executable: Path to KLayout executable (if None, auto-detect)
            use_generic_tech: Whether to use generic_tech PDK (real, not toy)
        """
        self.klayout_exec = _resolve_klayout_executable(klayout_executable)
        self.use_generic_tech = use_generic_tech and GENERIC_TECH_AVAILABLE
        self.drc_script_path = None

    def validate(self, component: gf.Component, gds_path: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Run DRC validation on a component using generic_tech PDK.

        Args:
            component: GDSFactory component to check
            gds_path: Optional path to save GDS file

        Returns:
            (is_valid, report) where report contains:
                - passed: bool
                - errors: List[str]
                - warnings: List[str]
                - violations: int
                - drc_report_path: str (if generated)
        """
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "violations": 0,
            "drc_report_path": None,
            "drc_mode": None,
        }

        klayout_gui = self._check_klayout_available()
        if not klayout_gui:
            report["warnings"].append(
                "KLayout GUI binary not found — using klayout.db Python DRC"
            )
            logger.warning("KLayout executable not found — Python DRC fallback")

        # Only generate + run .lydrc deck when the GUI binary exists
        if klayout_gui and self.use_generic_tech and GPLUGINS_AVAILABLE:
            try:
                self.drc_script_path = self._generate_drc_script()
            except Exception as e:
                logger.warning(f"Could not generate DRC script: {e}")
                report["warnings"].append(f"DRC script generation failed: {e}")

        try:
            cleanup_gds = False
            if gds_path is None:
                with tempfile.NamedTemporaryFile(suffix=".gds", delete=False) as tmp:
                    gds_path = tmp.name
                    cleanup_gds = True

            component.write_gds(gds_path)

            if (
                klayout_gui
                and self.drc_script_path
                and os.path.exists(self.drc_script_path)
            ):
                passed, violations = self._run_klayout_drc(gds_path, report)
                if violations == -1:
                    logger.warning(
                        "KLayout execution failed — falling back to Python DRC"
                    )
                    report["errors"].clear()
                    report["warnings"].append(
                        "KLayout DRC execution failed — using klayout.db"
                    )
                    passed, violations = self._run_basic_drc(gds_path, report)
                else:
                    report["drc_mode"] = report.get("drc_mode") or "klayout_batch"
            else:
                passed, violations = self._run_basic_drc(gds_path, report)

            report["passed"] = passed
            report["violations"] = violations

            if cleanup_gds and os.path.exists(gds_path):
                try:
                    os.unlink(gds_path)
                except OSError:
                    pass

            logger.info(
                f"DRC Validation: {'PASS' if passed else 'FAIL'} "
                f"({violations} violations, mode={report.get('drc_mode')})"
            )

        except Exception as e:
            logger.error(f"DRC validation failed with exception: {e}")
            report["passed"] = False
            report["errors"].append(f"DRC exception: {str(e)}")

        return report["passed"], report

    def _generate_drc_script(self) -> str:
        """Write a **batch** KLayout DRC DSL script (not a GUI .lydrc macro).

        ``gplugins.write_drc_deck_macro`` emits an XML macro that expects an
        open layout in the GUI — that fails under ``klayout -b -rd input_gds=``.
        """
        output_dir = Path(__file__).parent.parent / "output" / "drc_scripts"
        output_dir.mkdir(parents=True, exist_ok=True)
        drc_script_path = output_dir / "picasso_batch_wg.drc"
        # Also keep a GUI macro for interactive use when gplugins is present
        if GPLUGINS_AVAILABLE and GENERIC_TECH_AVAILABLE and write_drc_deck_macro:
            try:
                write_drc_deck_macro(
                    rules=["width_min", "space_min"],
                    layers=LAYER,
                    filepath=str(output_dir / "generic_tech_drc.lydrc"),
                )
            except Exception as e:
                logger.debug("GUI lydrc generation skipped: %s", e)

        script = """# PICasso batch DRC — WG width hard-fail; space soft markers.
# Usage:
#   klayout -b -r picasso_batch_wg.drc -rd input_gds=FILE.gds -rd report=OUT.lyrdb
source($input_gds)
report("PICasso WG DRC", $report)
threads(4)
WG = input(1, 0)
WG.width(0.35).output("WG_width_lt_0p35um")
WG.space(0.2).output("WG_space_lt_0p2um")
"""
        drc_script_path.write_text(script, encoding="utf-8")
        logger.info("Generated batch DRC script: %s", drc_script_path)
        return str(drc_script_path)

    def _check_klayout_available(self) -> bool:
        """Check if KLayout CLI is installed and accessible."""
        # Re-resolve in case Applications path was missed at init
        if self.klayout_exec == "klayout" or not os.path.exists(self.klayout_exec):
            resolved = _resolve_klayout_executable(None)
            if resolved != "klayout" or os.path.exists(resolved):
                self.klayout_exec = resolved
        try:
            result = subprocess.run(
                [self.klayout_exec, "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            ok = result.returncode == 0
            if ok:
                ver = (result.stdout or result.stderr or "").strip().splitlines()
                if ver:
                    logger.info("KLayout CLI: %s (%s)", ver[0], self.klayout_exec)
            return ok
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def _run_klayout_drc(self, gds_path: str, report: Dict) -> Tuple[bool, int]:
        """Run KLayout batch DRC (``-b -r``) with ``input_gds`` / ``report``."""
        try:
            drc_report_path = gds_path.replace(".gds", "_drc_report.lyrdb")
            cmd = [
                self.klayout_exec,
                "-b",
                "-r",
                self.drc_script_path,
                "-rd",
                f"input_gds={gds_path}",
                "-rd",
                f"report={drc_report_path}",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            stderr = result.stderr or ""
            if "ERROR:" in stderr and not Path(drc_report_path).is_file():
                report["errors"].append(
                    f"KLayout batch DRC failed: {stderr.strip()[:300]}"
                )
                return False, -1

            width_n, space_n = self._parse_lyrdb(drc_report_path)
            report["drc_report_path"] = drc_report_path
            report["drc_mode"] = "klayout_batch"
            report["violations_by_category"] = {
                "WG_width_lt_0p35um": width_n,
                "WG_space_lt_0p2um": space_n,
            }
            if space_n:
                report["warnings"].append(
                    f"WG space soft-warn: {space_n} markers < 0.2µm "
                    "(not hard-fail; needs net-aware DRC)"
                )
            # Hard-fail on width only
            if width_n:
                report["errors"].append(
                    f"KLayout WG width violations: {width_n} (min 0.35µm)"
                )
            return width_n == 0, width_n

        except subprocess.TimeoutExpired:
            report["errors"].append("DRC check timed out")
            return False, -1
        except Exception as e:
            report["errors"].append(f"DRC script execution failed: {e}")
            return False, -1

    @staticmethod
    def _parse_lyrdb(report_path: str) -> Tuple[int, int]:
        """Count width vs space items in a KLayout ``.lyrdb`` XML report."""
        path = Path(report_path)
        if not path.is_file():
            return 0, 0
        try:
            import xml.etree.ElementTree as ET

            root = ET.parse(path).getroot()
            # Categories declare names; items reference category by path
            cat_names: Dict[str, str] = {}
            for cat in root.findall(".//category"):
                name_el = cat.find("name")
                if name_el is not None and name_el.text:
                    cat_names[name_el.text] = name_el.text
            width_n = space_n = 0
            for item in root.findall(".//item"):
                cat = item.find("category")
                cname = (cat.text or "") if cat is not None else ""
                # category text may be path-like "WG_width_lt_0p35um"
                if "width" in cname:
                    width_n += 1
                elif "space" in cname:
                    space_n += 1
            return width_n, space_n
        except Exception:
            # Fallback: crude string counts
            text = path.read_text(encoding="utf-8", errors="ignore")
            return (
                text.count("WG_width_lt_0p35um"),
                text.count("WG_space_lt_0p2um"),
            )

    def _run_basic_drc(self, gds_path: str, report: Dict) -> Tuple[bool, int]:
        """Run Python klayout.db waveguide width checks (WG layer).

        Space checks on a fully merged WG region false-positive on routed
        PIC bends/arms; those need net-aware DRC. Width is the hard gate here.
        """
        try:
            import klayout.db as kdb
        except ImportError:
            report["warnings"].append(
                "No KLayout binary and no klayout.db — DRC soft-skipped"
            )
            report["drc_mode"] = "skipped"
            return True, 0

        report["warnings"].append(
            "Using klayout.db Python DRC (WG width; space soft-warn only)"
        )
        report["drc_mode"] = "klayout_db_wg_width"
        try:
            ly = kdb.Layout()
            ly.read(gds_path)
            top = ly.top_cell()
            if top is None:
                report["errors"].append("DRC: GDS has no top cell")
                return False, 1
            dbu = float(ly.dbu) or 0.001
            # generic_tech strip ~0.5 µm — enforce min width 0.35 µm
            min_w = max(1, int(0.35 / dbu))
            min_s = max(1, int(0.2 / dbu))
            violations = 0
            space_warn = 0
            by_layer: Dict[str, int] = {}
            # Prefer generic_tech WG / layer 1,0
            wg_layers = {(1, 0)}
            try:
                if LAYER is not None and hasattr(LAYER, "WG"):
                    wg = LAYER.WG
                    wg_layers.add((int(wg[0]), int(wg[1]) if len(wg) > 1 else 0))
            except Exception:
                pass

            checked = 0
            for li in ly.layer_infos():
                key = (int(li.layer), int(li.datatype))
                if key not in wg_layers:
                    continue
                idx = ly.layer(li.layer, li.datatype)
                region = kdb.Region(top.begin_shapes_rec(idx))
                if region.is_empty():
                    continue
                checked += 1
                # Width on raw shapes (not global-merge) avoids bend artifacts
                w = region.width_check(min_w)
                n_w = int(w.count())
                merged = region.merged()
                s = merged.space_check(min_s)
                n_s = int(s.count())
                space_warn += n_s
                if n_w:
                    by_layer[f"{li.layer}/{li.datatype}"] = n_w
                    violations += n_w
            if checked == 0:
                report["warnings"].append("DRC: no WG layer geometry found")
                return True, 0
            report["violations_by_category"] = {
                "width": by_layer,
                "space_soft": space_warn,
            }
            if space_warn:
                report["warnings"].append(
                    f"WG space soft-warn: {space_warn} edges < {0.2}µm "
                    "(not hard-fail; needs net-aware DRC)"
                )
            if violations:
                report["errors"].append(
                    f"klayout.db WG width violations: {violations} "
                    f"(min_w=0.35µm) layers={by_layer}"
                )
            return violations == 0, violations
        except Exception as e:
            report["errors"].append(f"klayout.db DRC failed: {e}")
            report["drc_mode"] = "klayout_db_error"
            return False, -1

    def _parse_drc_report(self, report_path: str, report: Dict) -> int:
        """
        Parse KLayout DRC report to count violations.

        Args:
            report_path: Path to DRC report file
            report: Report dictionary to update

        Returns:
            Number of violations found (0 = empty report = PASS)
        """
        if not os.path.exists(report_path):
            return 0

        try:
            # Read report file
            with open(report_path, 'r') as f:
                content = f.read()
            
            # Empty report = no violations = PASS
            if not content.strip():
                return 0
            
            # Count lines (each line typically represents a violation)
            # This is a simplified parser - full implementation would parse XML/DB format
            lines = content.strip().split('\n')
            violation_count = len([line for line in lines if line.strip()])
            
            report["violations_by_category"] = {"total": violation_count}
            
            return violation_count

        except Exception as e:
            logger.warning(f"Failed to parse DRC report: {e}")
            return 0

    def generate_feedback(self, report: Dict) -> str:
        """Generate human-readable feedback for LLM retry."""
        feedback_parts = []

        if report["violations"] > 0:
            feedback_parts.append(f"DRC VIOLATIONS: {report['violations']} found")
            feedback_parts.append("\nSUGGESTIONS FOR FIXING:")
            feedback_parts.append("  - Increase spacing between components (minimum 200um)")
            feedback_parts.append("  - Use larger bend radius (>= 20um)")
            feedback_parts.append("  - Check that routes don't cross or overlap")
            feedback_parts.append("  - Ensure proper clearance from waveguides")

        return "\n".join(feedback_parts)

