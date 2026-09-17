"""
Append-only mutation journal for PCGStore.

Every successful checked mutation appends a MutationRecord. Agents and
reproducibility tooling consume this; the store never rewrites history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MutationRecord(BaseModel):
    """One validated mutation that was committed to the store."""

    seq: int
    op: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    agent: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    topology_hash_after: Optional[str] = None


class MutationJournal:
    """Append-only log; consumers get a copy via ``entries``."""

    def __init__(self) -> None:
        self._entries: List[MutationRecord] = []

    @property
    def entries(self) -> List[MutationRecord]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def append(
        self,
        op: str,
        payload: Dict[str, Any],
        *,
        agent: Optional[str] = None,
        topology_hash_after: Optional[str] = None,
    ) -> MutationRecord:
        rec = MutationRecord(
            seq=len(self._entries),
            op=op,
            payload=dict(payload),
            agent=agent,
            topology_hash_after=topology_hash_after,
        )
        self._entries.append(rec)
        return rec

    def clear(self) -> None:
        """Test helper — production agents should not clear history."""
        self._entries.clear()
