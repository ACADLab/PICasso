"""Load PIC-Set NL problem statements for the N1 campaign."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBLEMS_FILE = _REPO_ROOT / "gd_picasso" / "problems_parsed.txt"


def load_problems(problems_file: Optional[Path] = None) -> List[Dict]:
    """Parse TASK/Problem file into [{id, name, description}, ...]."""
    path = Path(problems_file) if problems_file else DEFAULT_PROBLEMS_FILE
    if not path.is_file():
        raise FileNotFoundError(f"Problems file not found: {path}")

    problems: List[Dict] = []
    current: Optional[Dict] = None
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if stripped.startswith("TASK ") or stripped.startswith("Problem "):
                if current:
                    current["description"] = "\n".join(current["description_lines"])
                    del current["description_lines"]
                    problems.append(current)
                parts = stripped.split(" - ", 1)
                if len(parts) == 2:
                    header, name = parts[0].strip(), parts[1].strip()
                else:
                    parts = stripped.split(":", 1)
                    header = parts[0].strip()
                    name = parts[1].strip() if len(parts) == 2 else ""
                if header.startswith("TASK "):
                    pid = header.replace("TASK ", "").split()[0]
                elif header.startswith("Problem "):
                    pid = header.replace("Problem ", "").split()[0]
                else:
                    pid = str(len(problems) + 1)
                # strip parenthetical noise from id
                pid = "".join(ch for ch in pid if ch.isdigit()) or pid
                current = {
                    "id": pid,
                    "name": name,
                    "description_lines": [],
                }
            elif current is not None and stripped:
                current["description_lines"].append(stripped)
    if current:
        current["description"] = "\n".join(current["description_lines"])
        del current["description_lines"]
        problems.append(current)
    return problems


def problems_by_id(
    task_ids: Sequence[int],
    problems_file: Optional[Path] = None,
) -> Dict[int, Dict]:
    """Map int task_id → problem dict; raise if any id missing."""
    loaded = load_problems(problems_file)
    by_id: Dict[int, Dict] = {}
    for p in loaded:
        try:
            tid = int(p["id"])
        except (TypeError, ValueError):
            continue
        by_id[tid] = p
    missing = [t for t in task_ids if t not in by_id]
    if missing:
        raise KeyError(f"Missing problem statements for task ids: {missing}")
    return {t: by_id[t] for t in task_ids}
