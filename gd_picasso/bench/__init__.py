"""PIC-Bench-48 CVDP-style package surface.

Public API:
  ``load_benchmark()`` — catalog of 48 tasks with contracts / fixture paths
  ``evaluate_submission(task_id, store_candidate)`` — ExactCritic ∧ TaskContract
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from gd_picasso.agents.exact_critic import ExactCritic, ExactCritique
from gd_picasso.bench.contracts import (
    TASK_CONTRACTS,
    TaskContract,
    contract_failures,
    evaluate_task_contract,
    get_task_contract,
)
from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.build_formal_benchmarks import (
    PICSET,
    UNREALIZABLE_TASKS,
    gf_fixture_path,
    picbench_catalog,
    reject_unrealizable,
)
from gd_picasso.pcg.store import PCGStore

__all__ = [
    "TaskContract",
    "BenchTaskInfo",
    "SubmissionResult",
    "load_benchmark",
    "load_golden_store",
    "evaluate_submission",
    "evaluate_task_contract",
    "get_task_contract",
    "TASK_CONTRACTS",
]


@dataclass(frozen=True)
class BenchTaskInfo:
    task_id: int
    name: str
    kind: str  # gf | unrealizable
    fixture_path: Optional[Path]
    contract: Optional[TaskContract]


@dataclass(frozen=True)
class SubmissionResult:
    ok: bool
    task_id: int
    exact_critic_ok: bool
    contract_ok: bool
    exact_problems: List[str]
    contract_problems: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "task_id": self.task_id,
            "exact_critic_ok": self.exact_critic_ok,
            "contract_ok": self.contract_ok,
            "exact_problems": list(self.exact_problems),
            "contract_problems": list(self.contract_problems),
        }


def load_benchmark() -> List[BenchTaskInfo]:
    """Load the PIC-Bench-48 catalog (46 GF fixtures + 2 unrealizable specs)."""
    out: List[BenchTaskInfo] = []
    for task in picbench_catalog():
        if task.kind == "unrealizable":
            out.append(
                BenchTaskInfo(
                    task_id=task.task_id,
                    name=task.name,
                    kind="unrealizable",
                    fixture_path=None,
                    contract=None,
                )
            )
            continue
        path = gf_fixture_path(task.task_id)
        out.append(
            BenchTaskInfo(
                task_id=task.task_id,
                name=task.name,
                kind="gf",
                fixture_path=path if path.is_file() else path,
                contract=get_task_contract(task.task_id),
            )
        )
    return out


def evaluate_submission(task_id: int, store_candidate: PCGStore) -> SubmissionResult:
    """Score a candidate store: ExactCritic.review().ok AND TaskContract.

    Unrealizable tasks (47–48) always fail structural evaluation — callers
    should use ``reject_unrealizable`` for the PSD gate.
    """
    if task_id in UNREALIZABLE_TASKS:
        return SubmissionResult(
            ok=False,
            task_id=task_id,
            exact_critic_ok=False,
            contract_ok=False,
            exact_problems=["task is unrealizable (psd_gate reject)"],
            contract_problems=["no TaskContract for unrealizable tasks"],
        )
    contract = get_task_contract(task_id)
    if contract is None:
        return SubmissionResult(
            ok=False,
            task_id=task_id,
            exact_critic_ok=False,
            contract_ok=False,
            exact_problems=[f"unknown task_id {task_id}"],
            contract_problems=[f"unknown task_id {task_id}"],
        )
    critique: ExactCritique = ExactCritic().review(store_candidate)
    c_ok = evaluate_task_contract(store_candidate, contract)
    return SubmissionResult(
        ok=bool(critique.ok) and c_ok,
        task_id=task_id,
        exact_critic_ok=bool(critique.ok),
        contract_ok=c_ok,
        exact_problems=list(critique.problems),
        contract_problems=contract_failures(store_candidate, contract),
    )


def load_golden_store(task_id: int) -> PCGStore:
    """Load the golden GF fixture for a realizable task."""
    path = gf_fixture_path(task_id)
    if not path.is_file():
        raise FileNotFoundError(path)
    return from_gf_yaml(path.read_text())
