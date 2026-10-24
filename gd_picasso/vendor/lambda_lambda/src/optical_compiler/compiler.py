"""Compilation of photonic calculus expressions to signal graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Sequence, Tuple

from . import ast
from .graph import GraphBuilder, GraphFragment, Label, merge_graphs
from .typesys import (
    OPTICAL,
    REAL,
    UNIT,
    TupleType,
    Type,
    UnitaryType,
)


class CompileError(Exception):
    pass


@dataclass
@dataclass
class VarBinding:
    typ: Type
    slot: Optional[int] = None


@dataclass
class CompileContext:
    vars: Dict[str, VarBinding] = field(default_factory=dict)
    available_inputs: Optional[Dict[int, Type]] = None
    used_inputs: Dict[int, Type] = field(default_factory=dict)
    used_outputs: Dict[int, Type] = field(default_factory=dict)

    def copy(self) -> "CompileContext":
        return CompileContext(
            vars=dict(self.vars),
            available_inputs=None
            if self.available_inputs is None
            else dict(self.available_inputs),
            used_inputs=dict(self.used_inputs),
            used_outputs=dict(self.used_outputs),
        )

    def bind_var(self, name: str, typ: Type, slot: Optional[int] = None) -> None:
        if name in self.vars:
            raise CompileError(f"duplicate binding for {name}")
        self.vars[name] = VarBinding(typ=typ, slot=slot)

    def pop_var(self, name: str) -> VarBinding:
        if name not in self.vars:
            raise CompileError(f"unbound variable {name}")
        return self.vars.pop(name)

    def consume_input(self, index: int) -> None:
        if self.available_inputs is not None:
            if index not in self.available_inputs:
                raise CompileError(f"unexpected input({index})")
            typ = self.available_inputs.pop(index)
        else:
            typ = OPTICAL
        self.used_inputs[index] = typ

    def reserve_output(self, index: int) -> None:
        if index in self.used_outputs:
            raise CompileError(f"output({index}) written twice")
        self.used_outputs[index] = OPTICAL


@dataclass
class CompileResult:
    graph: GraphFragment
    typ: Type


class Compiler:
    def __init__(self) -> None:
        self.builder = GraphBuilder()

    def compile(
        self,
        expr: ast.Expr,
        *,
        inputs: Optional[Dict[int, Type]] = None,
    ) -> CompileResult:
        ctx = CompileContext(available_inputs=dict(inputs) if inputs else None)
        result = self._compile(expr, ctx)
        if ctx.vars:
            leftover = ", ".join(ctx.vars)
            raise CompileError(f"linear variables not consumed: {leftover}")
        return result

    def _compile(self, expr: ast.Expr, ctx: CompileContext) -> CompileResult:
        if isinstance(expr, ast.Input):
            ctx.consume_input(expr.index)
            fragment = GraphFragment(self.builder)
            port_node = fragment.add_node(
                Label("input_port", expr.index),
            )
            wire_node = fragment.add_node(Label("wire"), output_slot=1)
            fragment.add_edge(port_node, wire_node)
            return CompileResult(fragment, OPTICAL)

        if isinstance(expr, ast.Var):
            binding = ctx.pop_var(expr.name)
            typ = binding.typ
            slot = binding.slot or 1
            fragment = GraphFragment(self.builder)
            if isinstance(typ, TupleType):
                fragment.add_node(
                    Label("placeholder"),
                    sigma=expr.name,
                    output_slot=1,
                    placeholder_slot=1,
                )
                fragment.add_node(
                    Label("placeholder"),
                    sigma=expr.name,
                    output_slot=2,
                    placeholder_slot=2,
                )
                return CompileResult(fragment, typ)
            placeholder = fragment.add_node(
                Label("placeholder"),
                sigma=expr.name,
                output_slot=1,
                placeholder_slot=slot,
            )
            return CompileResult(fragment, typ)

        if isinstance(expr, ast.Number):
            return CompileResult(GraphFragment(self.builder), REAL)

        if isinstance(expr, ast.UnitLiteral):
            return CompileResult(GraphFragment(self.builder), UNIT)

        if isinstance(expr, ast.MatrixLiteral):
            return CompileResult(GraphFragment(self.builder), UnitaryType())

        if isinstance(expr, ast.Let):
            value_res = self._compile(expr.value, ctx)
            ctx.bind_var(expr.name, value_res.typ)
            body_res = self._compile(expr.body, ctx)
            if expr.name in ctx.vars:
                raise CompileError(f"{expr.name} not consumed in body")
            graph = body_res.graph.copy()
            graph.substitute_placeholder(expr.name, value_res.graph)
            return CompileResult(graph, body_res.typ)

        if isinstance(expr, ast.LetOutput):
            value_res = self._compile(expr.value, ctx)
            ctx.reserve_output(expr.port)
            out_graph = value_res.graph.copy()
            out_slot = next(iter(out_graph.outputs.values()), None)
            if out_slot != 1 or len(out_graph.outputs) != 1:
                raise CompileError("output binding expects a single optical signal")
            (signal_node,) = out_graph.outputs.keys()
            out_port = out_graph.add_node(Label("output_port", expr.port))
            out_graph.add_edge(signal_node, out_port)
            body_res = self._compile(expr.body, ctx)
            merged = merge_graphs([out_graph, body_res.graph])
            merged.remove_output(signal_node)
            merged.outputs.update(body_res.graph.outputs)
            return CompileResult(merged, body_res.typ)

        if isinstance(expr, ast.Phase):
            signal_res = self._compile(expr.signal, ctx)
            if signal_res.typ != OPTICAL:
                raise CompileError("phase expects an optical signal")
            graph = signal_res.graph.copy()
            if len(graph.outputs) != 1:
                raise CompileError("phase expects single output from argument")
            source_node = next(iter(graph.outputs))
            graph.remove_output(source_node)
            phase_node = graph.add_node(Label("phase", expr.theta))
            graph.add_edge(source_node, phase_node)
            out_node = graph.add_node(Label("wire"), output_slot=1)
            graph.add_edge(phase_node, out_node)
            return CompileResult(graph, OPTICAL)

        if isinstance(expr, ast.Split):
            signal_res = self._compile(expr.signal, ctx)
            if signal_res.typ != OPTICAL:
                raise CompileError("split expects an optical signal")
            graph = signal_res.graph.copy()
            if len(graph.outputs) != 1:
                raise CompileError("split expects single output from argument")
            source_node = next(iter(graph.outputs))
            graph.remove_output(source_node)
            split_node = graph.add_node(Label("splitter", expr.ratio))
            graph.add_edge(source_node, split_node)
            left = graph.add_node(Label("wire"), output_slot=1)
            right = graph.add_node(Label("wire"), output_slot=2)
            graph.add_edge(split_node, left)
            graph.add_edge(split_node, right)
            return CompileResult(graph, TupleType(OPTICAL, OPTICAL))

        if isinstance(expr, ast.Pair):
            left_res = self._compile(expr.left, ctx)
            right_res = self._compile(expr.right, ctx)
            if left_res.typ != OPTICAL or right_res.typ != OPTICAL:
                raise CompileError("pair currently supports optical signals only")
            left_graph = left_res.graph
            right_graph = right_res.graph
            combined = merge_graphs([left_graph, right_graph])
            outputs = {}
            if len(left_graph.outputs) != 1 or len(right_graph.outputs) != 1:
                raise CompileError("pair expects both sides to be optical")
            outputs.update({next(iter(left_graph.outputs)): 1})
            outputs.update({next(iter(right_graph.outputs)): 2})
            combined.outputs = outputs
            return CompileResult(combined, TupleType(left_res.typ, right_res.typ))

        if isinstance(expr, ast.Unitary):
            signal_res = self._compile(expr.signal, ctx)
            if not isinstance(signal_res.typ, TupleType):
                raise CompileError("unitary expects a pair of optical signals")
            graph = signal_res.graph.copy()
            if len(graph.outputs) != 2:
                raise CompileError("unitary expects two outputs from argument")
            ordered = sorted(graph.outputs.items(), key=lambda kv: kv[1])
            first_node, second_node = ordered[0][0], ordered[1][0]
            graph.remove_output(first_node)
            graph.remove_output(second_node)
            unitary_node = graph.add_node(Label("unitary", expr.matrix))
            graph.add_edge(first_node, unitary_node)
            graph.add_edge(second_node, unitary_node)
            out1 = graph.add_node(Label("wire"), output_slot=1)
            out2 = graph.add_node(Label("wire"), output_slot=2)
            graph.add_edge(unitary_node, out1)
            graph.add_edge(unitary_node, out2)
            return CompileResult(graph, TupleType(OPTICAL, OPTICAL))

        if isinstance(expr, ast.Unpack):
            pair_res = self._compile(expr.pair_expr, ctx)
            if not isinstance(pair_res.typ, TupleType):
                raise CompileError("unpack expects a pair")
            ctx.bind_var(expr.left_name, pair_res.typ.left, slot=1)
            ctx.bind_var(expr.right_name, pair_res.typ.right, slot=2)
            body_res = self._compile(expr.body, ctx)
            for name in (expr.left_name, expr.right_name):
                if name in ctx.vars:
                    raise CompileError(f"{name} not consumed in unpack body")
            graph = body_res.graph.copy()
            slot_map = {1: 1, 2: 2}
            graph.substitute_placeholder(expr.left_name, pair_res.graph, slot_map)
            graph.substitute_placeholder(
                expr.right_name, pair_res.graph, slot_map, reuse_existing=True
            )
            return CompileResult(graph, body_res.typ)

        raise CompileError(f"unsupported expression: {expr!r}")
