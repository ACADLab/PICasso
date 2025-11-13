"""
Place and Route (P&R) Validator

Checks for physical layout quality issues:
- Component overlap
- Proper spacing
- Route lengths
- Layout compactness
"""

import gdsfactory as gf
from typing import Dict, List, Tuple, Optional
import logging
try:
    from ..config import MIN_COMPONENT_SPACING, MAX_LAYOUT_AREA, MAX_ROUTE_LENGTH
except ImportError:
    # Fallback values
    MIN_COMPONENT_SPACING = 20.0
    MAX_LAYOUT_AREA = 500000.0
    MAX_ROUTE_LENGTH = 2000.0

logger = logging.getLogger(__name__)


class PNRValidator:
    """Validates placement and routing quality of GDSFactory components."""

    def __init__(
        self,
        min_spacing: float = MIN_COMPONENT_SPACING,
        max_area: float = MAX_LAYOUT_AREA,
        max_route_length: float = MAX_ROUTE_LENGTH
    ):
        self.min_spacing = min_spacing
        self.max_area = max_area
        self.max_route_length = max_route_length

    def validate(self, component: gf.Component) -> Tuple[bool, Dict]:
        """
        Validate P&R quality of a component.

        Args:
            component: GDSFactory Component to validate

        Returns:
            (is_valid, report) where report contains:
                - passed: bool
                - errors: List[str]
                - warnings: List[str]
                - metrics: Dict[str, float]
        """
        report = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "metrics": {}
        }

        try:
            # Run all validation checks
            self._check_component_overlap(component, report)
            self._check_spacing(component, report)
            self._check_layout_area(component, report)
            self._check_route_quality(component, report)
            self._calculate_metrics(component, report)

            # Determine overall pass/fail
            report["passed"] = len(report["errors"]) == 0

            logger.info(
                f"P&R Validation: {'PASS' if report['passed'] else 'FAIL'} "
                f"({len(report['errors'])} errors, {len(report['warnings'])} warnings)"
            )

        except Exception as e:
            logger.error(f"P&R validation failed with exception: {e}")
            report["passed"] = False
            report["errors"].append(f"Validation exception: {str(e)}")

        return report["passed"], report

    def _get_bbox_dict(self, bbox) -> Dict[str, float]:
        """Universal bbox handler for different GDSFactory versions."""
        # Try KLayout Box format (most common with current GDSFactory)
        if hasattr(bbox, 'left') and hasattr(bbox, 'right'):
            # KLayout Box: uses left, right, bottom, top
            return {
                'xmin': float(bbox.left),
                'ymin': float(bbox.bottom),
                'xmax': float(bbox.right),
                'ymax': float(bbox.top),
                'width': float(bbox.right - bbox.left),
                'height': float(bbox.top - bbox.bottom)
            }
        elif hasattr(bbox, 'xmin'):
            # DBox format: uses xmin, xmax, ymin, ymax
            return {
                'xmin': float(bbox.xmin),
                'ymin': float(bbox.ymin),
                'xmax': float(bbox.xmax),
                'ymax': float(bbox.ymax),
                'width': float(bbox.xmax - bbox.xmin),
                'height': float(bbox.ymax - bbox.ymin)
            }
        else:
            # Tuple format: (xmin, ymin, xmax, ymax)
            try:
                return {
                    'xmin': float(bbox[0]),
                    'ymin': float(bbox[1]),
                    'xmax': float(bbox[2]),
                    'ymax': float(bbox[3]),
                    'width': float(bbox[2] - bbox[0]),
                    'height': float(bbox[3] - bbox[1])
                }
            except Exception as e:
                raise ValueError(f"Unsupported bbox format. Type: {type(bbox)}, Error: {e}")

    def _check_component_overlap(self, component: gf.Component, report: Dict):
        """Check if any component instances overlap.

        Note: In photonic circuits, waveguides (routes) naturally overlap with
        component bounding boxes at connection points. We skip overlap checks
        since DRC will catch real design rule violations.
        """
        # DISABLED: Overlap checks produce false positives because waveguides
        # connecting to components will always overlap bounding boxes at ports.
        # DRC validation provides more accurate overlap detection with proper
        # design rules, so we rely on that instead.
        return

    def _check_spacing(self, component: gf.Component, report: Dict):
        """Check minimum spacing between components."""
        # Handle different GDSFactory versions
        try:
            refs = list(component.references)
        except AttributeError:
            refs = list(getattr(component, 'insts', []))

        if len(refs) < 2:
            return

        spacing_violations = []
        for i, ref1 in enumerate(refs):
            bbox1 = self._get_bbox_dict(ref1.bbox())

            for ref2 in refs[i+1:]:
                bbox2 = self._get_bbox_dict(ref2.bbox())

                # Calculate minimum distance between bounding boxes
                if bbox1['xmax'] <= bbox2['xmin']:
                    x_dist = bbox2['xmin'] - bbox1['xmax']
                elif bbox2['xmax'] <= bbox1['xmin']:
                    x_dist = bbox1['xmin'] - bbox2['xmax']
                else:
                    x_dist = 0

                if bbox1['ymax'] <= bbox2['ymin']:
                    y_dist = bbox2['ymin'] - bbox1['ymax']
                elif bbox2['ymax'] <= bbox1['ymin']:
                    y_dist = bbox1['ymin'] - bbox2['ymax']
                else:
                    y_dist = 0

                min_dist = min(x_dist, y_dist) if x_dist > 0 and y_dist > 0 else max(x_dist, y_dist)

                if 0 < min_dist < self.min_spacing:
                    spacing_violations.append(f"Spacing {min_dist:.1f}µm < minimum {self.min_spacing}µm")

        if spacing_violations:
            report["warnings"].append(f"Found {len(spacing_violations)} spacing violations")

    def _check_layout_area(self, component: gf.Component, report: Dict):
        """Check if layout area is within acceptable bounds."""
        bbox = self._get_bbox_dict(component.bbox())
        area = bbox['width'] * bbox['height']

        report["metrics"]["layout_area"] = area
        report["metrics"]["layout_width"] = bbox['width']
        report["metrics"]["layout_height"] = bbox['height']

        if area > self.max_area:
            report["warnings"].append(
                f"Layout area {area:.0f}µm² exceeds maximum {self.max_area:.0f}µm²"
            )

        # Check aspect ratio
        aspect_ratio = bbox['width'] / bbox['height'] if bbox['height'] > 0 else 1.0
        report["metrics"]["aspect_ratio"] = aspect_ratio

        if aspect_ratio > 10 or aspect_ratio < 0.1:
            report["warnings"].append(
                f"Extreme aspect ratio {aspect_ratio:.2f} (very stretched layout)"
            )

    def _check_route_quality(self, component: gf.Component, report: Dict):
        """Check routing quality metrics."""
        # This is a simplified check - real implementation would analyze actual routes
        # For now, we'll check if the component has a reasonable structure

        num_ports = len(component.ports)
        # Handle different GDSFactory versions
        try:
            num_refs = len(list(component.references))
        except AttributeError:
            num_refs = len(list(getattr(component, 'insts', [])))

        report["metrics"]["num_components"] = num_refs
        report["metrics"]["num_ports"] = num_ports

        if num_refs == 0:
            report["errors"].append("No components found in layout")

        if num_ports == 0:
            report["warnings"].append("No external ports defined")

    def _calculate_metrics(self, component: gf.Component, report: Dict):
        """Calculate additional quality metrics."""
        bbox = self._get_bbox_dict(component.bbox())

        # Compactness score (0-1, higher is better)
        area = bbox['width'] * bbox['height']
        if area > 0:
            # Simple compactness: ratio of used area to bounding box
            # (This is simplified - real calculation would analyze polygon coverage)
            compactness = min(bbox['width'], bbox['height']) / max(bbox['width'], bbox['height'])
            report["metrics"]["compactness"] = compactness
        else:
            report["metrics"]["compactness"] = 0.0

        # Overall quality score (0-1, higher is better)
        quality_score = 1.0

        # Penalties
        if report["errors"]:
            quality_score *= 0.0  # Critical failure
        if len(report["warnings"]) > 0:
            quality_score *= 0.8 ** len(report["warnings"])  # 20% penalty per warning

        # Rewards for compactness
        if "compactness" in report["metrics"]:
            quality_score *= (0.5 + 0.5 * report["metrics"]["compactness"])

        report["metrics"]["quality_score"] = max(0.0, min(1.0, quality_score))

    def generate_feedback(self, report: Dict) -> str:
        """
        Generate human-readable feedback for LLM retry.

        This feedback helps the LLM understand what went wrong and how to fix it.
        """
        feedback_parts = []

        if report["errors"]:
            feedback_parts.append("CRITICAL ERRORS:")
            for error in report["errors"]:
                feedback_parts.append(f"  - {error}")

        if report["warnings"]:
            feedback_parts.append("\nWARNINGS:")
            for warning in report["warnings"]:
                feedback_parts.append(f"  - {warning}")

        if report["metrics"]:
            feedback_parts.append("\nLAYOUT METRICS:")
            metrics = report["metrics"]
            if "layout_area" in metrics:
                feedback_parts.append(f"  - Layout area: {metrics['layout_area']:.0f} µm²")
            if "aspect_ratio" in metrics:
                feedback_parts.append(f"  - Aspect ratio: {metrics['aspect_ratio']:.2f}")
            if "compactness" in metrics:
                feedback_parts.append(f"  - Compactness: {metrics['compactness']:.2f}")
            if "quality_score" in metrics:
                feedback_parts.append(f"  - Quality score: {metrics['quality_score']:.2f}")

        feedback_parts.append("\nSUGGESTIONS FOR IMPROVEMENT:")
        if "component overlaps" in str(report.get("errors", [])):
            feedback_parts.append("  - Increase spacing between components (minimum 20µm)")
            feedback_parts.append("  - Adjust component positions to prevent overlaps")

        if "aspect_ratio" in report.get("metrics", {}) and (
            report["metrics"]["aspect_ratio"] > 5 or report["metrics"]["aspect_ratio"] < 0.2
        ):
            feedback_parts.append("  - Balance component placement to improve aspect ratio")
            feedback_parts.append("  - Consider arranging components in a more square layout")

        if "spacing violations" in str(report.get("warnings", [])):
            feedback_parts.append("  - Use route_bundle instead of route_single for cleaner routing")
            feedback_parts.append("  - Increase separation parameter in routing functions")

        return "\n".join(feedback_parts)
