"""Utilities for interpreting lab-mesh switch states."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union, TYPE_CHECKING

from .embedding import HostGraph

if TYPE_CHECKING:  # pragma: no cover - type checking aid
    from .embedding import EmbeddingResult

PUC_LABELS = {"phase", "splitter", "unitary"}


@dataclass(frozen=True)
class InactiveSwitchSpec:
    """Interpretation table for a passive PUC.

    Attributes
    ----------
    default_state:
        Returned when no routed path touches the node. Typically ``"bar"``.
    pair_states:
        Mapping from unordered neighbour pairs to the state string that real hardware
        should assume when those ports are used for transit routing.
    """

    default_state: str = "bar"
    pair_states: Mapping[frozenset[int], str] = field(default_factory=dict)

    def classify(self, neighbours: Iterable[int]) -> str:
        """Return the configured state for the given neighbour set."""

        normalized = frozenset(neighbours)
        if not normalized:
            return self.default_state
        if len(normalized) != 2:
            raise ValueError(
                f"passive PUCs should connect exactly two neighbours, got {sorted(normalized)}"
            )
        state = self.pair_states.get(normalized)
        if state is None:
            raise KeyError(
                f"no state registered for neighbour pair {sorted(normalized)}"
            )
        return state


def _collect_used_neighbours(edge_paths: Mapping[Tuple[int, int], Sequence[Tuple[int, int]]]) -> Dict[int, Set[int]]:
    used: Dict[int, Set[int]] = defaultdict(set)
    for path in edge_paths.values():
        for src, dst in path:
            used[src].add(dst)
            used[dst].add(src)
    return used


def derive_switch_dictionary(
    host: "HostGraph",
    embedding: "EmbeddingResult",
    inactive_specs: Mapping[int, InactiveSwitchSpec],
) -> Dict[int, Dict[str, Optional[object]]]:
    """Return a node->state dictionary (bar/cross/middle) for a solved embedding.

    Middle-state entries (phase/splitter/unitary components) include their parameter.
    Passive nodes rely on ``inactive_specs`` to decide whether a routed neighbour pair
    should be treated as ``bar`` or ``cross``.
    """

    used_neighbours = _collect_used_neighbours(embedding.edge_paths)
    states: Dict[int, Dict[str, Optional[object]]] = {}

    for node_id, host_node in host.nodes.items():
        if not (PUC_LABELS & host_node.candidates):
            continue

        assigned_label = embedding.host_assignments.get(node_id)
        if assigned_label in PUC_LABELS:
            states[node_id] = {
                "state": "middle",
                "component": assigned_label,
                "value": embedding.host_params.get(node_id),
            }
            continue

        spec = inactive_specs.get(node_id, InactiveSwitchSpec())
        neighbours = used_neighbours.get(node_id, set())
        state = spec.classify(neighbours)
        states[node_id] = {
            "state": state,
            "component": None,
            "value": None,
        }

    return states


def _resolve_node_ref(ref: object, aliases: Optional[Mapping[str, int]]) -> int:
    if isinstance(ref, int):
        return ref
    if isinstance(ref, str):
        if aliases and ref in aliases:
            return aliases[ref]
        if ref.isdigit():
            return int(ref)
    raise ValueError(f"unknown node reference {ref!r}")


def _inactive_spec_from_entry(
    entry: Mapping[str, object],
    aliases: Optional[Mapping[str, int]],
) -> InactiveSwitchSpec:
    default_state = entry.get("default", "bar")
    pairs_section = entry.get("pairs", {})
    if not isinstance(pairs_section, Mapping):
        raise ValueError("switching 'pairs' must be a mapping")

    pair_states: Dict[frozenset[int], str] = {}
    for state_name, combos in pairs_section.items():
        if not isinstance(combos, Sequence):
            raise ValueError(f"neighbour combos for state {state_name!r} must be a list")
        for combo in combos:
            if not isinstance(combo, Sequence) or len(combo) != 2:
                raise ValueError(f"neighbour pairs must be 2-element lists: {combo!r}")
            src = _resolve_node_ref(combo[0], aliases)
            dst = _resolve_node_ref(combo[1], aliases)
            normalized = frozenset({src, dst})
            if normalized in pair_states:
                raise ValueError(
                    f"neighbour pair {sorted(normalized)} assigned twice"
                )
            pair_states[normalized] = str(state_name)

    return InactiveSwitchSpec(
        default_state=str(default_state),
        pair_states=pair_states,
    )


def _collect_aliases(nodes_section: Sequence[Mapping[str, object]]) -> Dict[str, int]:
    aliases: Dict[str, int] = {}
    for entry in nodes_section:
        raw_id = entry.get("id")
        internal = entry.get("internal_id")
        node_id: Optional[int] = None
        if internal is not None:
            try:
                node_id = int(internal)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError(f"internal_id must be numeric: {internal!r}") from exc
        elif isinstance(raw_id, int):
            node_id = raw_id
        elif isinstance(raw_id, str) and raw_id.isdigit():
            node_id = int(raw_id)

        if node_id is None:
            continue

        aliases[str(node_id)] = node_id
        if raw_id is not None:
            aliases[str(raw_id)] = node_id
    return aliases


def _collect_inline_switch_specs(
    nodes_section: Sequence[Mapping[str, object]],
    aliases: Mapping[str, int],
) -> Dict[int, InactiveSwitchSpec]:
    specs: Dict[int, InactiveSwitchSpec] = {}
    for entry in nodes_section:
        switch_entry = entry.get("switching")
        if not isinstance(switch_entry, Mapping):
            continue
        node_ref = entry.get("internal_id", entry.get("id"))
        node_id = _resolve_node_ref(node_ref, aliases)
        specs[node_id] = _inactive_spec_from_entry(switch_entry, aliases)
    return specs


def _parse_switch_table(
    raw: Mapping[str, object],
    aliases: Optional[Mapping[str, int]] = None,
) -> Dict[int, InactiveSwitchSpec]:
    if not isinstance(raw, Mapping):
        return {}

    specs: Dict[int, InactiveSwitchSpec] = {}
    node_payload: Mapping[str, object]

    graph_section = raw.get("graph")
    if isinstance(graph_section, Mapping):
        nodes_section = graph_section.get("nodes")
        if isinstance(nodes_section, Sequence):
            alias_lookup = aliases or _collect_aliases(nodes_section)
            specs.update(_collect_inline_switch_specs(nodes_section, alias_lookup))
            aliases = alias_lookup
        switch_section = raw.get("switch_table", {})
        node_payload = switch_section if isinstance(switch_section, Mapping) else {}
    else:
        node_payload = raw

    node_section = node_payload.get("nodes", node_payload)
    if not isinstance(node_section, Mapping):
        return specs

    for key, entry in node_section.items():
        if not isinstance(entry, Mapping):
            raise ValueError(f"node entry for {key!r} must be an object")
        try:
            node_id = _resolve_node_ref(key, aliases)
        except ValueError:
            if isinstance(key, str) and key.isdigit():
                node_id = int(key)
            else:
                continue
        specs[node_id] = _inactive_spec_from_entry(entry, aliases)

    return specs


def load_puc_switch_table(path: Union[str, Path]) -> Dict[int, InactiveSwitchSpec]:
    """Load the switch table (bar/cross interpretation) from ``path``."""

    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, Mapping):
        raise ValueError("switch table JSON must be an object")
    return _parse_switch_table(raw)


def load_host_graph_from_json(
    path: Union[str, Path],
) -> Tuple[HostGraph, Dict[int, InactiveSwitchSpec]]:
    """Construct a host graph (and optional switch table) from a JSON description.

    Nodes may now embed their side groups, adjacency, and switching behaviour directly.
    Each node must list ``labels`` and may optionally specify ``id`` (string) and
    ``internal_id`` (numeric).  When present, ``connections`` is treated as a list of
    outgoing edges, and ``sides`` mirrors ``port_groups`` but can reference node aliases
    instead of raw integers.
    """

    data = json.loads(Path(path).read_text())
    if not isinstance(data, Mapping):
        raise ValueError("host graph JSON must be an object")

    graph_section = data.get("graph")
    if not isinstance(graph_section, Mapping):
        raise ValueError("JSON must include a 'graph' object")

    nodes_section = graph_section.get("nodes")
    if not isinstance(nodes_section, Sequence):
        raise ValueError("'graph' must contain a 'nodes' list")

    alias_lookup: Dict[str, int] = {}
    assigned_ids: Set[int] = set()
    next_auto_id = 0

    def allocate_node_id(entry: Mapping[str, object]) -> int:
        nonlocal next_auto_id
        node_id: Optional[int] = None
        if isinstance(entry.get("internal_id"), (int, float)):
            node_id = int(entry["internal_id"])
        elif isinstance(entry.get("id"), int):
            node_id = entry["id"]
        elif isinstance(entry.get("id"), str) and entry["id"].isdigit():
            node_id = int(entry["id"])

        if node_id is None:
            while next_auto_id in assigned_ids:
                next_auto_id += 1
            node_id = next_auto_id
            next_auto_id += 1

        if node_id in assigned_ids:
            raise ValueError(f"duplicate node identifier {node_id}")
        assigned_ids.add(node_id)
        return node_id

    for entry in nodes_section:
        if not isinstance(entry, Mapping):
            raise ValueError("each node entry must be an object")
        if "labels" not in entry:
            raise ValueError("node entries must include 'labels'")
        resolved_id = allocate_node_id(entry)
        entry["_resolved_id"] = resolved_id
        raw_id = entry.get("id")
        if raw_id is not None:
            alias_lookup[str(raw_id)] = resolved_id
        alias_lookup[str(resolved_id)] = resolved_id

    def resolve(ref: object) -> int:
        try:
            return _resolve_node_ref(ref, alias_lookup)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"unknown node reference {ref!r}") from exc

    host = HostGraph()
    inline_edges: List[Mapping[str, object]] = []
    specs: Dict[int, InactiveSwitchSpec] = {}

    for entry in nodes_section:
        node_id = entry.pop("_resolved_id")
        labels = entry.get("labels", [])
        if not isinstance(labels, Sequence):
            raise ValueError(f"node {node_id} labels must be a list")
        name = entry.get("name") if isinstance(entry.get("name"), str) else None
        pos = entry.get("pos")
        if pos is not None:
            if (
                not isinstance(pos, Sequence)
                or len(pos) != 2
                or not all(isinstance(coord, (int, float)) for coord in pos)
            ):
                raise ValueError(f"node {node_id} pos must be [x, y]")
            pos_tuple = (float(pos[0]), float(pos[1]))
        else:
            pos_tuple = None

        combined_groups: Dict[str, List[int]] = {}
        for group_source in (entry.get("port_groups"), entry.get("sides")):
            if not isinstance(group_source, Mapping):
                continue
            for group_name, neighbours in group_source.items():
                if not isinstance(neighbours, Sequence):
                    raise ValueError(
                        f"node {node_id} group {group_name!r} must be a list"
                    )
                resolved = [resolve(nbr) for nbr in neighbours]
                if resolved:
                    combined_groups[group_name] = resolved

        host.add_node(
            node_id,
            name=name,
            labels=[str(label) for label in labels],
            pos=pos_tuple,
            port_groups=combined_groups or None,
        )

        connections = entry.get("connections", [])
        if isinstance(connections, Sequence):
            for conn in connections:
                if isinstance(conn, Mapping):
                    target = conn.get("target")
                    weight = float(conn.get("weight", 1.0))
                else:
                    target = conn
                    weight = 1.0
                inline_edges.append({"src": node_id, "dst": resolve(target), "weight": weight})

        switch_entry = entry.get("switching")
        if isinstance(switch_entry, Mapping):
            specs[node_id] = _inactive_spec_from_entry(switch_entry, alias_lookup)

    edges_section = graph_section.get("edges")
    combined_edges: List[Mapping[str, object]] = []
    if isinstance(edges_section, Sequence):
        combined_edges.extend(edges_section)
    combined_edges.extend(inline_edges)

    seen_edges: Set[Tuple[int, int]] = set()
    for edge_entry in combined_edges:
        if not isinstance(edge_entry, Mapping):
            raise ValueError("edge entries must be objects")
        src = resolve(edge_entry.get("src"))
        dst = resolve(edge_entry.get("dst"))
        weight = float(edge_entry.get("weight", 1.0))
        if (src, dst) in seen_edges:
            continue
        host.add_edge(src, dst, weight=weight)
        seen_edges.add((src, dst))

    switch_table_raw = data.get("switch_table", {})
    if isinstance(switch_table_raw, Mapping):
        fallback_specs = _parse_switch_table(switch_table_raw, alias_lookup)
    else:
        fallback_specs = {}
    for node_id, spec in fallback_specs.items():
        specs.setdefault(node_id, spec)

    return host, specs
