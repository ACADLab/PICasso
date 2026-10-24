#!/usr/bin/env python3
"""Symbolic executor for the photonic calculus AST.

It computes how outputs depend linearly on inputs, returning both an
output-to-input matrix and the per-output symbolic expressions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union, Iterable, Set

import sympy as sp

from optical_compiler import ast as oc_ast

# A Signal is a linear combination of inputs: sum_k coeff[k] * input(k)
Signal = Dict[int, sp.Expr]
PairVal = Tuple[Signal, Signal]
Value = Union[Signal, PairVal, sp.Expr, None]


class SymbolicExecError(Exception):
    """Raised when the symbolic executor hits an unsupported construct."""


def _basis(idx: int) -> Signal:
    return {idx: sp.Integer(1)}


def _add_signals(*signals: Signal) -> Signal:
    out: Signal = {}
    for sig in signals:
        for k, v in sig.items():
            out[k] = out.get(k, 0) + v
    return {k: sp.simplify(v) for k, v in out.items() if v != 0}


def _scale_signal(sig: Signal, scalar: sp.Expr) -> Signal:
    if scalar == 1:
        return dict(sig)
    return {k: sp.simplify(scalar * v) for k, v in sig.items()}


def _apply_2x2(matrix: Iterable[Iterable[complex]], s0: Signal, s1: Signal) -> PairVal:
    """Apply a 2x2 unitary to two signals."""
    m = sp.Matrix(matrix)
    if m.shape != (2, 2):
        raise SymbolicExecError(f"unitary expects 2x2, got {m.shape}")
    a, b, c, d = m[0, 0], m[0, 1], m[1, 0], m[1, 1]
    out0 = _add_signals(_scale_signal(s0, a), _scale_signal(s1, b))
    out1 = _add_signals(_scale_signal(s0, c), _scale_signal(s1, d))
    return out0, out1


@dataclass
class ExecResult:
    outputs: Dict[int, Signal]
    inputs: List[int]
    matrix: sp.Matrix
    expressions: Dict[int, sp.Expr]


def execute_symbolic(expr: oc_ast.Expr) -> ExecResult:
    """
    Execute a program symbolically.

    Returns:
        ExecResult with:
          - outputs: port -> Signal mapping
          - inputs: sorted list of input indices encountered
          - matrix: (#outputs x #inputs) sympy Matrix of coefficients

    Notes:
        Split is interpreted as amplitude splitting: left *= sqrt(ratio),
        right *= sqrt(1 - ratio).
    """
    env: Dict[str, Value] = {}
    outputs: Dict[int, Signal] = {}
    seen_inputs: Set[int] = set()

    def eval_expr(e: oc_ast.Expr) -> Value:
        if isinstance(e, oc_ast.Input):
            seen_inputs.add(e.index)
            return _basis(e.index)

        if isinstance(e, oc_ast.Var):
            if e.name not in env:
                raise SymbolicExecError(f"unbound variable {e.name}")
            val = env.pop(e.name)
            return val

        if isinstance(e, oc_ast.Number):
            return sp.Float(e.value)

        if isinstance(e, oc_ast.ComplexLiteral):
            return sp.nsimplify(e.value)

        if isinstance(e, oc_ast.MatrixLiteral):
            return sp.Matrix([[sp.nsimplify(v) for v in row] for row in e.entries])

        if isinstance(e, oc_ast.UnitLiteral):
            return None

        if isinstance(e, oc_ast.Let):
            val = eval_expr(e.value)
            env[e.name] = val
            result = eval_expr(e.body)
            if e.name in env:
                # Linear usage check: binding must be consumed.
                env.pop(e.name)
                raise SymbolicExecError(f"linear variable {e.name} not consumed in body")
            return result

        if isinstance(e, oc_ast.LetOutput):
            val = eval_expr(e.value)
            if not isinstance(val, dict):
                raise SymbolicExecError("output expects an optical signal")
            outputs[e.port] = val
            return eval_expr(e.body)

        if isinstance(e, oc_ast.Phase):
            val = eval_expr(e.signal)
            if not isinstance(val, dict):
                raise SymbolicExecError("phase expects an optical signal")
            theta_raw = sp.nsimplify(e.theta)
            ratio = sp.nsimplify(theta_raw / sp.pi)
            if ratio.is_rational:
                theta = sp.simplify(ratio * sp.pi)
            else:
                theta = sp.Float(e.theta)
            phase = sp.simplify(sp.exp(sp.I * theta))
            return _scale_signal(val, phase)

        if isinstance(e, oc_ast.Split):
            val = eval_expr(e.signal)
            if not isinstance(val, dict):
                raise SymbolicExecError("split expects an optical signal")
            r = sp.Float(e.ratio)
            return (
                _scale_signal(val, sp.sqrt(r)),
                _scale_signal(val, sp.sqrt(1 - r)),
            )

        if isinstance(e, oc_ast.Pair):
            left = eval_expr(e.left)
            right = eval_expr(e.right)
            if not isinstance(left, dict) or not isinstance(right, dict):
                raise SymbolicExecError("pair currently supports optical signals only")
            return (left, right)

        if isinstance(e, oc_ast.Unitary):
            val = eval_expr(e.signal)
            if not (isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], dict) and isinstance(val[1], dict)):
                raise SymbolicExecError("unitary expects a pair of optical signals")
            return _apply_2x2(e.matrix, val[0], val[1])

        if isinstance(e, oc_ast.Unpack):
            val = eval_expr(e.pair_expr)
            if not (isinstance(val, tuple) and len(val) == 2):
                raise SymbolicExecError("unpack expects a pair")
            env[e.left_name] = val[0]
            env[e.right_name] = val[1]
            result = eval_expr(e.body)
            missing = [name for name in (e.left_name, e.right_name) if name in env]
            for name in (e.left_name, e.right_name):
                env.pop(name, None)
            if missing:
                raise SymbolicExecError(f"linear variables not consumed in unpack body: {', '.join(missing)}")
            return result

        raise SymbolicExecError(f"unsupported expression: {e!r}")

    eval_expr(expr)
    if env:
        raise SymbolicExecError(f"linear variables not consumed: {', '.join(sorted(env))}")

    input_list = sorted(seen_inputs)
    out_ports = sorted(outputs)
    sym_inputs = {idx: sp.Symbol(f"input({idx})") for idx in input_list}

    expressions: Dict[int, sp.Expr] = {}
    if input_list:
        rows: List[List[sp.Expr]] = []
        for p in out_ports:
            sig = outputs[p]
            row = [sp.simplify(sig.get(idx, 0)) for idx in input_list]
            rows.append(row)
            expr = sp.Add(*[sym_inputs[i] * sig.get(i, 0) for i in input_list], evaluate=True)
            expressions[p] = sp.simplify(expr)
        matrix = sp.Matrix(rows)
    else:
        matrix = sp.Matrix.zeros(len(out_ports), 0)
        expressions = {p: sp.Integer(0) for p in out_ports}

    return ExecResult(outputs=outputs, inputs=input_list, matrix=matrix, expressions=expressions)


if __name__ == "__main__":  # simple smoke test
    prog = oc_ast.LetOutput(
        port=1,
        value=oc_ast.Phase(
            signal=oc_ast.Input(1),
            theta=0.5,
        ),
        body=oc_ast.UnitLiteral(),
    )
    res = execute_symbolic(prog)
    print("inputs:", res.inputs)
    print("outputs:", res.outputs)
    print("matrix:", res.matrix)
