"""Factory functions for host-graph topologies."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

from .embedding import HostGraph


def _add_bidirectional_edge(host: HostGraph, src: int, dst: int, *, weight: float = 1.0) -> None:
    if (src, dst) in host.edges:
        return
    host.add_edge(src, dst, weight=weight)
    host.add_edge(dst, src, weight=weight)


def build_smartlight_mesh(
    *,
    rows: int = 12,
    cols: int = 6,
    input_ports: int = 20,
    output_ports: int = 20,
    base_weight: float = 1.0,
) -> HostGraph:
    """Return a host graph approximating the 72-PUC Smartlight mesh.

    The mesh is modelled as a skewed rectangular lattice where every PUC can act as
    a phase shifter, splitter, or a unitary block.  Each PUC is represented as a node
    that connects horizontally and diagonally to its neighbours, mimicking the
    hexagonal routing pattern shown in the Smartlight laboratory simulator manual.

    Parameters
    ----------
    rows, cols:
        Dimensions of the mesh.  The default (12 x 6) yields 72 PUCs as described in
        the manual.
    input_ports, output_ports:
        Number of electrical/optical I/O ports to model.  These are attached to the
        first (west) and last (east) columns, respectively.
    base_weight:
        Default edge weight used for the lattice connections.  This can be tuned to
        bias the ILP objective when minimising path length.
    """

    num_pucs = rows * cols
    host = HostGraph()

    def puc_index(row: int, col: int) -> int:
        return row * cols + col

    def puc_pos(row: int, col: int) -> Tuple[float, float]:
        x = float(col)
        y = -(row + 0.5 * (col % 2))
        return (x, y)

    # Add one host node per PUC with geometric positions.
    for r in range(rows):
        for c in range(cols):
            idx = puc_index(r, c)
            host.add_node(
                idx,
                labels={"phase", "splitter", "unitary"},
                pos=puc_pos(r, c),
            )

    # Connectivity mimicking the staggered Smartlight lattice.
    for r in range(rows):
        for c in range(cols):
            node = puc_index(r, c)

            if c + 1 < cols:
                _add_bidirectional_edge(host, node, puc_index(r, c + 1), weight=base_weight)

            if r + 1 < rows:
                _add_bidirectional_edge(host, node, puc_index(r + 1, c), weight=base_weight)

            if c % 2 == 0:
                if r > 0:
                    _add_bidirectional_edge(host, node, puc_index(r - 1, c), weight=base_weight)
                if r > 0 and c + 1 < cols:
                    _add_bidirectional_edge(host, node, puc_index(r - 1, c + 1), weight=base_weight)
            else:
                if r + 1 < rows:
                    _add_bidirectional_edge(host, node, puc_index(r + 1, c), weight=base_weight)
                if r + 1 < rows and c + 1 < cols:
                    _add_bidirectional_edge(host, node, puc_index(r + 1, c + 1), weight=base_weight)

    port_index = num_pucs
    for i in range(input_ports):
        row = i % rows
        host.add_node(
            port_index + i,
            labels={"input_port"},
            pos=(puc_pos(row, 0)[0] - 1.0, puc_pos(row, 0)[1]),
        )
        host.add_edge(port_index + i, puc_index(row, 0), weight=base_weight)

    output_start = port_index + input_ports
    for i in range(output_ports):
        row = i % rows
        host.add_node(
            output_start + i,
            labels={"output_port"},
            pos=(puc_pos(row, cols - 1)[0] + 1.0, puc_pos(row, cols - 1)[1]),
        )
        host.add_edge(puc_index(row, cols - 1), output_start + i, weight=base_weight)

    return host


def build_feedforward_mesh(
    *,
    rows: int = 12,
    cols: int = 6,
    input_ports: int = 20,
    output_ports: int = 20,
    base_weight: float = 1.0,
) -> HostGraph:
    """Return a directed, feedforward mesh host graph.

    This host is a layered lattice intended to model a "feedforward" routing fabric:
    edges always advance from column ``c`` to ``c+1`` (never backwards). Each PUC
    connects to the same row and adjacent rows in the next column, providing limited
    lateral movement while remaining acyclic.

    Parameters
    ----------
    rows, cols:
        Dimensions of the PUC lattice.
    input_ports, output_ports:
        Number of electrical/optical I/O ports to attach to the first and last
        columns, respectively.
    base_weight:
        Default edge weight used for lattice connections.
    """

    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive")
    if input_ports < 0 or output_ports < 0:
        raise ValueError("input_ports/output_ports must be non-negative")

    num_pucs = rows * cols
    host = HostGraph()

    def puc_index(row: int, col: int) -> int:
        return row * cols + col

    def puc_pos(row: int, col: int) -> Tuple[float, float]:
        x = float(col)
        y = -(row + 0.5 * (col % 2))
        return (x, y)

    for r in range(rows):
        for c in range(cols):
            idx = puc_index(r, c)
            host.add_node(
                idx,
                labels={"phase", "splitter", "unitary"},
                pos=puc_pos(r, c),
            )

    # Feedforward connectivity: only from column c to c+1.
    for r in range(rows):
        for c in range(cols - 1):
            src = puc_index(r, c)
            for dr in (-1, 0, 1):
                rr = r + dr
                if 0 <= rr < rows:
                    host.add_edge(src, puc_index(rr, c + 1), weight=base_weight)

    port_index = num_pucs
    for i in range(input_ports):
        row = i % rows
        host.add_node(
            port_index + i,
            labels={"input_port"},
            pos=(puc_pos(row, 0)[0] - 1.0, puc_pos(row, 0)[1]),
        )
        host.add_edge(port_index + i, puc_index(row, 0), weight=base_weight)

    output_start = port_index + input_ports
    for i in range(output_ports):
        row = i % rows
        host.add_node(
            output_start + i,
            labels={"output_port"},
            pos=(puc_pos(row, cols - 1)[0] + 1.0, puc_pos(row, cols - 1)[1]),
        )
        host.add_edge(puc_index(row, cols - 1), output_start + i, weight=base_weight)

    return host


def build_triangle_mesh(
    *,
    rows: int = 12,
    cols: int = 6,
    input_ports: int = 20,
    output_ports: int = 20,
    base_weight: float = 1.0,
) -> HostGraph:
    """Return a bidirectional triangular lattice host graph.

    The lattice uses a staggered row layout where each PUC connects to six nearby
    neighbours, forming a triangular tiling. Ports attach to the west/east columns.
    """

    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive")
    if input_ports < 0 or output_ports < 0:
        raise ValueError("input_ports/output_ports must be non-negative")

    num_pucs = rows * cols
    host = HostGraph()

    def puc_index(row: int, col: int) -> int:
        return row * cols + col

    def puc_pos(row: int, col: int) -> Tuple[float, float]:
        x = float(col) + 0.5 * (row % 2)
        y = -row * (math.sqrt(3) / 2.0)
        return (x, y)

    for r in range(rows):
        for c in range(cols):
            idx = puc_index(r, c)
            host.add_node(
                idx,
                labels={"phase", "splitter", "unitary"},
                pos=puc_pos(r, c),
            )

    even_offsets = [(0, -1), (0, 1), (-1, -1), (-1, 0), (1, -1), (1, 0)]
    odd_offsets = [(0, -1), (0, 1), (-1, 0), (-1, 1), (1, 0), (1, 1)]

    for r in range(rows):
        for c in range(cols):
            src = puc_index(r, c)
            offsets = even_offsets if r % 2 == 0 else odd_offsets
            for dr, dc in offsets:
                rr = r + dr
                cc = c + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    _add_bidirectional_edge(host, src, puc_index(rr, cc), weight=base_weight)

    port_index = num_pucs
    for i in range(input_ports):
        row = i % rows
        host.add_node(
            port_index + i,
            labels={"input_port"},
            pos=(puc_pos(row, 0)[0] - 1.0, puc_pos(row, 0)[1]),
        )
        host.add_edge(port_index + i, puc_index(row, 0), weight=base_weight)

    output_start = port_index + input_ports
    for i in range(output_ports):
        row = i % rows
        host.add_node(
            output_start + i,
            labels={"output_port"},
            pos=(puc_pos(row, cols - 1)[0] + 1.0, puc_pos(row, cols - 1)[1]),
        )
        host.add_edge(puc_index(row, cols - 1), output_start + i, weight=base_weight)

    return host


def build_lab_simulator_mesh(
    *,
    rows: int = 6,
    cols: int = 12,
    base_weight: float = 1.0,
) -> HostGraph:
    

    host = HostGraph()

    def puc_index(row: int, col: int) -> int:
        return col * rows + row

    def puc_pos(row: int, col: int) -> Tuple[float, float]:
        x = float(col)
        y = -(row + 0.5 * (col % 2))
        return (x, y)

    # Add PUC nodes (indices 0..71 when rows=6, cols=12).
    for col in range(cols):
        for row in range(rows):
            host.add_node(
                puc_index(row, col),
                labels={"phase", "splitter", "unitary"},
                pos=puc_pos(row, col),
            )

    # Hexagonal connectivity (borrowed from build_smartlight_mesh but with transposed indexing).
    for col in range(cols):
        for row in range(rows):
            node = puc_index(row, col)

            if col + 1 < cols:
                _add_bidirectional_edge(host, node, puc_index(row, col + 1), weight=base_weight)

            if col % 2 == 0:
                if row > 0 and col + 1 < cols:
                    _add_bidirectional_edge(host, node, puc_index(row - 1, col + 1), weight=base_weight)
            else:
                if row + 1 < rows and col + 1 < cols:
                    _add_bidirectional_edge(host, node, puc_index(row + 1, col + 1), weight=base_weight)

    num_pucs = rows * cols

    # Port layout (clockwise starting from top-left). Values are (column, row, dx, dy).
    port_layout: List[Tuple[int, int, float, float]] = []

    # Top edge (left to right)
    for col in range(cols):
        port_layout.append((col, 0, 0.0, 1.2))

    # Right edge (top to bottom, repeat rows to reach eight ports)
    right_rows = [0, 1, 2, 3, 4, 5, 2, 4]
    for row in right_rows:
        port_layout.append((cols - 1, row, 1.2, 0.0))

    # Bottom edge (right to left)
    for col in reversed(range(cols)):
        port_layout.append((col, rows - 1, 0.0, -1.2))

    # Left edge (bottom to top, repeat to fill remaining slots)
    left_rows = [5, 4, 3, 2, 1, 0, 3, 1]
    for row in left_rows:
        port_layout.append((0, row, -1.2, 0.0))

    assert len(port_layout) == 40, "port layout should yield 40 connectors"

    for offset, (col, row, dx, dy) in enumerate(port_layout):
        node_id = num_pucs + offset
        x, y = puc_pos(row, col)
        host.add_node(
            node_id,
            labels={"input_port", "output_port"},
            name=f"port_{offset}",
            pos=(x + dx, y + dy),
        )
        _add_bidirectional_edge(host, node_id, puc_index(row, col), weight=base_weight)

    return host


# LAB_SIMULATOR_REFERENCE_CONFIG: Dict[int, Tuple[str, float]] = {
#     **{puc: ("inactive", 0.0) for puc in range(72)},
#     0: ("cross", 1.0),
#     2: ("cross", 1.0),
#     6: ("bar", 0.0),
#     7: ("splitter", 0.5),
#     9: ("cross", 1.0),
#     11: ("cross", 1.0),
#     15: ("bar", 0.0),
#     16: ("cross", 1.0),
#     19: ("bar", 0.0),
#     20: ("bar", 0.0),
# }
