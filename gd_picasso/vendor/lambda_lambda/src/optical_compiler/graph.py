"""Graph representation for compiled photonic programs."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from itertools import count
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Label:
    kind: str
    value: Optional[object] = None


@dataclass(frozen=True)
class Edge:
    src: int
    dst: int


@dataclass
class NodeData:
    label: Label
    sigma: Optional[str] = None
    value: Optional[object] = None

    def copy(self) -> "NodeData":
        return replace(self)


class GraphBuilder:
    """Supply fresh node identifiers."""

    def __init__(self) -> None:
        self._supply = count()

    def fresh(self) -> int:
        return next(self._supply)


@dataclass
class GraphFragment:
    builder: GraphBuilder
    nodes: Dict[int, NodeData] = field(default_factory=dict)
    edges: Set[Edge] = field(default_factory=set)
    outputs: Dict[int, int] = field(default_factory=dict)  # node -> slot
    placeholders: Dict[int, str] = field(default_factory=dict)  # node -> name
    placeholder_slots: Dict[int, int] = field(default_factory=dict)

    def copy(self) -> "GraphFragment":
        return GraphFragment(
            builder=self.builder,
            nodes={n: data.copy() for n, data in self.nodes.items()},
            edges=set(self.edges),
            outputs=dict(self.outputs),
            placeholders=dict(self.placeholders),
            placeholder_slots=dict(self.placeholder_slots),
        )

    def add_node(
        self,
        label: Label,
        *,
        sigma: Optional[str] = None,
        value: Optional[object] = None,
        output_slot: Optional[int] = None,
        placeholder_slot: Optional[int] = None,
    ) -> int:
        node = self.builder.fresh()
        self.nodes[node] = NodeData(label=label, sigma=sigma, value=value)
        if sigma is not None:
            self.placeholders[node] = sigma
        if placeholder_slot is not None:
            self.placeholder_slots[node] = placeholder_slot
        if output_slot is not None:
            self.outputs[node] = output_slot
        return node

    def add_edge(self, src: int, dst: int) -> None:
        self.edges.add(Edge(src=src, dst=dst))

    def extend_outputs(self, mapping: Dict[int, int]) -> None:
        self.outputs.update(mapping)

    def remove_output(self, node: int) -> None:
        self.outputs.pop(node, None)

    def union_inplace(self, other: "GraphFragment") -> None:
        overlapping = set(self.nodes).intersection(other.nodes)
        if overlapping:
            raise ValueError(f"node id clash during union: {overlapping}")
        self.nodes.update({n: d.copy() for n, d in other.nodes.items()})
        self.edges.update(other.edges)
        self.outputs.update(other.outputs)
        self.placeholders.update(other.placeholders)
        self.placeholder_slots.update(other.placeholder_slots)

    def indegree(self, node: int) -> int:
        return sum(1 for e in self.edges if e.dst == node)

    def outdegree(self, node: int) -> int:
        return sum(1 for e in self.edges if e.src == node)

    def connected_from(self, node: int) -> List[int]:
        return [e.dst for e in self.edges if e.src == node]

    def connected_to(self, node: int) -> List[int]:
        return [e.src for e in self.edges if e.dst == node]

    def substitute_placeholder(
        self,
        var_name: str,
        replacement: "GraphFragment",
        slot_to_slot: Optional[Dict[int, int]] = None,
        *,
        reuse_existing: bool = False,
    ) -> None:
        """Splice ``replacement`` in place of every placeholder for ``var_name``."""
        occurrences = [
            node for node, name in self.placeholders.items() if name == var_name
        ]
        if not occurrences:
            raise ValueError(f"placeholder for {var_name} not found")

        if reuse_existing:
            overlapping = set(self.nodes).intersection(replacement.nodes)
            if overlapping and not all(
                self.nodes[o].label == replacement.nodes[o].label for o in overlapping
            ):
                raise ValueError("incompatible reuse of nodes during substitution")
            for edge in replacement.edges:
                if edge not in self.edges:
                    self.edges.add(edge)
            for node, slot in replacement.outputs.items():
                if node not in self.outputs:
                    self.outputs[node] = slot
        else:
            self.union_inplace(replacement)
        for node in occurrences:
            outgoing = [e for e in self.edges if e.src == node]
            incoming = [e for e in self.edges if e.dst == node]
            if incoming:
                raise ValueError("placeholders should not have incoming edges")

            slot = self.placeholder_slots.get(node)
            slot_map = slot_to_slot or {}

            if slot is None:
                slot = 1

            desired_slot = slot_map.get(slot, slot)
            candidate = None
            for out_node, out_slot in replacement.outputs.items():
                if out_slot == desired_slot:
                    candidate = out_node
                    break
            if candidate is None:
                raise ValueError(
                    f"replacement for {var_name} lacks slot {desired_slot}"
                )

            for edge in outgoing:
                self.edges.remove(edge)
                self.edges.add(Edge(src=candidate, dst=edge.dst))

            if node in self.outputs:
                slot_value = self.outputs.pop(node)
                self.outputs[candidate] = slot_value

            self.nodes.pop(node, None)
            self.placeholders.pop(node, None)
            self.placeholder_slots.pop(node, None)

    def remove_placeholders(self, names: Iterable[str]) -> None:
        obsolete = {n for n, name in self.placeholders.items() if name in names}
        for node in obsolete:
            self.nodes.pop(node, None)
            self.placeholders.pop(node, None)
            self.placeholder_slots.pop(node, None)
            self.outputs.pop(node, None)
            # Remove dangling edges if present.
            self.edges = {e for e in self.edges if e.src != node and e.dst != node}

    def prune_outputs(self, keep_slots: Iterable[int]) -> None:
        keep = set(keep_slots)
        to_remove = [node for node, slot in self.outputs.items() if slot not in keep]
        for node in to_remove:
            self.outputs.pop(node, None)


def merge_graphs(fragments: Iterable[GraphFragment]) -> GraphFragment:
    fragments = list(fragments)
    if not fragments:
        raise ValueError("nothing to merge")
    base = fragments[0].copy()
    for fragment in fragments[1:]:
        base.union_inplace(fragment)
    return base
