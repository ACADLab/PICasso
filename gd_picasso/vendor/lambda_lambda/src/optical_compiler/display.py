"""Utility helpers for pretty-printing programs and visualising graphs."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections import defaultdict
from itertools import cycle
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import networkx as nx  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    nx = None  # type: ignore

try:
    import matplotlib  # type: ignore

    matplotlib.use("Agg")  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    plt = None  # type: ignore

ENABLE_NETWORKX_RENDER = (
    os.environ.get("OPTICAL_COMPILER_ENABLE_NETWORKX", "1") != "0"
    and nx is not None
    and plt is not None
)

from . import ast
from .embedding import ComponentGraph, HostGraph
from .graph import GraphFragment


def format_expr(expr: ast.Expr, indent: int = 0) -> str:
    """Return a human-readable, indented representation of an expression."""

    space = "  " * indent

    if isinstance(expr, ast.Input):
        return f"{space}input({expr.index})"
    if isinstance(expr, ast.Var):
        return f"{space}{expr.name}"
    if isinstance(expr, ast.Number):
        return f"{space}{expr.value}"
    if isinstance(expr, ast.UnitLiteral):
        return f"{space}()"
    if isinstance(expr, ast.ComplexLiteral):
        return f"{space}{expr.value}"
    if isinstance(expr, ast.MatrixLiteral):
        rows = [
            "[" + ", ".join(f"{value!r}" for value in row) + "]"
            for row in expr.entries
        ]
        return f"{space}matrix(\n" + "\n".join(f"{space}  {row}" for row in rows) + f"\n{space})"
    if isinstance(expr, ast.Unitary):
        matrix_rows = [
            "[" + ", ".join(f"{value!r}" for value in row) + "]" for row in expr.matrix
        ]
        matrix_repr = "\n".join(f"{space}    {row}" for row in matrix_rows)
        signal_repr = format_expr(expr.signal, indent + 2)
        return (
            f"{space}unitary(\n"
            f"{space}  U =\n{matrix_repr}\n"
            f"{space}  signal=\n{signal_repr}\n"
            f"{space})"
        )
    if isinstance(expr, ast.Phase):
        signal = format_expr(expr.signal, indent + 1)
        return f"{space}phase(theta={expr.theta},\n{signal}\n{space})"
    if isinstance(expr, ast.Split):
        signal = format_expr(expr.signal, indent + 1)
        return f"{space}split(ratio={expr.ratio},\n{signal}\n{space})"
    if isinstance(expr, ast.Pair):
        left = format_expr(expr.left, indent + 1)
        right = format_expr(expr.right, indent + 1)
        return f"{space}pair(\n{left},\n{right}\n{space})"
    if isinstance(expr, ast.Let):
        value = format_expr(expr.value, indent + 1)
        body = format_expr(expr.body, indent + 1)
        return f"{space}let {expr.name} =\n{value}\n{space}in\n{body}"
    if isinstance(expr, ast.LetOutput):
        value = format_expr(expr.value, indent + 1)
        body = format_expr(expr.body, indent + 1)
        return f"{space}let output({expr.port}) =\n{value}\n{space}in\n{body}"
    if isinstance(expr, ast.Unpack):
        pair = format_expr(expr.pair_expr, indent + 1)
        body = format_expr(expr.body, indent + 1)
        return (
            f"{space}unpack ({expr.left_name}, {expr.right_name}) =\n"
            f"{pair}\n{space}in\n{body}"
        )

    return f"{space}{expr!r}"


def _node_label(kind: str, value: object | None) -> str:
    return kind if value is None else f"{kind}\\n{value!r}"


def _format_scalar(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, complex):
        real = value.real
        imag = value.imag
        return f"{real:.4g}{imag:+.4g}j"
    return str(value)


def _matrix_dims(value: object) -> Optional[Tuple[int, int]]:
    if not isinstance(value, (list, tuple)):
        return None
    if not value:
        return None
    first_row = value[0]
    if not isinstance(first_row, (list, tuple)):
        return None
    cols = len(first_row)
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != cols:
            return None
    return len(value), cols


def _format_param_for_label(label: Optional[str], param: object | None) -> str:
    if param is None:
        return ""
    if label in {"splitter", "coupler"}:
        return f"ratio={_format_scalar(param)}"
    if label in {"phase", "phase_shifter"}:
        return f"theta={_format_scalar(param)}"
    if label == "unitary":
        dims = _matrix_dims(param)
        if dims is not None:
            rows, cols = dims
            return f"U={rows}x{cols}"
        return "U"
    if isinstance(param, (int, float, complex)):
        return f"param={_format_scalar(param)}"
    return f"param={param}"


def _resolve_host_metadata(
    node_id: int,
    node: object,
    assignments: Optional[Dict[int, str]],
    params: Optional[Dict[int, object]],
) -> Tuple[Optional[str], Optional[object]]:
    chosen = assignments.get(node_id) if assignments else None
    if chosen is None:
        chosen = getattr(node, "assigned_label", None)
    param_value = params.get(node_id) if params else None
    if param_value is None:
        param_value = getattr(node, "assigned_param", None)
    return chosen, param_value


def _host_label_lines(
    node,
    chosen_label: Optional[str],
    param_value: object | None,
    show_name: bool,
) -> List[str]:
    lines: List[str] = []
    if chosen_label:
        lines.append(chosen_label)
    else:
        if node.candidates:
            lines.append(", ".join(sorted(node.candidates)))
    param_text = _format_param_for_label(chosen_label, param_value)
    if param_text:
        lines.append(param_text)
    return lines


def graph_fragment_summary(graph: GraphFragment, title: str) -> str:
    lines = [f"--- {title} ---", "Nodes:"]
    for node_id, data in sorted(graph.nodes.items()):
        if data.label.kind == "wire":
            continue
        lines.append(
            f"  {node_id}: {data.label.kind} value={data.label.value!r} sigma={data.sigma!r}"
        )
    lines.append("Edges:")
    for edge in sorted(graph.edges, key=lambda e: (e.src, e.dst)):
        if graph.nodes[edge.src].label.kind == "wire" or graph.nodes[edge.dst].label.kind == "wire":
            continue
        lines.append(f"  {edge.src} -> {edge.dst}")
    if graph.outputs:
        lines.append("Outputs:")
        for node, slot in sorted(graph.outputs.items()):
            if graph.nodes[node].label.kind == "wire":
                continue
            lines.append(f"  node {node} slot {slot}")
    return "\n".join(lines)


def graph_fragment_to_dot(
    graph: GraphFragment,
    name: str = "graph",
    *,
    collapse_wires: bool = True,
    show_wire_slots: bool = False,
) -> str:
    wire_nodes = {
        node_id
        for node_id, data in graph.nodes.items()
        if data.label.kind == "wire"
    }

    lines = [f"digraph {name} {{"]
    for node_id, data in sorted(graph.nodes.items()):
        if node_id in wire_nodes and collapse_wires:
            continue
        if data.label.kind == "wire":
            slot = graph.outputs.get(node_id)
            if show_wire_slots and slot is not None:
                label = f"wire\\nslot={slot}"
            else:
                label = "wire"
        else:
            label = _node_label(data.label.kind, data.label.value)
        lines.append(f'  {node_id} [label="{label}"];')

    if collapse_wires:
        edges_to_render: Set[Tuple[int, int]] = set()
        for edge in graph.edges:
            if edge.src in wire_nodes or edge.dst in wire_nodes:
                continue
            edges_to_render.add((edge.src, edge.dst))

        # collapse wire nodes by connecting predecessors directly to successors
        if wire_nodes:
            preds: Dict[int, List[int]] = defaultdict(list)
            succs: Dict[int, List[int]] = defaultdict(list)
            for edge in graph.edges:
                if edge.dst in wire_nodes:
                    preds[edge.dst].append(edge.src)
                if edge.src in wire_nodes:
                    succs[edge.src].append(edge.dst)
            for wire in wire_nodes:
                for p in preds.get(wire, []):
                    if p in wire_nodes:
                        continue
                    for s in succs.get(wire, []):
                        if s in wire_nodes:
                            continue
                        edges_to_render.add((p, s))

        for src, dst in sorted(edges_to_render):
            lines.append(f"  {src} -> {dst};")
    else:
        for edge in sorted(graph.edges, key=lambda e: (e.src, e.dst)):
            lines.append(f"  {edge.src} -> {edge.dst};")
    lines.append("}")
    return "\n".join(lines)


def component_graph_summary(component: ComponentGraph, title: str) -> str:
    lines = [f"--- {title} ---"]
    for node_id, node in sorted(component.nodes.items()):
        lines.append(
            f"  {node_id}: {node.label.kind} indeg={node.indegree} outdeg={node.outdegree}"
        )
    lines.append("Edges:")
    for src, dst, slot in sorted(component.edges):
        lines.append(f"  {src} -[{slot}]-> {dst}")
    return "\n".join(lines)


def component_graph_to_dot(component: ComponentGraph, name: str = "component") -> str:
    lines = [f"digraph {name} {{"]
    for node_id, node in sorted(component.nodes.items()):
        lines.append(
            f'  {node_id} [label="{_node_label(node.label.kind, node.label.value)}"];'
        )
    for src, dst, slot in sorted(component.edges):
        lines.append(f'  {src} -> {dst} [label="slot {slot}"];')
    lines.append("}")
    return "\n".join(lines)


def host_graph_summary(
    host: HostGraph,
    title: str,
    assignments: Optional[Dict[int, str]] = None,
    params: Optional[Dict[int, object]] = None,
) -> str:
    lines = [f"--- {title} ---", "Nodes:"]
    for node_id, node in sorted(host.nodes.items()):
        chosen, param_value = _resolve_host_metadata(
            node_id, node, assignments, params
        )
        label_text = chosen or ", ".join(sorted(node.candidates))
        param_text = _format_param_for_label(chosen, param_value)
        if param_text:
            lines.append(
                f"  {node_id}: host={node.name} label={label_text} {param_text}"
            )
        else:
            lines.append(f"  {node_id}: host={node.name} label={label_text}")
    lines.append("Edges:")
    for (src, dst), weight in sorted(host.edges.items()):
        lines.append(f"  {src} -> {dst} (weight={weight})")
    return "\n".join(lines)


def host_graph_to_dot(
    host: HostGraph,
    name: str = "host",
    *,
    highlight_paths: list[list[tuple[int, int]]] | None = None,
    assignments: Optional[Dict[int, str]] = None,
    params: Optional[Dict[int, object]] = None,
    include_weights: bool = True,
    show_host_names: bool = True,
    node_width: float = 0.4,
    highlight_penwidth: float = 2.8,
    stretch_x: float = 1.0,
    color_labeled_nodes: bool = False,
    node_font_size: float = 10.0,
) -> str:
    highlight_styles: dict[tuple[int, int], tuple[str, float]] = {}
    palette = ["#d62728", "#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"]
    if highlight_paths:
        for idx, path in enumerate(highlight_paths):
            color = palette[idx % len(palette)]
            for edge in path:
                if edge in host.edges:
                    highlight_styles[edge] = (color, highlight_penwidth)

    lines = [f"digraph {name} {{"]
    lines.append("  graph [layout=neato, overlap=false, splines=true];")
    lines.append(
        f"  node [shape=circle, width={node_width:.3f}, fontsize={node_font_size:.1f}];"
    )
    pink_nodes = set()
    for node_id, node in sorted(host.nodes.items()):
        chosen, param_value = _resolve_host_metadata(
            node_id, node, assignments, params
        )
        label_lines = _host_label_lines(node, chosen, param_value, show_host_names)
        if show_host_names:
            label_lines.append(f"mode={node.name}")
        label_lines.append(f"id={node_id}")
        label = "\\n".join(label_lines)
        pos_attr = ""
        if node.pos is not None:
            x, y = node.pos
            pos_attr = f', pos="{x * stretch_x},{y}!"'
        fill_attr = ""
        assigned_kind = chosen or getattr(node, "assigned_label", None)
        if color_labeled_nodes:
            if assigned_kind == "unitary":
                fill_attr = ', style="filled", fillcolor="#ff6b6b"'
            elif assigned_kind in {"input_port", "output_port"}:
                fill_attr = ', style="filled", fillcolor="#ffe066"'
        else:
            if assigned_kind == "unitary":
                fill_attr = ', style="filled", fillcolor="#ffc0cb"'
                pink_nodes.add(node_id)
            elif assigned_kind in {"input_port", "output_port"}:
                fill_attr = ', style="filled", fillcolor="#fee090"'
        lines.append(f'  {node_id} [label="{label}"{pos_attr}{fill_attr}];')
    for (src, dst), weight in sorted(host.edges.items()):
        attrs = []
        if include_weights:
            attrs.append(f'label="{weight}"')
        if (src, dst) in highlight_styles:
            color, penwidth = highlight_styles[(src, dst)]
            attrs.append(f'color="{color}"')
            attrs.append(f'penwidth="{penwidth}"')
            attrs.append(f'fontcolor="{color}"')
        lines.append(f"  {src} -> {dst} [{', '.join(attrs)}];")
    lines.append("}")
    return "\n".join(lines)


def print_dot(title: str, dot_source: str) -> None:
    print(f"\nDOT ({title}):")
    print(dot_source)


def export_graphviz(
    dot_source: str,
    *,
    directory: Path,
    stem: str,
    render: bool = True,
    fmt: str = "png",
) -> tuple[Path, Path | None]:
    """Persist DOT text and optionally render via ``dot`` if available."""

    directory.mkdir(parents=True, exist_ok=True)
    dot_path = directory / f"{stem}.dot"
    dot_path.write_text(dot_source, encoding="utf-8")

    png_path: Path | None = None
    if render and (dot_bin := shutil.which("dot")):
        png_path = directory / f"{stem}.{fmt}"
        try:
            subprocess.run(
                [dot_bin, f"-T{fmt}", str(dot_path), "-o", str(png_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            png_path = None
    return dot_path, png_path


def render_host_with_paths(
    host: HostGraph,
    highlight_paths: list[list[tuple[int, int]]] | None,
    *,
    directory: Path,
    stem: str,
    render: bool = True,
    assignments: Optional[Dict[int, str]] = None,
    params: Optional[Dict[int, object]] = None,
    include_weights: bool = True,
    show_host_names: bool = True,
    node_size: float = 850.0,
    font_size: float = 8.0,
    show_edge_weights: bool = True,
    arrow_style: str = "-|>",
    arrow_size: float = 14.0,
    base_edge_width: float = 1.2,
    highlight_edge_width: float = 3.2,
    color_labeled_nodes: bool = False,
) -> dict[str, Path | None]:
    """Generate DOT/Graphviz output and, if possible, a NetworkX visualisation."""

    directory.mkdir(parents=True, exist_ok=True)
    highlight_paths = highlight_paths or []
    dot_source = host_graph_to_dot(
        host,
        name=stem,
        highlight_paths=highlight_paths,
        assignments=assignments,
        params=params,
        include_weights=include_weights,
        show_host_names=show_host_names,
        node_width=max(0.15, node_size / 2000.0),
        stretch_x=1.5,
        color_labeled_nodes=color_labeled_nodes,
        node_font_size=font_size,
    )
    dot_path, graphviz_png = export_graphviz(
        dot_source,
        directory=directory,
        stem=stem,
        render=render,
    )

    networkx_png: Path | None = None
    if ENABLE_NETWORKX_RENDER and render:
        G = nx.DiGraph()
        node_labels = {}
        for node_id, node in host.nodes.items():
            G.add_node(node_id)
            chosen, param_value = _resolve_host_metadata(
                node_id, node, assignments, params
            )
            lines = _host_label_lines(node, chosen, param_value, show_host_names)
            if show_host_names:
                lines.append(f"mode={node.name}")
            lines.append(f"id={node_id}")
            node_labels[node_id] = "\n".join(lines)
        for (src, dst), weight in host.edges.items():
            G.add_edge(src, dst, weight=weight)

        edge_colors = defaultdict(lambda: "#b0b0b0")
        edge_widths = defaultdict(lambda: base_edge_width)
        palette = cycle(["#d62728", "#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b"])
        for color, path in zip(palette, highlight_paths):
            for edge in path:
                if edge in G.edges:
                    edge_colors[edge] = color
                    edge_widths[edge] = highlight_edge_width

        if all(node.pos is not None for node in host.nodes.values()):
            pos = {node_id: host.nodes[node_id].pos for node_id in G.nodes}
        else:
            pos = nx.spring_layout(G, seed=42)
        fig, ax = plt.subplots(figsize=(6, 5))

        style_groups: Dict[Tuple[str, str, float], list[int]] = defaultdict(list)
        for node_id, node in host.nodes.items():
            assigned = assignments.get(node_id) if assignments else None
            if assigned is None:
                assigned = getattr(node, "assigned_label", None)
            if assigned in {"input_port", "output_port"}:
                style = ("#ffe066", "#c97e00", node_size * 0.9)
            elif assigned == "unitary":
                if color_labeled_nodes:
                    style = ("#ff6b6b", "#b22222", node_size)
                else:
                    style = ("#ffc0cb", "#b22222", node_size * 1.05)
            else:
                style = ("#cfe2ff", "#245192", node_size)
            style_groups[style].append(node_id)
        for (color, edgecolor, size), nodes in style_groups.items():
            nx.draw_networkx_nodes(
                G,
                pos,
                nodelist=nodes,
                node_color=color,
                edgecolors=edgecolor,
                linewidths=1.2,
                node_size=size,
                ax=ax,
            )
        nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=font_size, ax=ax)

        color_groups: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for edge in G.edges:
            color_groups[edge_colors[edge]].append(edge)

        for color, edges in color_groups.items():
            widths = [edge_widths[e] for e in edges]
            nx.draw_networkx_edges(
                G,
                pos,
                edgelist=edges,
                edge_color=color,
                width=widths,
                arrows=True,
                arrowstyle=arrow_style,
                arrowsize=arrow_size,
                ax=ax,
            )

        if show_edge_weights:
            weight_attrs = nx.get_edge_attributes(G, "weight")
            for (u, v), weight in weight_attrs.items():
                x = (pos[u][0] + pos[v][0]) / 2
                y = (pos[u][1] + pos[v][1]) / 2
                ax.text(
                    x,
                    y,
                    f"{weight}",
                    fontsize=max(6, font_size),
                    color=edge_colors[(u, v)],
                    bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=1.0),
                )

        ax.axis("off")
        fig.tight_layout()
        networkx_png = directory / f"{stem}_networkx.png"
        fig.savefig(networkx_png, dpi=160)
        plt.close(fig)

    return {"dot": dot_path, "graphviz": graphviz_png, "networkx": networkx_png}
