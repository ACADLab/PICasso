"""Type definitions and small helpers for the photonic calculus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


class Type:
    """Base class for all types."""

    def __repr__(self) -> str:  # pragma: no cover - convenience
        return self.__class__.__name__


@dataclass(frozen=True)
class RealType(Type):
    pass


@dataclass(frozen=True)
class OpticalType(Type):
    pass


@dataclass(frozen=True)
class UnitaryType(Type):
    dimension: int = 2


@dataclass(frozen=True)
class UnitType(Type):
    pass


@dataclass(frozen=True)
class TupleType(Type):
    left: Type
    right: Type


REAL = RealType()
OPTICAL = OpticalType()
UNIT = UnitType()


def flatten_tuple_type(t: Type) -> Dict[int, Type]:
    """Return a slot-indexed view for tuple types."""
    if isinstance(t, TupleType):
        return {1: t.left, 2: t.right}
    return {1: t}

