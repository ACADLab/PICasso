"""Frozen Arm C system prompt — N1 typed-mutation generation.

Registered in ``N1_FROZEN_ARTIFACT_PATHS``. Do not edit after
``protocol-freeze-n1-prompts`` without a new annotated tag.
"""

from __future__ import annotations

ARM_C_SYSTEM_PROMPT = """\
You are generating a photonic circuit as a STRICT JSON object for the PICasso
Photonic Circuit Graph (PCG).

OUTPUT RULES (mandatory):
1. Reply with ONLY a JSON object. No markdown fences, no commentary.
2. Schema:
   {
     "mutations": [ ... A1 v1 ops ... ],
     "ports": { "<export_name>": "<node_id>,<port_name>", ... }
   }
3. "mutations" elements have "op" in {"add_node", "connect", "set_param"} only.
4. Do NOT emit insert_module, group_constraint, set_edge_grade, set_placement,
   set_exported_ports, export_port, or any other op inside "mutations".
5. "ports" is required and mirrors YAML's ports: block — every optical I/O that
   is intentionally external (dangling by design) MUST appear here. Omitting
   a dangling port fails ExactCritic the same way missing YAML ports fails.

MUTATION SCHEMAS:
- {"op":"add_node","id":"<string>","component":"<gf.components name>",
   "params":{...optional...}}
- {"op":"connect","src":"<node_id>","src_port":"<port>",
   "dst":"<node_id>","dst_port":"<port>","bundle":"optical"}
- {"op":"set_param","node":"<node_id>","key":"<param>","value":<json-scalar>}

CONSTRAINTS:
- Optical ports have degree at most 1.
- The optical graph with >1 nodes MUST be connected (no isolated islands).
- Use only real generic_tech components (mmi1x2, mmi2x2, straight,
  straight_heater_metal, bend_euler, coupler, ...).
- straight / straight_heater_metal length must be > 0.
- bend_euler radius must be >= 5.0.
- Prefer ASCII only in all strings.

When correcting a previous attempt, you will see PREVIOUS ATTEMPT and
VALIDATION / CRITIC ERRORS. Fix every listed error and re-emit the FULL JSON
object (mutations + ports), not a patch.
"""


def arm_c_system_prompt() -> str:
    """Return the frozen Arm C system prompt text."""
    return ARM_C_SYSTEM_PROMPT


def arm_c_user_prompt(
    problem_text: str,
    *,
    feedback: str | None = None,
    previous_attempt: str | None = None,
) -> str:
    """Build the user turn for Arm C (problem + optional prior attempt/errors)."""
    if feedback or previous_attempt:
        parts = [
            "Problem:",
            problem_text.strip(),
            "",
        ]
        if previous_attempt:
            parts.extend(
                [
                    "PREVIOUS ATTEMPT:",
                    previous_attempt.strip(),
                    "",
                ]
            )
        parts.extend(
            [
                "VALIDATION / CRITIC ERRORS:",
                (feedback or "").strip() or "(none)",
                "",
                "Emit a corrected FULL JSON object "
                '{"mutations":[...],"ports":{...}} now.',
            ]
        )
        return "\n".join(parts)
    return "\n".join(
        [
            "Problem:",
            problem_text.strip(),
            "",
            'Emit the JSON object {"mutations":[...],"ports":{...}} now.',
        ]
    )
