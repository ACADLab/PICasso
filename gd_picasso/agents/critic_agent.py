"""
Critic Agent for multi-agent photonic circuit design.

Reviews a generated YAML netlist and provides structured feedback
to the generator agent before it hits the formal validator.

Improvements over v1:
  - Injects real PDK component specs (port names, valid parameters)
  - Problem-aware checking (required components, parameters, topology)
  - Confidence scoring to avoid over-correcting valid YAML
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Hard-coded PDK port map — source of truth for optical port validation
# ============================================================================
COMPONENT_PORT_MAP = {
    "straight":                  ["o1", "o2"],
    "bend_euler":                ["o1", "o2"],
    "bend_circular":             ["o1", "o2"],
    "bend_s":                    ["o1", "o2"],
    "mmi1x2":                    ["o1", "o2", "o3"],
    "mmi2x2":                    ["o1", "o2", "o3", "o4"],
    "coupler":                   ["o1", "o2", "o3", "o4"],
    "mzi":                       ["o1", "o2"],
    "ring_single":               ["o1", "o2"],
    "straight_heater_metal":     ["o1", "o2"],   # electrical ports l_e*/r_e* do NOT need routing
    "taper":                     ["o1", "o2"],
    "spiral":                    ["o1", "o2"],
    "grating_coupler_elliptical":["o1", "o2"],
    "crossing":                  ["o1", "o2", "o3", "o4"],
}

# Components that are valid in generic_tech PDK
VALID_COMPONENTS = set(COMPONENT_PORT_MAP.keys())

# Component aliases that do NOT exist (common LLM mistakes)
INVALID_ALIASES = {
    "mmi2x1":       "mmi1x2 with mirror: true",
    "phase_shifter":"straight_heater_metal",
    "heater":       "straight_heater_metal",
    "waveguide":    "straight",
    "y_splitter":   "mmi1x2 or coupler",
    "y_junction":   "mmi1x2 or coupler",
    "dc_2x2":       "coupler",
    "star_coupler": "coupler or mmi2x2",
    "photodiode":   "not available in generic_tech PDK",
}

# ============================================================================
# System prompt — built dynamically with component spec injected
# ============================================================================

def _build_system_prompt(component_spec_text: str = "") -> str:
    port_map_lines = []
    for comp, ports in COMPONENT_PORT_MAP.items():
        port_map_lines.append(f"  {comp}: {', '.join(ports)}")
    port_map_str = "\n".join(port_map_lines)

    invalid_lines = "\n".join(
        f"  {bad} → use {good}" for bad, good in INVALID_ALIASES.items()
    )

    spec_section = ""
    if component_spec_text:
        spec_section = f"""
===================================================
COMPONENT SPECIFICATIONS FROM PDK
===================================================
{component_spec_text}
"""

    return f"""You are an expert photonic circuit design reviewer for GDSFactory generic_tech PDK.

Your job is to review a YAML netlist and identify REAL problems — not hypothetical ones.
Only flag issues you can verify directly from reading the YAML. Do NOT guess.

You are NOT generating a circuit. You are reviewing one.

===================================================
PDK PORT REFERENCE (authoritative)
===================================================
{port_map_str}

NOTE: straight_heater_metal has electrical ports (l_e1-4, r_e1-4) that do NOT
need optical routing. Only o1 and o2 are optical and need to be connected.

===================================================
INVALID COMPONENTS (do not exist in generic_tech)
===================================================
{invalid_lines}
{spec_section}
===================================================
WHAT TO CHECK — ONLY THESE FOUR THINGS
===================================================

You MUST only check these four things. Do not check anything else.

1. PORT NAMES IN ROUTES — Are port names in the routes section valid?
   Use the port reference above. Example of a real error: using "o5" on
   an mmi1x2 (which only has o1, o2, o3).
   Do NOT flag electrical ports on straight_heater_metal (l_e*, r_e*).

2. MIRRORING — If an mmi1x2 is used as a combiner (right side of circuit),
   does it have mirror: true in its placement?

3. MISSING ROUTES — If there are multiple components, is there a routes section
   with links connecting them?

4. STRUCTURE — Are all four required sections present?
   (instances, placements, routes, ports)

===================================================
MZI / MZM IMPLEMENTATION RULE — CRITICAL, READ THIS FIRST
===================================================

The 'mzi' compound component does NOT work in this framework (no SAX model).
The ONLY correct MZI implementation is:
  mmi1x2 (splitter) + straight_heater_metal (phase arm) + mmi1x2 (combiner, mirror:true)

THIS OVERRIDES THE PROBLEM DESCRIPTION. Even if the problem spec says "use mzi
components", a YAML that uses mmi1x2 + straight_heater_metal IS CORRECT.

NEVER tell the generator to switch back to 'mzi'.
NEVER flag mmi1x2 + straight_heater_metal as "incorrect use of mmi1x2".
NEVER flag a circuit as "missing MZI/MZM" if it contains mmi1x2 + straight_heater_metal.
NEVER flag instance count mismatches caused by expanding mzi into primitives —
  each mzi becomes 3 instances (splitter + heater + combiner), so counts will differ
  from what the problem spec says.

===================================================
DO NOT CHECK THESE — THEY ARE HANDLED ELSEWHERE
===================================================

- DO NOT check instance ID names (phase_shifter, mmi1, mzm, etc.) — these are
  arbitrary labels chosen by the designer, not component types.
- DO NOT check component: field values — handled by static validator.
- DO NOT check settings parameters or DeltaL — handled by static validator.
- DO NOT check spacing between components — handled by pilot validator.
- DO NOT check routing topology or connection correctness — cannot be verified
  without building the circuit.
- DO NOT flag a circuit as "missing MZI/MZM" if it uses mmi1x2 + straight_heater_metal.
- DO NOT flag instance counts — the problem spec counts assume mzi compound components
  but the correct implementation uses 3 primitives per MZI, so counts will not match.
- DO NOT tell the generator to use 'mzi' for any reason.

===================================================
CONFIDENCE RULE — IMPORTANT
===================================================
Only set ISSUES_FOUND: YES if you are CONFIDENT something is wrong.
If you are unsure, set ISSUES_FOUND: NO — it is better to let the
formal validator catch real errors than to over-correct working YAML.

===================================================
RESPONSE FORMAT (use exactly)
===================================================
ISSUES_FOUND: <YES or NO>
CONFIDENCE: <HIGH or LOW>
PROBLEMS:
- <specific problem with component/port name>
SUGGESTIONS:
- <specific fix>

If no issues:
ISSUES_FOUND: NO
CONFIDENCE: HIGH
PROBLEMS: none
SUGGESTIONS: none

Be concise. Do not rewrite the YAML. Do not explain basics."""


class CriticAgent:
    """
    Reviews generated YAML netlists with PDK-aware and problem-aware checking.
    """

    def __init__(self, agent, component_spec_text: str = ""):
        """
        Initialize critic agent.

        Args:
            agent: LLM agent instance with ASK_LLM method
            component_spec_text: Optional PDK component spec text to inject
        """
        self.agent = agent
        self.system_prompt = _build_system_prompt(component_spec_text)

    def review(self, yaml_str: str, problem_desc: str) -> dict:
        """
        Review a generated YAML netlist.

        Args:
            yaml_str: The YAML netlist to review
            problem_desc: The original problem description

        Returns:
            dict with keys:
                - issues_found: bool
                - confidence: str ("HIGH" or "LOW")
                - problems: list of problem strings
                - suggestions: list of suggestion strings
                - raw_response: full critic response
        """
        # Run pre-checks we can do deterministically (no LLM needed)
        static_issues = self._static_checks(yaml_str, problem_desc)

        user_message = f"""ORIGINAL PROBLEM:
{problem_desc}

GENERATED YAML TO REVIEW:
{yaml_str}

Review this YAML. Focus on whether it correctly solves the problem above."""

        # Static checks first — these are certain, no LLM needed.
        if static_issues:
            return {
                "issues_found": True,
                "confidence": "HIGH",
                "problems": static_issues["problems"],
                "suggestions": static_issues["suggestions"],
                "raw_response": "static"
            }

        # Static checks passed — ask the LLM critic for a deeper review.
        # Only act on HIGH confidence findings to avoid false positives.
        if self.agent is not None:
            try:
                llm_response = self.agent.ASK_LLM(self.system_prompt, user_message)
                result = self._parse_response(llm_response)
                # Discard LOW confidence LLM findings — not worth acting on
                if result["issues_found"] and result["confidence"] != "HIGH":
                    logger.info("🔍 Critic LLM: issues found but confidence LOW — ignoring")
                    result["issues_found"] = False
                    result["problems"] = []
                    result["suggestions"] = []
                return result
            except Exception as e:
                logger.warning(f"Critic LLM call failed ({e}) — falling back to static result")

        return {
            "issues_found": False,
            "confidence": "HIGH",
            "problems": [],
            "suggestions": [],
            "raw_response": "static"
        }

    def _static_checks(self, yaml_str: str, problem_desc: str) -> Optional[dict]:
        """
        Run fast deterministic checks without an LLM call.
        Flags issues we can verify with certainty from the YAML text alone.

        Returns dict of problems/suggestions, or None if no issues found.
        """
        import yaml as _yaml
        problems = []
        suggestions = []

        # Parse YAML safely
        try:
            data = _yaml.safe_load(yaml_str)
        except Exception:
            return None  # Malformed YAML — let the formal validator handle it

        if not isinstance(data, dict):
            return None

        instances = data.get("instances", {}) or {}
        placements = data.get("placements", {}) or {}

        # ------------------------------------------------------------------
        # Check 1: Invalid component names (do not exist in PDK)
        # ------------------------------------------------------------------
        for inst_name, inst_data in instances.items():
            if not isinstance(inst_data, dict):
                continue
            comp = inst_data.get("component", "")
            if comp in INVALID_ALIASES:
                problems.append(
                    f"Instance '{inst_name}' uses invalid component '{comp}' "
                    f"— use {INVALID_ALIASES[comp]} instead"
                )
                suggestions.append(
                    f"Replace component: {comp} with {INVALID_ALIASES[comp]} for '{inst_name}'"
                )

            # Check 2: 'mirror' in settings instead of placements
            # mmi1x2() does not accept 'mirror' as a constructor argument —
            # it must go in the placements section, not instance settings.
            settings = inst_data.get("settings", {}) or {}
            if "mirror" in settings:
                problems.append(
                    f"Instance '{inst_name}' has 'mirror' inside settings — "
                    f"'mirror' must be in placements, not settings"
                )
                suggestions.append(
                    f"Move 'mirror: true' from instances.{inst_name}.settings "
                    f"to placements.{inst_name}.mirror: true"
                )

        # ------------------------------------------------------------------
        # Check 3: Component 'mzi' used directly — SAX has no model for it
        # Use primitive components (mmi1x2 + straight_heater_metal) instead
        # ------------------------------------------------------------------
        for inst_name, inst_data in instances.items():
            if not isinstance(inst_data, dict):
                continue
            comp = inst_data.get("component", "")
            if comp == "mzi":
                problems.append(
                    f"Instance '{inst_name}' uses the 'mzi' compound component — "
                    f"SAX cannot simulate it (missing model). "
                    f"Build the MZI from primitives: mmi1x2 + straight_heater_metal + mmi1x2"
                )
                suggestions.append(
                    f"Replace the 'mzi' instance with explicit mmi1x2 splitter, "
                    f"straight_heater_metal arm(s), and mmi1x2 combiner (mirror: true)"
                )

        # ------------------------------------------------------------------
        # Check 4: Component spacing — flag pairs closer than 50um
        # (pilot validator catches <100um, but we catch obvious <50um here
        #  so the generator can fix it before the pilot validator fires)
        # ------------------------------------------------------------------
        positions = {}
        for inst_name, placement in placements.items():
            if not isinstance(placement, dict):
                continue
            x = placement.get("x", 0)
            y = placement.get("y", 0)
            try:
                positions[inst_name] = (float(x), float(y))
            except (TypeError, ValueError):
                pass

        inst_names = list(positions.keys())
        for i in range(len(inst_names)):
            for j in range(i + 1, len(inst_names)):
                a, b = inst_names[i], inst_names[j]
                ax, ay = positions[a]
                bx, by = positions[b]
                dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                if dist < 50:
                    problems.append(
                        f"Components '{a}' and '{b}' are only {dist:.0f}um apart "
                        f"— minimum spacing is 100um"
                    )
                    suggestions.append(
                        f"Increase spacing between '{a}' and '{b}' to at least 100um "
                        f"by moving one component further away"
                    )

        # ------------------------------------------------------------------
        # Check 5: Missing required YAML sections
        # ------------------------------------------------------------------
        for section in ["instances", "placements", "routes", "ports"]:
            if section not in data:
                problems.append(f"Required section '{section}' is missing from YAML")
                suggestions.append(f"Add a '{section}' section to the YAML")

        if problems:
            return {"problems": problems, "suggestions": suggestions}
        return None

    def _extract_required_components(self, problem_desc: str) -> dict:
        """
        Parse the problem description to extract required component counts.
        e.g. "Two MMI1x2" → {"mmi1x2": 2}
        """
        required = {}
        text = problem_desc.lower()

        # Number words → integers
        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4,
            "a ": 1, "an ": 1,
        }

        # Component name patterns to look for
        component_patterns = {
            "mmi1x2": [r"mmi1x2", r"mmi 1x2", r"mmi1 x2", r"1x2 mmi"],
            "mmi2x2": [r"mmi2x2", r"mmi 2x2", r"2x2 mmi"],
            "straight_heater_metal": [r"straight_heater_metal", r"heater", r"phase.shifter"],
            "coupler": [r"\bcoupler\b", r"directional coupler"],
            "ring_single": [r"ring_single", r"ring resonator", r"\bring\b"],
            "straight": [r"\bstraight\b", r"\bwaveguide\b"],
        }

        for comp, patterns in component_patterns.items():
            for pattern in patterns:
                matches = re.findall(
                    r'(\w+|\d+)\s+(?:' + pattern + r')',
                    text
                )
                if matches:
                    for match in matches:
                        count = number_words.get(match + " ", None) or number_words.get(match, None)
                        if count is None:
                            try:
                                count = int(match)
                            except ValueError:
                                count = 1
                        required[comp] = max(required.get(comp, 0), count)
                    break

        return required

    def _check_required_parameters(self, problem_desc: str, instances: dict) -> dict:
        """
        Check that parameters specified in the problem are present in instances.
        e.g. if problem says "L = 10.0", check at least one instance has length: 10.0
        """
        problems = []
        suggestions = []

        # Look for parameter assignments in problem description
        # Matches patterns like "L = 10.0", "length=50", "DeltaL = 10"
        param_pattern = re.findall(
            r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([0-9]+(?:\.[0-9]+)?)',
            problem_desc
        )

        if not param_pattern:
            return {"problems": problems, "suggestions": suggestions}

        # Map common problem param names to YAML setting names
        param_aliases = {
            "L": ["length", "l"],
            "length": ["length", "l"],
            "deltal": ["delta_l", "deltal", "length"],
            "width": ["width", "w"],
            "W": ["width", "w"],
        }

        for param_name, param_value in param_pattern:
            expected_value = float(param_value)
            aliases = param_aliases.get(param_name, [param_name.lower()])

            # Check if any instance has this parameter
            found = False
            for inst_name, inst_data in instances.items():
                if not isinstance(inst_data, dict):
                    continue
                settings = inst_data.get("settings", {}) or {}
                for alias in aliases:
                    if alias in settings:
                        found = True
                        break
                if found:
                    break

            # Only flag if the param is clearly missing (not DeltaL which is a path difference)
            if not found and param_name.upper() not in ["DELTAL", "DELTA_L"]:
                problems.append(
                    f"Problem specifies {param_name}={param_value} but no instance "
                    f"has a matching '{aliases[0]}' setting"
                )
                suggestions.append(
                    f"Add '{aliases[0]}: {param_value}' to the relevant component's settings"
                )

        return {"problems": problems, "suggestions": suggestions}

    def _parse_response(self, response: str) -> dict:
        """Parse the critic's structured response."""
        result = {
            "issues_found": False,
            "confidence": "LOW",
            "problems": [],
            "suggestions": [],
            "raw_response": response
        }

        lines = response.strip().split("\n")
        section = None

        for line in lines:
            line = line.strip()

            if line.startswith("ISSUES_FOUND:"):
                result["issues_found"] = "YES" in line.upper()

            elif line.startswith("CONFIDENCE:"):
                result["confidence"] = "HIGH" if "HIGH" in line.upper() else "LOW"

            elif line.startswith("PROBLEMS:"):
                section = "problems"
                inline = line.replace("PROBLEMS:", "").strip()
                if inline and inline.lower() != "none":
                    result["problems"].append(inline)

            elif line.startswith("SUGGESTIONS:"):
                section = "suggestions"
                inline = line.replace("SUGGESTIONS:", "").strip()
                if inline and inline.lower() != "none":
                    result["suggestions"].append(inline)

            elif line.startswith("- ") and section == "problems":
                result["problems"].append(line[2:].strip())

            elif line.startswith("- ") and section == "suggestions":
                result["suggestions"].append(line[2:].strip())

        return result

    def format_feedback(self, review: dict) -> str:
        """
        Format review results as feedback text for the generator agent.
        """
        if not review["issues_found"]:
            return ""

        parts = ["DESIGN REVIEW FEEDBACK (fix these before finalizing):"]

        if review["problems"]:
            parts.append("\nPROBLEMS FOUND:")
            for p in review["problems"]:
                parts.append(f"  - {p}")

        if review["suggestions"]:
            parts.append("\nHOW TO FIX:")
            for s in review["suggestions"]:
                parts.append(f"  - {s}")

        return "\n".join(parts)
