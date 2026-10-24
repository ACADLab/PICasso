"""Abstract syntax tree definitions for the photonic calculus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


class Expr:
    """Base class for all expressions."""


@dataclass(frozen=True)
class Input(Expr):
    index: int


@dataclass(frozen=True)
class Var(Expr):
    name: str


@dataclass(frozen=True)
class Let(Expr):
    name: str
    value: Expr
    body: Expr


@dataclass(frozen=True)
class LetOutput(Expr):
    port: int
    value: Expr
    body: Expr


@dataclass(frozen=True)
class Phase(Expr):
    signal: Expr
    theta: float


@dataclass(frozen=True)
class Split(Expr):
    signal: Expr
    ratio: float


@dataclass(frozen=True)
class Unitary(Expr):
    matrix: Sequence[Sequence[complex]]
    signal: Expr


@dataclass(frozen=True)
class Pair(Expr):
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Unpack(Expr):
    pair_expr: Expr
    left_name: str
    right_name: str
    body: Expr


@dataclass(frozen=True)
class Number(Expr):
    value: float


@dataclass(frozen=True)
class ComplexLiteral(Expr):
    value: complex


@dataclass(frozen=True)
class MatrixLiteral(Expr):
    entries: Tuple[Tuple[complex, complex], Tuple[complex, complex]]


@dataclass(frozen=True)
class UnitLiteral(Expr):
    """Represents () in the calculus."""

