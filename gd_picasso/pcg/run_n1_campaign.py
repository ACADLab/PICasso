"""N1 three-arm ablation campaign runner (Paper A / PIC-Bench-48).

Arms A/B/C share budgets from ``spa_protocol``. Repair feedback differs by arm.

Final headline ``pass``:
  - Arm A: ``ExactCritic.review(store).ok``
  - Arms B/C: ExactCritic **and** ``evaluate_task_contract(store, contract)``

CLI::

    python -m gd_picasso.pcg.run_n1_campaign --dry-run --mock
    python -m gd_picasso.pcg.run_n1_campaign --campaign --picbench48 --allow-dirty

Stop before pinning ``N1_LLM_MODEL_ID``; ``--campaign`` requires a pin.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from gd_picasso.agents.exact_critic import ExactCritic
from gd_picasso.agents.n1_arm_c_mutation_prompt import (
    arm_c_system_prompt,
    arm_c_user_prompt,
)
from gd_picasso.agents.schematic_agent import SchematicAgent
from gd_picasso.bench.contracts import (
    contract_failures,
    evaluate_task_contract,
    get_task_contract,
)
from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.n1_problems import load_problems
from gd_picasso.pcg.n1_stats import format_ci, no_win_claim, summarize_arm_passes
from gd_picasso.pcg.spa_protocol import (
    N1_ABLATION_ARMS,
    N1_DRY_RUN_TASK_IDS,
    N1_LLM_MODEL_ID,
    N1_MAX_REPAIR_ROUNDS,
    N1_MAX_TOKENS,
    N1_SAMPLES_PER_TASK,
    N1_TASK_SUBSET,
    N1_TEMPERATURE,
    N1_UNPARSEABLE_YAML,
    assert_api_model_matches_pin,
    n1_campaign_ready,
    run_manifest,
)
from gd_picasso.pcg.store import PCGMutationError, PCGStore
from gd_picasso.pilot.base_pilot_generator import BasePilotGenerator

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Full PIC-Bench-48 slot list (46 GF + 2 unrealizable).
PICBENCH48_TASK_IDS: Tuple[int, ...] = tuple(range(1, 49))


def resolve_problems(task_ids: Sequence[int]) -> Dict[int, Dict]:
    """Load NL problems; synthesize text for formal stress / unrealizable slots."""
    from gd_picasso.pcg.build_formal_benchmarks import (
        UNREALIZABLE_SPECS,
        picbench_catalog,
    )

    catalog = {t.task_id: t for t in picbench_catalog()}
    loaded = load_problems()
    by_id: Dict[int, Dict] = {}
    for p in loaded:
        try:
            by_id[int(p["id"])] = p
        except (TypeError, ValueError):
            continue
    out: Dict[int, Dict] = {}
    missing: List[int] = []
    for tid in task_ids:
        if tid in by_id:
            out[tid] = by_id[tid]
            continue
        task = catalog.get(tid)
        name = task.name if task else f"task {tid}"
        if tid in UNREALIZABLE_SPECS:
            _n, spec = UNREALIZABLE_SPECS[tid]
            spec_txt = "; ".join(spec)
            desc = (
                f"{name}. Formal stress: realize the optical transfer "
                f"{spec_txt}. "
                "If the spec is physically unrealizable (gain > 1), refuse."
            )
        else:
            desc = (
                f"Design a photonic integrated circuit for: {name}. "
                "Emit a connected, ExactCritic-legal netlist with the "
                "topology implied by the task name."
            )
        out[tid] = {"id": str(tid), "name": name, "description": desc}
        missing.append(tid)
    if missing:
        print(f"resolve_problems: synthesized statements for tasks {missing}")
    return out


def _contract_feedback(store: PCGStore, task_id: int) -> List[str]:
    contract = get_task_contract(task_id)
    if contract is None:
        return [f"no TaskContract for task {task_id} (unrealizable or unknown)"]
    if evaluate_task_contract(store, contract):
        return []
    return contract_failures(store, contract)


def _score_store(store: PCGStore, task_id: int, arm: str) -> Tuple[bool, bool, bool, List[str]]:
    """Return (pass_headline, exact_ok, contract_ok, problems)."""
    critique = ExactCritic().review(store)
    exact_ok = bool(critique.ok)
    problems = list(critique.problems)
    c_problems = _contract_feedback(store, task_id)
    contract_ok = len(c_problems) == 0
    if not contract_ok:
        problems = problems + [f"task_contract: {p}" for p in c_problems]
    if arm in ("B_yaml_exact_critic", "C_typed_exact_critic"):
        headline = exact_ok and contract_ok
    else:
        headline = exact_ok
    return headline, exact_ok, contract_ok, problems


# ---------------------------------------------------------------------------
# LLM client (async + backoff); MockLLM for tests / --mock
# ---------------------------------------------------------------------------

class MockLLM:
    """Deterministic stub — returns fixture YAML / mutations by task id."""

    def __init__(self, fixtures_dir: Optional[Path] = None) -> None:
        self.fixtures_dir = fixtures_dir or (
            _REPO_ROOT / "gd_picasso" / "pcg" / "fixtures" / "picset"
        )
        self.model_id = "mock-n1-llm"
        self.calls = 0

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = N1_TEMPERATURE,
        max_tokens: int = N1_MAX_TOKENS,
    ) -> Tuple[str, str, int]:
        self.calls += 1
        # Extract task id from user text if present in fixture path hints
        m = re.search(r"task[_\s-]?(\d+)", user, re.I)
        # Prefer latest "Problem" context — caller passes task_id via marker
        m2 = re.search(r"\[N1_TASK_ID=(\d+)\]", user)
        tid = int(m2.group(1)) if m2 else (int(m.group(1)) if m else 34)
        path = self.fixtures_dir / f"task_{tid:02d}.yaml"
        if "A1 v1" in system or "mutations" in system.lower():
            # Arm C: convert fixture to a trivial mutation list is hard;
            # return a minimal valid MZI-like batch for dry-run smoke.
            text = _fixture_to_arm_c_json(path) if path.is_file() else "[]"
        else:
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
        return text, self.model_id, max(1, len(text) // 4)


def _fixture_to_arm_c_json(path: Path) -> str:
    """Encode fixture as Arm C envelope: {mutations, ports}."""
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mutations: List[Dict[str, Any]] = []
    for nid, inst in (data.get("instances") or {}).items():
        mutations.append(
            {
                "op": "add_node",
                "id": str(nid),
                "component": inst.get("component", "straight"),
                "params": dict(inst.get("settings") or {}),
            }
        )
    links: List[Tuple[str, str]] = []
    conns = data.get("connections") or {}
    if isinstance(conns, dict):
        for src, dst in conns.items():
            links.append((str(src), str(dst)))
    for bundle in (data.get("routes") or {}).values():
        if not isinstance(bundle, dict):
            continue
        for src, dst in (bundle.get("links") or {}).items():
            links.append((str(src), str(dst)))
    for src, dst in links:
        if "," not in src or "," not in dst:
            continue
        s_n, s_p = src.split(",", 1)
        d_n, d_p = dst.split(",", 1)
        mutations.append(
            {
                "op": "connect",
                "src": s_n.strip(),
                "src_port": s_p.strip(),
                "dst": d_n.strip(),
                "dst_port": d_p.strip(),
                "bundle": "optical",
            }
        )
    ports = {
        str(k): str(v) for k, v in (data.get("ports") or {}).items()
    }
    return json.dumps({"mutations": mutations, "ports": ports})


@dataclass
class TokenUsage:
    """Cumulative token counters for dry-run cost accounting."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# Approximate USD / 1M tokens (list prices; update when pinning campaign model).
# Sources: provider public pricing pages — treat as estimate, not invoice.
_MODEL_PRICE_PER_MTOT: Dict[str, Tuple[float, float]] = {
    # (input_usd_per_mtok, output_usd_per_mtok)
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


def estimate_cost_usd(model_id: str, usage: TokenUsage) -> float:
    """Best-effort USD estimate from cumulative usage (not a billing guarantee)."""
    prices = _MODEL_PRICE_PER_MTOT.get(model_id)
    if prices is None:
        # prefix match (e.g. dated snapshots)
        for key, val in _MODEL_PRICE_PER_MTOT.items():
            if model_id.startswith(key.split("-20")[0]) or key in model_id:
                prices = val
                break
    if prices is None:
        return float("nan")
    inp, out = prices
    return (usage.input_tokens / 1e6) * inp + (usage.output_tokens / 1e6) * out


class AsyncOpenAILLM:
    """Minimal async OpenAI-compatible chat client with exponential backoff."""

    def __init__(self, model_id: str, api_key: Optional[str] = None) -> None:
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get(
            "OPENROUTER_API"
        )
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY / OPENROUTER_API not set")
        self.usage = TokenUsage()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = N1_TEMPERATURE,
        max_tokens: int = N1_MAX_TOKENS,
    ) -> Tuple[str, str, int]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        delay = 1.0
        last_err: Optional[Exception] = None
        for attempt in range(6):
            try:
                resp = await client.chat.completions.create(
                    model=self.model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text = (resp.choices[0].message.content or "").strip()
                reported = getattr(resp, "model", None) or self.model_id
                usage = getattr(resp, "usage", None)
                in_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
                out_tok = int(getattr(usage, "completion_tokens", 0) or 0)
                tokens = int(getattr(usage, "total_tokens", 0) or (in_tok + out_tok))
                self.usage.input_tokens += in_tok
                self.usage.output_tokens += out_tok
                self.usage.calls += 1
                return text, str(reported), tokens
            except Exception as e:  # noqa: BLE001 — classify below
                last_err = e
                msg = str(e).lower()
                if "429" in msg or "rate" in msg or "timeout" in msg or "503" in msg:
                    await asyncio.sleep(delay)
                    delay = min(60.0, delay * 2)
                    continue
                raise
        raise RuntimeError(f"LLM retries exhausted: {last_err}")


class AsyncAnthropicLLM:
    """Async Anthropic Messages API client with exponential backoff + usage."""

    def __init__(self, model_id: str, api_key: Optional[str] = None) -> None:
        self.model_id = model_id
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self.usage = TokenUsage()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = N1_TEMPERATURE,
        max_tokens: int = N1_MAX_TOKENS,
    ) -> Tuple[str, str, int]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key, timeout=180.0)
        delay = 1.0
        last_err: Optional[Exception] = None
        for attempt in range(6):
            try:
                # Note: current anthropic SDK Messages.create has no
                # ``temperature`` kwarg — protocol temp is logged in manifest
                # only for Anthropic path.
                _ = temperature
                resp = await client.messages.create(
                    model=self.model_id,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                parts = []
                for block in resp.content or []:
                    t = getattr(block, "text", None)
                    if t:
                        parts.append(t)
                text = "\n".join(parts).strip()
                reported = getattr(resp, "model", None) or self.model_id
                usage = getattr(resp, "usage", None)
                in_tok = int(getattr(usage, "input_tokens", 0) or 0)
                out_tok = int(getattr(usage, "output_tokens", 0) or 0)
                self.usage.input_tokens += in_tok
                self.usage.output_tokens += out_tok
                self.usage.calls += 1
                return text, str(reported), in_tok + out_tok
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e).lower()
                name = type(e).__name__.lower()
                retryable = (
                    "429" in msg
                    or "rate" in msg
                    or "timeout" in msg
                    or "529" in msg
                    or "overloaded" in msg
                    or "connection" in msg
                    or "connect" in name
                    or "apiConnectionerror" in name
                )
                if retryable:
                    await asyncio.sleep(delay)
                    delay = min(60.0, delay * 2)
                    continue
                raise
        raise RuntimeError(f"LLM retries exhausted: {last_err}")


def build_live_llm(model_id: str) -> Any:
    """Dispatch to Anthropic or OpenAI from model id / env."""
    mid = model_id.lower()
    if mid.startswith("claude") or os.environ.get("N1_LLM_PROVIDER") == "anthropic":
        return AsyncAnthropicLLM(model_id=model_id)
    return AsyncOpenAILLM(model_id=model_id)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_YAML_TOP_KEY = re.compile(
    r"^(?:name|instances|connections|ports|placements|routes)\s*:",
    re.MULTILINE,
)


def extract_yaml_block(text: str) -> str:
    """Strip markdown fences and unfenced conversational preamble/trailer."""
    m = re.search(r"```(?:yaml|yml)?\s*\n(.*?)```", text, re.DOTALL | re.I)
    if m:
        return m.group(1).strip()
    raw = text.strip()
    # Drop conversational preamble before first YAML top-level key
    km = _YAML_TOP_KEY.search(raw)
    if km:
        raw = raw[km.start() :]
    # Drop trailing prose after the last YAML-looking block: keep through last
    # non-empty line that looks like YAML (key:, list item, or indented)
    lines = raw.splitlines()
    last_yaml = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if (
            s.startswith("#")
            or s.startswith("-")
            or ":" in s
            or line[:1] in (" ", "\t")
        ):
            last_yaml = i
    if last_yaml >= 0:
        raw = "\n".join(lines[: last_yaml + 1]).strip()
    return raw


def extract_arm_c_payload(text: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Parse Arm C JSON envelope ``{mutations, ports}`` (or legacy bare list).

    Returns ``(mutations, ports)``. Bare lists are accepted only as a
    transitional decode path and yield empty ports (ExactCritic will then
    flag dangling — same rule as YAML without a ports block).
    """
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.I)
    raw = m.group(1).strip() if m else text.strip()
    if not raw.startswith("{") and not raw.startswith("["):
        # Prefer object envelope; fall back to array slice
        i_obj, j_obj = raw.find("{"), raw.rfind("}")
        i_arr, j_arr = raw.find("["), raw.rfind("]")
        if i_obj >= 0 and j_obj > i_obj and (i_arr < 0 or i_obj < i_arr):
            raw = raw[i_obj : j_obj + 1]
        elif i_arr >= 0 and j_arr > i_arr:
            raw = raw[i_arr : j_arr + 1]
    data = json.loads(raw)
    if isinstance(data, list):
        return data, {}
    if not isinstance(data, dict):
        raise ValueError("Arm C payload must be a JSON object or array")
    mutations = data.get("mutations")
    if not isinstance(mutations, list):
        raise ValueError('Arm C payload missing "mutations" list')
    ports_raw = data.get("ports") or {}
    if not isinstance(ports_raw, dict):
        raise ValueError('Arm C "ports" must be an object')
    ports = {str(k): str(v) for k, v in ports_raw.items()}
    return mutations, ports


def build_repair_user(
    *,
    problem_text: str,
    previous_attempt: str,
    feedback: str,
    ask: str,
) -> str:
    """Shared repair turn: previous attempt + validation/critic errors."""
    return "\n".join(
        [
            "Problem:",
            problem_text.strip(),
            "",
            "PREVIOUS ATTEMPT:",
            previous_attempt.strip(),
            "",
            "VALIDATION / CRITIC ERRORS:",
            feedback.strip(),
            "",
            ask.strip(),
        ]
    )


def map_error_class(problems: Sequence[str], *, unparseable: bool = False) -> str:
    if unparseable:
        return N1_UNPARSEABLE_YAML
    blob = " ".join(problems).lower()
    if "out_of_bounds" in blob:
        return "out_of_bounds_param"
    if "polarization" in blob or "portkind" in blob:
        return "illegal_port"
    if "unknown component" in blob or "not on node" in blob:
        return "illegal_port"
    if "degree" in blob or "already connected" in blob:
        return "fanout"
    if "non-ascii" in blob or "unicode" in blob:
        return "non_ascii"
    if "unit" in blob:
        return "unit_mismatch"
    if "dangling" in blob or "connect" in blob or "n_crossings" in blob or "planar" in blob:
        return "wrong_connectivity"
    return "wrong_connectivity"


def yaml_to_store(yaml_text: str) -> PCGStore:
    return from_gf_yaml(yaml_text)


def pilot_validate(yaml_text: str) -> Tuple[bool, str]:
    """Legacy pilot feedback for Arm A repair (not the final oracle)."""
    try:
        from gd_picasso.validators.yaml_pilot_validator import YAMLPilotValidator

        ok, err, _ = YAMLPilotValidator().validate(yaml_text)
        return bool(ok), err or ""
    except Exception as e:  # noqa: BLE001
        # Fallback: parse + from_gf_yaml
        try:
            yaml_to_store(yaml_text)
            return True, ""
        except Exception as e2:  # noqa: BLE001
            return False, f"{e}; {e2}"


# ---------------------------------------------------------------------------
# Per-sample result
# ---------------------------------------------------------------------------

@dataclass
class SampleResult:
    task_id: int
    arm: str
    sample: int
    pass_: bool  # headline: ExactCritic (A) or ExactCritic∧TaskContract (B/C)
    pilot_pass: bool
    exact_critic_pass: bool
    error_class: str
    repair_rounds: int
    tokens: int
    model_id: str
    tip_sha: str
    problems: List[str] = field(default_factory=list)
    contract_pass: bool = False

    def to_csv_row(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "arm": self.arm,
            "sample": self.sample,
            "pass": int(self.pass_),
            "pilot_pass": int(self.pilot_pass),
            "exact_critic_pass": int(self.exact_critic_pass),
            "contract_pass": int(self.contract_pass),
            "error_class": self.error_class,
            "repair_rounds": self.repair_rounds,
            "tokens": self.tokens,
            "model_id": self.model_id,
            "tip_sha": self.tip_sha,
            "problems": " | ".join(self.problems),
        }


# ---------------------------------------------------------------------------
# Arm runners
# ---------------------------------------------------------------------------

async def run_arm_sample(
    *,
    arm: str,
    task_id: int,
    sample: int,
    problem_text: str,
    llm: Any,
    tip_sha: str,
    require_model_pin: bool,
    sem: asyncio.Semaphore,
) -> SampleResult:
    async with sem:
        return await _run_arm_sample_inner(
            arm=arm,
            task_id=task_id,
            sample=sample,
            problem_text=problem_text,
            llm=llm,
            tip_sha=tip_sha,
            require_model_pin=require_model_pin,
        )


async def _run_arm_sample_inner(
    *,
    arm: str,
    task_id: int,
    sample: int,
    problem_text: str,
    llm: Any,
    tip_sha: str,
    require_model_pin: bool,
) -> SampleResult:
    critic = ExactCritic()
    total_tokens = 0
    model_reported = getattr(llm, "model_id", N1_LLM_MODEL_ID)
    marked = f"[N1_TASK_ID={task_id}]\n{problem_text}"

    if arm == "A_yaml_pilot":
        system = BasePilotGenerator().generate_base_pilot_prompt()
        user = f"Problem:\n{marked}\n\nGenerate the YAML DSL netlist:"
    elif arm == "B_yaml_exact_critic":
        system = (
            "You generate GDSFactory YAML netlists for photonic circuits. "
            "Output YAML only (optional ```yaml fences). ASCII only."
        )
        user = f"Problem:\n{marked}\n\nGenerate the YAML DSL netlist:"
    elif arm == "C_typed_exact_critic":
        system = arm_c_system_prompt()
        user = arm_c_user_prompt(marked)
    else:
        raise ValueError(f"unknown arm {arm}")

    final_yaml: Optional[str] = None
    final_arm_c_text: Optional[str] = None
    pilot_ok = False
    critique_problems: List[str] = []
    rounds_used = 0

    for round_i in range(N1_MAX_REPAIR_ROUNDS + 1):
        rounds_used = round_i
        text, model_reported, tokens = await llm.complete(
            system=system, user=user, temperature=N1_TEMPERATURE, max_tokens=N1_MAX_TOKENS
        )
        total_tokens += tokens
        if require_model_pin:
            assert_api_model_matches_pin(model_reported)

        if arm in ("A_yaml_pilot", "B_yaml_exact_critic"):
            yaml_text = extract_yaml_block(text)
            try:
                store = yaml_to_store(yaml_text)
                final_yaml = yaml_text
            except Exception as e:  # noqa: BLE001
                feedback = (
                    f"YAML parse/build failed: {e}"
                    if arm == "A_yaml_pilot"
                    else f"{N1_UNPARSEABLE_YAML}: {e}"
                )
                pilot_ok = False
                if round_i >= N1_MAX_REPAIR_ROUNDS:
                    return SampleResult(
                        task_id=task_id,
                        arm=arm,
                        sample=sample,
                        pass_=False,
                        pilot_pass=False,
                        exact_critic_pass=False,
                        error_class=N1_UNPARSEABLE_YAML,
                        repair_rounds=rounds_used,
                        tokens=total_tokens,
                        model_id=model_reported,
                        tip_sha=tip_sha,
                        problems=[feedback],
                    )
                user = build_repair_user(
                    problem_text=marked,
                    previous_attempt=yaml_text or text,
                    feedback=feedback,
                    ask="Please fix and regenerate the full YAML DSL netlist.",
                )
                continue

            if arm == "A_yaml_pilot":
                pilot_ok, pilot_err = pilot_validate(yaml_text)
                if not pilot_ok and round_i < N1_MAX_REPAIR_ROUNDS:
                    user = build_repair_user(
                        problem_text=marked,
                        previous_attempt=yaml_text,
                        feedback=pilot_err or "pilot validator failed",
                        ask="Please fix and regenerate the full YAML DSL netlist.",
                    )
                    continue
                critique = critic.review(store)
                critique_problems = list(critique.problems)
                break
            else:  # Arm B — ExactCritic + TaskContract feedback for repair
                _headline, _exact, _contract, critique_problems = _score_store(
                    store, task_id, arm
                )
                pilot_ok = True
                if not _headline and round_i < N1_MAX_REPAIR_ROUNDS:
                    user = build_repair_user(
                        problem_text=marked,
                        previous_attempt=yaml_text,
                        feedback="\n".join(critique_problems),
                        ask="Please fix and regenerate the full YAML DSL netlist.",
                    )
                    continue
                break

        else:  # Arm C — explicit ports envelope; fresh store every round
            try:
                mutations, ports = extract_arm_c_payload(text)
            except Exception as e:  # noqa: BLE001
                feedback = f"{N1_UNPARSEABLE_YAML}: {e}"
                if round_i >= N1_MAX_REPAIR_ROUNDS:
                    return SampleResult(
                        task_id=task_id,
                        arm=arm,
                        sample=sample,
                        pass_=False,
                        pilot_pass=False,
                        exact_critic_pass=False,
                        contract_pass=False,
                        error_class=N1_UNPARSEABLE_YAML,
                        repair_rounds=rounds_used,
                        tokens=total_tokens,
                        model_id=model_reported,
                        tip_sha=tip_sha,
                        problems=[feedback],
                    )
                user = arm_c_user_prompt(
                    marked, feedback=feedback, previous_attempt=text
                )
                continue

            store = PCGStore(default_agent="N1_C")
            a1 = SchematicAgent()
            try:
                a1.commit_mutations(store, mutations)
                if ports:
                    store.set_exported_ports(ports, agent="N1_C")
            except PCGMutationError as e:
                feedback = str(e)
                if round_i >= N1_MAX_REPAIR_ROUNDS:
                    return SampleResult(
                        task_id=task_id,
                        arm=arm,
                        sample=sample,
                        pass_=False,
                        pilot_pass=False,
                        exact_critic_pass=False,
                        contract_pass=False,
                        error_class=map_error_class([feedback]),
                        repair_rounds=rounds_used,
                        tokens=total_tokens,
                        model_id=model_reported,
                        tip_sha=tip_sha,
                        problems=[feedback],
                    )
                user = arm_c_user_prompt(
                    marked, feedback=feedback, previous_attempt=text
                )
                continue

            _headline, _exact, _contract, critique_problems = _score_store(
                store, task_id, arm
            )
            final_arm_c_text = text
            pilot_ok = True
            if not _headline and round_i < N1_MAX_REPAIR_ROUNDS:
                user = arm_c_user_prompt(
                    marked,
                    feedback="\n".join(critique_problems),
                    previous_attempt=text,
                )
                continue
            break

    # Final grade from last successful parse
    if arm in ("A_yaml_pilot", "B_yaml_exact_critic"):
        assert final_yaml is not None
        store = yaml_to_store(final_yaml)
        if arm == "A_yaml_pilot":
            pilot_ok, _ = pilot_validate(final_yaml)
        else:
            pilot_ok = True
    elif arm == "C_typed_exact_critic" and final_arm_c_text is not None:
        # Re-apply final payload for a clean grade
        mutations, ports = extract_arm_c_payload(final_arm_c_text)
        store = PCGStore(default_agent="N1_C")
        SchematicAgent().commit_mutations(store, mutations)
        if ports:
            store.set_exported_ports(ports, agent="N1_C")

    headline, exact_ok, contract_ok, critique_problems = _score_store(
        store, task_id, arm
    )
    err = "" if headline else map_error_class(critique_problems)
    return SampleResult(
        task_id=task_id,
        arm=arm,
        sample=sample,
        pass_=headline,
        pilot_pass=pilot_ok,
        exact_critic_pass=exact_ok,
        contract_pass=contract_ok,
        error_class=err,
        repair_rounds=rounds_used,
        tokens=total_tokens,
        model_id=model_reported,
        tip_sha=tip_sha,
        problems=critique_problems,
    )


# ---------------------------------------------------------------------------
# Checkpoint + CSV
# ---------------------------------------------------------------------------

def _key(task_id: int, arm: str, sample: int) -> str:
    return f"{task_id}:{arm}:{sample}"


def load_checkpoint(path: Path) -> Dict[str, Dict[str, Any]]:
    done: Dict[str, Dict[str, Any]] = {}
    if not path.is_file():
        return done
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            done[_key(row["task_id"], row["arm"], row["sample"])] = row
    return done


def append_checkpoint(path: Path, result: SampleResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = result.to_csv_row()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_campaign(
    *,
    task_ids: Sequence[int],
    arms: Sequence[str] = N1_ABLATION_ARMS,
    samples_per_task: int = N1_SAMPLES_PER_TASK,
    llm: Any,
    out_dir: Path,
    require_clean: bool = True,
    require_model_pin: bool = False,
    concurrency: int = 4,
    dry_run: bool = False,
    results_csv_name: str = "n1_results.csv",
) -> List[SampleResult]:
    if require_model_pin and not n1_campaign_ready():
        raise RuntimeError(
            "N1_LLM_MODEL_ID is still PIN_BEFORE_CAMPAIGN; refuse --campaign"
        )
    manifest = run_manifest(
        require_clean=require_clean,
        prompts_untouched_after_dry_run=True if dry_run else None,
    )
    tip_sha = manifest["tip_commit_sha"]
    problems = resolve_problems(task_ids)

    ckpt = out_dir / ("n1_dryrun.jsonl" if dry_run else "n1_campaign.jsonl")
    done = load_checkpoint(ckpt)
    sem = asyncio.Semaphore(concurrency)
    results: List[SampleResult] = []
    pending = []

    for tid in task_ids:
        for arm in arms:
            for s in range(samples_per_task):
                k = _key(tid, arm, s)
                if k in done:
                    row = done[k]
                    results.append(
                        SampleResult(
                            task_id=row["task_id"],
                            arm=row["arm"],
                            sample=row["sample"],
                            pass_=bool(row["pass"]),
                            pilot_pass=bool(row["pilot_pass"]),
                            exact_critic_pass=bool(row["exact_critic_pass"]),
                            contract_pass=bool(row.get("contract_pass", False)),
                            error_class=row.get("error_class", ""),
                            repair_rounds=int(row.get("repair_rounds", 0)),
                            tokens=int(row.get("tokens", 0)),
                            model_id=row.get("model_id", ""),
                            tip_sha=row.get("tip_sha", tip_sha),
                            problems=(
                                row.get("problems", "").split(" | ")
                                if row.get("problems")
                                else []
                            ),
                        )
                    )
                    continue
                pending.append((tid, arm, s))

    async def _one(tid: int, arm: str, s: int) -> SampleResult:
        try:
            r = await run_arm_sample(
                arm=arm,
                task_id=tid,
                sample=s,
                problem_text=problems[tid]["description"],
                llm=llm,
                tip_sha=tip_sha,
                require_model_pin=require_model_pin,
                sem=sem,
            )
        except Exception as e:  # noqa: BLE001 — never abort whole campaign
            r = SampleResult(
                task_id=tid,
                arm=arm,
                sample=s,
                pass_=False,
                pilot_pass=False,
                exact_critic_pass=False,
                contract_pass=False,
                error_class="wrong_connectivity",
                repair_rounds=0,
                tokens=0,
                model_id=getattr(llm, "model_id", ""),
                tip_sha=tip_sha,
                problems=[f"uncaught:{type(e).__name__}: {e}"],
            )
        append_checkpoint(ckpt, r)
        return r

    if pending:
        # Chunked gather so a hung API call cannot stall the entire campaign;
        # checkpoint resume skips completed (task, arm, sample) keys.
        chunk_size = max(concurrency * 4, 16)
        for i in range(0, len(pending), chunk_size):
            chunk = pending[i : i + chunk_size]
            print(
                f"[n1] launching chunk {i // chunk_size + 1}/"
                f"{(len(pending) + chunk_size - 1) // chunk_size} "
                f"({len(chunk)} samples)",
                flush=True,
            )
            batch = await asyncio.gather(
                *[_one(tid, arm, s) for tid, arm, s in chunk],
                return_exceptions=False,
            )
            results.extend(batch)

    rows = [r.to_csv_row() for r in results]
    csv_name = "n1_dryrun.csv" if dry_run else results_csv_name
    write_csv(out_dir / csv_name, rows)
    # Always mirror PIC-Bench-48 headline name when requested.
    if results_csv_name == "n1_results_picbench48.csv" and not dry_run:
        write_csv(out_dir / "n1_results_picbench48.csv", rows)
    (out_dir / "n1_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    _print_summary(results)
    return results


def _print_summary(results: Sequence[SampleResult]) -> None:
    print("=== N1 headline pass (A: ExactCritic; B/C: ExactCritic∧TaskContract) ===")
    cis = []
    for arm in N1_ABLATION_ARMS:
        arm_res = [r for r in results if r.arm == arm]
        ci = summarize_arm_passes(r.pass_ for r in arm_res)
        cis.append(ci)
        print(f"  {arm}: {format_ci(ci)}")
    if no_win_claim(cis):
        print("  (Wilson CIs overlap → no win claim)")
    print("=== ExactCritic-only (diagnostic) ===")
    for arm in N1_ABLATION_ARMS:
        arm_res = [r for r in results if r.arm == arm]
        ci = summarize_arm_passes(r.exact_critic_pass for r in arm_res)
        print(f"  {arm}: {format_ci(ci)}")
    print("=== N1 pilot_pass (Arm A baseline signal) ===")
    for arm in N1_ABLATION_ARMS:
        arm_res = [r for r in results if r.arm == arm]
        ci = summarize_arm_passes(r.pilot_pass for r in arm_res)
        print(f"  {arm}: {format_ci(ci)}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="N1 three-arm ablation campaign")
    p.add_argument("--dry-run", action="store_true", help="Tasks 34,36 only; allow unpinned model")
    p.add_argument("--campaign", action="store_true", help="Full campaign; requires model pin")
    p.add_argument(
        "--picbench48",
        action="store_true",
        help="Use all 48 PIC-Bench tasks; write n1_results_picbench48.csv",
    )
    p.add_argument("--mock", action="store_true", help="Use MockLLM (no API)")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_REPO_ROOT / "gd_picasso" / "pcg" / "n1_runs",
    )
    p.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Skip clean-worktree gate (dev only)",
    )
    p.add_argument("--samples", type=int, default=None, help="Override samples/task")
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Live model id (default: N1_LIVE_MODEL env or claude-haiku-4-5-20251001)",
    )
    args = p.parse_args(argv)

    if args.campaign and args.dry_run:
        p.error("choose one of --dry-run or --campaign")
    if not args.campaign and not args.dry_run:
        args.dry_run = True  # safe default

    if args.dry_run:
        task_ids = list(N1_DRY_RUN_TASK_IDS)
        results_csv = "n1_dryrun.csv"
    elif args.picbench48:
        task_ids = list(PICBENCH48_TASK_IDS)
        results_csv = "n1_results_picbench48.csv"
    else:
        task_ids = list(N1_TASK_SUBSET)
        results_csv = "n1_results.csv"
    samples = args.samples if args.samples is not None else (
        1 if args.dry_run else N1_SAMPLES_PER_TASK
    )

    if args.mock:
        llm: Any = MockLLM()
    else:
        if not n1_campaign_ready() and args.campaign:
            raise SystemExit("Refuse --campaign while N1_LLM_MODEL_ID unpinned")
        if n1_campaign_ready():
            model = N1_LLM_MODEL_ID
        else:
            model = (
                args.model
                or os.environ.get("N1_LIVE_MODEL")
                or "claude-haiku-4-5-20251001"
            )
        print(
            f"WARNING: live run using model={model!r} "
            f"(protocol pin still {N1_LLM_MODEL_ID!r})"
        )
        llm = build_live_llm(model)

    results = asyncio.run(
        run_campaign(
            task_ids=task_ids,
            samples_per_task=samples,
            llm=llm,
            out_dir=args.out_dir,
            require_clean=not args.allow_dirty,
            require_model_pin=bool(args.campaign),
            concurrency=args.concurrency,
            dry_run=bool(args.dry_run),
            results_csv_name=results_csv,
        )
    )
    usage = getattr(llm, "usage", None)
    if usage is not None and not args.mock:
        mid = getattr(llm, "model_id", "unknown")
        cost = estimate_cost_usd(mid, usage)
        print("=== Token / cost estimate (list prices; not an invoice) ===")
        print(
            f"  model={mid} calls={usage.calls} "
            f"input_tok={usage.input_tokens} output_tok={usage.output_tokens} "
            f"total_tok={usage.total_tokens}"
        )
        if cost == cost:  # not NaN
            print(f"  estimated_usd≈${cost:.4f}")
        else:
            print("  estimated_usd=unknown (no price table entry for model)")
        cost_path = args.out_dir / "n1_cost_estimate.json"
        cost_path.parent.mkdir(parents=True, exist_ok=True)
        cost_path.write_text(
            json.dumps(
                {
                    "model_id": mid,
                    "calls": usage.calls,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "estimated_usd": None if cost != cost else round(cost, 6),
                    "n_results": len(results),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  wrote {cost_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
