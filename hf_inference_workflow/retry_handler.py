"""
Retry Handler with LLM Feedback

Manages intelligent retry logic for failed designs:
- Collects validation feedback from P&R, DRC, and SAX validators
- Feeds back to LLM for correction
- Tracks retry attempts and success rates
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationStage(Enum):
    """Validation stages in order of execution."""
    PARSING = "parsing"
    PNR = "pnr"
    DRC = "drc"
    SAX = "sax"


@dataclass
class RetryAttempt:
    """Record of a single retry attempt."""
    attempt_number: int
    failed_stage: ValidationStage
    feedback: str
    response: str
    timestamp: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())


@dataclass
class RetryResult:
    """Result of retry process."""
    success: bool
    final_design: Optional[str]
    attempts: List[RetryAttempt]
    total_attempts: int
    failed_stage: Optional[ValidationStage] = None
    final_feedback: Optional[str] = None


class RetryHandler:
    """
    Manages retry logic with intelligent feedback to LLM.

    The retry process:
    1. Design generation fails at some validation stage
    2. Collect detailed feedback from failed validator
    3. Format feedback for LLM understanding
    4. Ask LLM to generate improved design
    5. Repeat until success or max retries reached
    """

    def __init__(self, max_retries: int = 3):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts
        """
        self.max_retries = max_retries
        self.retry_history: List[RetryAttempt] = []

    def should_retry(self, attempt_number: int) -> bool:
        """Check if we should retry based on attempt number."""
        return attempt_number < self.max_retries

    def format_feedback_for_llm(
        self,
        failed_stage: ValidationStage,
        validation_reports: Dict[str, Dict],
        problem_description: str
    ) -> str:
        """
        Format validation feedback into LLM-friendly prompt.

        Args:
            failed_stage: Which validation stage failed
            validation_reports: Reports from all validators
            problem_description: Original problem statement

        Returns:
            Formatted feedback prompt for LLM
        """
        feedback_parts = []

        feedback_parts.append("The previous design attempt failed validation.")
        feedback_parts.append(f"Failed at stage: {failed_stage.value.upper()}\n")

        # Add stage-specific feedback
        if failed_stage == ValidationStage.PARSING:
            feedback_parts.append("PARSING ERROR:")
            feedback_parts.append("The generated code could not be parsed or executed.")
            feedback_parts.append("Please ensure:")
            feedback_parts.append("  - Code is valid Python syntax")
            feedback_parts.append("  - All imports are correct")
            feedback_parts.append("  - No undefined variables")
            feedback_parts.append("  - Proper indentation")

        elif failed_stage == ValidationStage.PNR:
            pnr_report = validation_reports.get('pnr', {})
            feedback_parts.append("PLACE & ROUTE VALIDATION FAILED:")
            if pnr_report:
                feedback_parts.append(self._format_pnr_feedback(pnr_report))

        elif failed_stage == ValidationStage.DRC:
            drc_report = validation_reports.get('drc', {})
            feedback_parts.append("DESIGN RULE CHECK (DRC) FAILED:")
            if drc_report:
                feedback_parts.append(self._format_drc_feedback(drc_report))

        elif failed_stage == ValidationStage.SAX:
            sax_report = validation_reports.get('sax', {})
            feedback_parts.append("SAX COMPILATION/ROUTING VALIDATION FAILED:")
            if sax_report:
                feedback_parts.append(self._format_sax_feedback(sax_report))

        # Add general improvement suggestions
        feedback_parts.append("\n" + "="*60)
        feedback_parts.append("PLEASE FIX THE ABOVE ISSUES AND REGENERATE THE DESIGN.")
        feedback_parts.append("="*60)
        feedback_parts.append(f"\nOriginal problem:\n{problem_description}")

        return "\n".join(feedback_parts)

    def _format_pnr_feedback(self, pnr_report: Dict) -> str:
        """Format P&R validation report for LLM."""
        feedback = []

        if pnr_report.get("errors"):
            feedback.append("\nCritical Errors:")
            for error in pnr_report["errors"]:
                feedback.append(f"  ❌ {error}")

        if pnr_report.get("warnings"):
            feedback.append("\nWarnings:")
            for warning in pnr_report["warnings"]:
                feedback.append(f"  ⚠️  {warning}")

        if pnr_report.get("metrics"):
            feedback.append("\nLayout Metrics:")
            metrics = pnr_report["metrics"]
            for key, value in metrics.items():
                if isinstance(value, float):
                    feedback.append(f"  • {key}: {value:.2f}")
                else:
                    feedback.append(f"  • {key}: {value}")

        feedback.append("\nKey Improvements Needed:")
        feedback.append("  1. Increase spacing between components to at least 20µm")
        feedback.append("  2. Use .move() to position components without overlap")
        feedback.append("  3. Use route_bundle instead of route_single for cleaner routing")
        feedback.append("  4. Ensure bend radius >= 10µm")
        feedback.append("  5. Keep layout compact but not cramped")

        return "\n".join(feedback)

    def _format_drc_feedback(self, drc_report: Dict) -> str:
        """Format DRC validation report for LLM."""
        feedback = []

        if drc_report.get("violations", 0) > 0:
            feedback.append(f"\nTotal DRC Violations: {drc_report['violations']}")

            if "violations_by_category" in drc_report:
                feedback.append("\nViolations by Category:")
                for category, count in drc_report["violations_by_category"].items():
                    feedback.append(f"  • {category}: {count}")

        if drc_report.get("errors"):
            feedback.append("\nErrors:")
            for error in drc_report["errors"]:
                feedback.append(f"  ❌ {error}")

        feedback.append("\nDRC Fix Checklist:")
        feedback.append("  1. Minimum waveguide spacing: 2-3µm")
        feedback.append("  2. Minimum bend radius: 10µm")
        feedback.append("  3. No overlapping waveguides or components")
        feedback.append("  4. Metal traces have proper clearance from waveguides")
        feedback.append("  5. All features meet minimum size requirements")

        return "\n".join(feedback)

    def _format_sax_feedback(self, sax_report: Dict) -> str:
        """Format SAX validation report for LLM."""
        feedback = []

        if not sax_report.get("sax_compiled", False):
            feedback.append("\n❌ Circuit failed to compile in SAX simulator")
            feedback.append("This usually means:")
            feedback.append("  • Missing or incorrect component names")
            feedback.append("  • Invalid netlist structure")
            feedback.append("  • Unsupported component types")

        if not sax_report.get("routing_validated", False):
            feedback.append("\n❌ Physical routing validation failed")
            feedback.append("This means the circuit may compile but routing is incorrect:")
            feedback.append("  • Components placed but not physically connected")
            feedback.append("  • Missing waveguide routes between components")
            feedback.append("  • Port orientations misaligned")

        if sax_report.get("errors"):
            feedback.append("\nSpecific Errors:")
            for error in sax_report["errors"]:
                feedback.append(f"  ❌ {error}")

        feedback.append("\nSAX/Routing Fix Checklist:")
        feedback.append("  1. Use route_bundle to create actual waveguide connections")
        feedback.append("  2. Ensure all component optical ports are connected or exposed")
        feedback.append("  3. Verify port orientations are cardinal (0°, 90°, 180°, 270°)")
        feedback.append("  4. Don't just place components - route between them!")
        feedback.append("  5. Use proper GDSFactory component names from the PDK")

        return "\n".join(feedback)

    def create_retry_prompt(
        self,
        original_prompt: str,
        feedback: str,
        attempt_number: int
    ) -> str:
        """
        Create complete retry prompt combining original request with feedback.

        Args:
            original_prompt: Original system/instruction prompt
            feedback: Formatted validation feedback
            attempt_number: Current retry attempt number

        Returns:
            Complete retry prompt for LLM
        """
        retry_prompt = f"""
{original_prompt}

{'='*70}
RETRY ATTEMPT {attempt_number}/{self.max_retries}
{'='*70}

{feedback}

IMPORTANT: Please carefully address ALL the issues mentioned above.
Focus on:
  • Proper component spacing (minimum 20µm)
  • Using route_bundle for routing (not route_single)
  • Clean, organized layout (not clumsy)
  • All ports properly connected
  • Following the example structure provided

Generate the corrected design below:
"""
        return retry_prompt

    def record_attempt(
        self,
        attempt_number: int,
        failed_stage: ValidationStage,
        feedback: str,
        response: str
    ):
        """Record a retry attempt for tracking."""
        attempt = RetryAttempt(
            attempt_number=attempt_number,
            failed_stage=failed_stage,
            feedback=feedback,
            response=response
        )
        self.retry_history.append(attempt)
        logger.info(f"Recorded retry attempt {attempt_number} (failed at {failed_stage.value})")

    def get_summary(self) -> Dict:
        """Get summary of retry attempts."""
        return {
            "total_attempts": len(self.retry_history),
            "stages_failed": [attempt.failed_stage.value for attempt in self.retry_history],
            "max_retries": self.max_retries
        }

    def reset(self):
        """Reset retry history for new design."""
        self.retry_history = []


class AdaptiveRetryHandler(RetryHandler):
    """
    Adaptive retry handler that adjusts strategy based on failure patterns.

    Features:
    - Increases temperature for stuck designs
    - Provides more specific hints after repeated failures
    - Tracks which failure modes are most common
    """

    def __init__(self, max_retries: int = 3):
        super().__init__(max_retries)
        self.failure_counts = {stage: 0 for stage in ValidationStage}

    def format_feedback_for_llm(
        self,
        failed_stage: ValidationStage,
        validation_reports: Dict[str, Dict],
        problem_description: str
    ) -> str:
        """Enhanced feedback with adaptive hints."""
        # Get base feedback
        feedback = super().format_feedback_for_llm(
            failed_stage, validation_reports, problem_description
        )

        # Track failure
        self.failure_counts[failed_stage] += 1

        # Add adaptive hints for repeated failures
        if self.failure_counts[failed_stage] > 1:
            feedback += f"\n\n⚠️  NOTE: This is the {self.failure_counts[failed_stage]}th time failing at {failed_stage.value}."
            feedback += "\nConsider a significantly different approach!"

            if failed_stage == ValidationStage.PNR:
                feedback += "\nTry: Much larger spacing (30-40µm), simpler layout arrangement"
            elif failed_stage == ValidationStage.DRC:
                feedback += "\nTry: Larger bend radius (15-20µm), increase all clearances"
            elif failed_stage == ValidationStage.SAX:
                feedback += "\nTry: Simpler component connections, verify component names"

        return feedback

    def suggest_generation_params(self, attempt_number: int) -> Dict:
        """Suggest adjusted generation parameters for retries."""
        params = {}

        # Increase temperature for retries to get different designs
        if attempt_number == 1:
            params["temperature"] = 0.5  # Slightly more creative
        elif attempt_number == 2:
            params["temperature"] = 0.7  # More creative
        elif attempt_number >= 3:
            params["temperature"] = 0.8  # Very creative

        return params
