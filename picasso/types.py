"""Shared type hints (kept small on purpose)."""
from typing import TypedDict, List, Dict, Optional

class DesignRecord(TypedDict, total=False):
    id: str
    prompt: str
    code: str
    reports: Dict[str, Dict]
    passed: bool
