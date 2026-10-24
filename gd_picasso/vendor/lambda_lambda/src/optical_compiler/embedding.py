"""Embedding compiled graphs onto a hardware host graph via ILP or MaxSAT."""

from __future__ import annotations

import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple, Mapping, Callable


def _ensure_gurobi_on_path() -> None:
    prefixes = set()
    for key in ("GUROBI_HOME", "CONDA_PREFIX", "VIRTUAL_ENV"):
        value = os.environ.get(key)
        if value:
            prefixes.add(Path(value))
    try:
        prefixes.add(Path(sys.executable).resolve().parent.parent)
    except Exception:  # pragma: no cover - best effort only
        pass

    home = Path.home()
    for name in ("anaconda3", "miniconda3", "gurobi"):
        candidate = home / name
        if candidate.exists():
            prefixes.add(candidate)

    for prefix in prefixes:
        lib_dir = prefix / "lib"
        if not lib_dir.exists():
            continue
        for candidate in sorted(lib_dir.glob("python*/site-packages")):
            path_str = str(candidate)
            if path_str not in sys.path:
                sys.path.append(path_str)


_ensure_gurobi_on_path()

try:
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:  # pragma: no cover - environment dependent
    gp = None  # type: ignore
    GRB = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from pysat.examples.rc2 import RC2
    from pysat.formula import WCNF
except ImportError:  # pragma: no cover - environment dependent
    RC2 = None  # type: ignore
    WCNF = None  # type: ignore

from .graph import GraphFragment, Label


@dataclass(frozen=True)
class LabelSpec:
    """Static constraints for a component label."""

    name: str
    indegree: int
    outdegree: int
    incoming_labels: Optional[Set[str]] = None
    outgoing_labels: Optional[Set[str]] = None


@dataclass
class ComponentNode:
    node_id: int
    label: Label
    indegree: int = 0
    outdegree: int = 0


@dataclass
class ComponentGraph:
    nodes: Dict[int, ComponentNode]
    edges: List[Tuple[int, int, int]]


def build_component_graph(fragment: GraphFragment) -> ComponentGraph:
    """Collapse routing wires while preserving per-slot connectivity."""

    component_kinds = {"input_port", "output_port", "phase", "splitter", "unitary"}
    nodes = {
        node_id: data
        for node_id, data in fragment.nodes.items()
        if data.label.kind in component_kinds
    }

    def bfs_from(start: int) -> List[Tuple[int, int]]:
        seen: Set[int] = set()
        initial_neighbors = fragment.connected_from(start)
        queue: deque[Tuple[int, Optional[int]]] = deque()
        for neighbor in initial_neighbors:
            slot = fragment.outputs.get(neighbor)
            queue.append((neighbor, slot))
        collected: List[Tuple[int, int]] = []
        while queue:
            current, slot = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            if current in nodes:
                if current != start:
                    collected.append((current, slot or 0))
                continue
            for nxt in fragment.connected_from(current):
                queue.append((nxt, slot))
        return collected

    edges: List[Tuple[int, int, int]] = []
    for node_id in nodes:
        for target, slot in bfs_from(node_id):
            edges.append((node_id, target, slot))

    indegree_count = defaultdict(int)
    outdegree_count = defaultdict(int)
    for src, dst, _ in edges:
        outdegree_count[src] += 1
        indegree_count[dst] += 1

    comp_nodes: Dict[int, ComponentNode] = {}
    for node_id, data in nodes.items():
        comp_nodes[node_id] = ComponentNode(
            node_id=node_id,
            label=data.label,
            indegree=indegree_count[node_id],
            outdegree=outdegree_count[node_id],
        )
    return ComponentGraph(nodes=comp_nodes, edges=edges)


@dataclass
class HostNode:
    node_id: int
    name: str
    candidates: Set[str]
    pos: Optional[Tuple[float, float]] = None
    assigned_label: Optional[str] = None
    assigned_param: Optional[object] = None
    port_groups: Dict[str, Set[int]] = field(default_factory=dict)


@dataclass
class HostGraph:
    nodes: Dict[int, HostNode] = field(default_factory=dict)
    edges: Dict[Tuple[int, int], float] = field(default_factory=dict)

    def add_node(
        self,
        node_id: int,
        *,
        name: Optional[str] = None,
        labels: Iterable[str],
        pos: Optional[Tuple[float, float]] = None,
        port_groups: Optional[Mapping[str, Iterable[int]]] = None,
    ) -> None:
        normalized_groups: Dict[str, Set[int]] = {}
        if port_groups:
            for group_name, members in port_groups.items():
                member_ids = {int(member) for member in members}
                if member_ids:
                    normalized_groups[str(group_name)] = member_ids
        self.nodes[node_id] = HostNode(
            node_id=node_id,
            name=name or f"h{node_id}",
            candidates=set(labels),
            pos=pos,
            assigned_label=None,
            assigned_param=None,
            port_groups=normalized_groups,
        )

    def add_edge(self, src: int, dst: int, *, weight: float = 1.0) -> None:
        if src not in self.nodes or dst not in self.nodes:
            raise ValueError("host edge endpoints must exist")
        self.edges[(src, dst)] = float(weight)

    def neighbors(self, node_id: int) -> List[int]:
        return [dst for (src, dst) in self.edges if src == node_id]

    def predecessors(self, node_id: int) -> List[int]:
        return [src for (src, dst) in self.edges if dst == node_id]


@dataclass
class EmbeddingResult:
    mapping: Dict[int, int]
    edge_paths: Dict[Tuple[int, int, int], List[Tuple[int, int]]]
    node_labels: Dict[int, Label]
    host_assignments: Dict[int, str]
    host_params: Dict[int, Optional[object]]


class EmbeddingError(Exception):
    """Raised when the embedding ILP has no feasible solution."""


class EmbeddingProblem:
    """Formulate and solve the embedding problem as a Gurobi ILP."""

    def __init__(
        self,
        dag: ComponentGraph,
        host: HostGraph,
        label_specs: Dict[str, LabelSpec],
    ) -> None:
        self.dag = dag
        self.host = host
        self.label_specs = label_specs
        self._validate_component_labels()
        self.same_side_groups = self._same_side_groups()

    def solve(
        self, method: str = "ilp", *, debug_dir: Optional[Path] = None
    ) -> EmbeddingResult:
        return self._solve(
            method=method, debug_dir=debug_dir, num_solutions=1
        )[0]

    def solve_multiple(
        self,
        num_solutions: int,
        *,
        method: str = "ilp",
        debug_dir: Optional[Path] = None,
    ) -> List[EmbeddingResult]:
        if num_solutions <= 0:
            raise ValueError("num_solutions must be positive")
        return self._solve(
            method=method, debug_dir=debug_dir, num_solutions=num_solutions
        )

    def _solve(
        self,
        *,
        method: str,
        debug_dir: Optional[Path],
        num_solutions: int,
    ) -> List[EmbeddingResult]:
        method_normalized = method.lower()
        if method_normalized == "ilp":
            return self._solve_ilp(debug_dir=debug_dir, num_solutions=num_solutions)
        if method_normalized == "maxsat":
            if num_solutions != 1:
                raise EmbeddingError(
                    "MaxSAT solver currently supports a single solution only"
                )
            if WCNF is None or RC2 is None:
                raise EmbeddingError(
                    "pysat is not installed. Install python-sat to use the MaxSAT solver."
                )
            return self._solve_maxsat(debug_dir=debug_dir)
        raise EmbeddingError(f"unknown embedding method '{method}'")

    def _solve_ilp(
        self, debug_dir: Optional[Path] = None, num_solutions: int = 1
    ) -> List[EmbeddingResult]:
        if gp is None or GRB is None:
            raise EmbeddingError(
                "gurobipy is not installed. Install Gurobi and set up a license."
            )

        dag_nodes = sorted(self.dag.nodes.keys())
        dag_edges = sorted(self.dag.edges)
        host_nodes = sorted(self.host.nodes.keys())
        oriented_edges = sorted(self.host.edges.keys())
        incoming_edge_indices: Dict[int, List[int]] = defaultdict(list)
        for edge_idx, (_, dst_node, _) in enumerate(dag_edges):
            incoming_edge_indices[dst_node].append(edge_idx)

        candidate_map = self._candidate_map()
        label_vars_per_host = self._label_candidates()

        model = gp.Model("embedding")
        model.Params.OutputFlag = 0
        model.Params.Threads = 1
        model.Params.MIPGap = 0.5
        if num_solutions > 1:
            model.Params.PoolSolutions = num_solutions
            model.Params.PoolSearchMode = 2
            model.Params.PoolGap = 0.5

        # Node assignment variables
        y_vars: Dict[Tuple[int, int], gp.Var] = {}
        for node_id in dag_nodes:
            for host_id in candidate_map[node_id]:
                y_vars[(node_id, host_id)] = model.addVar(
                    vtype=GRB.BINARY, name=f"y_{node_id}_{host_id}"
                )

        # Label selection variables (exclusive per host node)
        label_vars: Dict[Tuple[int, str], gp.Var] = {}
        for host_id, labels in label_vars_per_host.items():
            for label in labels:
                label_vars[(host_id, label)] = model.addVar(
                    vtype=GRB.BINARY, name=f"label_{host_id}_{label}"
                )

        # Flow variables for every DAG edge across host edges
        x_vars: Dict[Tuple[int, int, int], gp.Var] = {}
        for edge_idx, _ in enumerate(dag_edges):
            for src, dst in oriented_edges:
                x_vars[(edge_idx, src, dst)] = model.addVar(
                    vtype=GRB.BINARY, name=f"x_{edge_idx}_{src}_{dst}"
                )
        sink_guard_vars: Dict[Tuple[int, int, int], gp.Var] = {}
        if self.same_side_groups:
            for dst_node, edge_indices in incoming_edge_indices.items():
                if len(edge_indices) < 2:
                    continue
                for host_id in candidate_map[dst_node]:
                    groups = self.same_side_groups.get(host_id)
                    if not groups or len(groups) < 2:
                        continue
                    sink_var = y_vars[(dst_node, host_id)]
                    guard_vars: List[gp.Var] = []
                    for group_idx, _ in enumerate(groups):
                        guard = model.addVar(
                            vtype=GRB.BINARY,
                            name=f"sink_guard_{dst_node}_{host_id}_{group_idx}",
                        )
                        sink_guard_vars[(dst_node, host_id, group_idx)] = guard
                        guard_vars.append(guard)
                        model.addConstr(
                            guard <= sink_var,
                            name=(
                                f"sink_guard_link_{dst_node}_{host_id}_{group_idx}"
                            ),
                        )
                    model.addConstr(
                        gp.quicksum(guard_vars) == sink_var,
                        name=f"sink_guard_select_{dst_node}_{host_id}",
                    )
        model.update()

        # Each component node maps to exactly one host node
        for node_id in dag_nodes:
            model.addConstr(
                gp.quicksum(y_vars[(node_id, h)] for h in candidate_map[node_id]) == 1,
                name=f"assign_{node_id}",
            )

        # Host exclusivity: at most one component per host node
        for host_id in host_nodes:
            host_usage = gp.quicksum(
                y_var for (node, h), y_var in y_vars.items() if h == host_id
            )
            model.addConstr(host_usage <= 1, name=f"host_capacity_{host_id}")

        # Link node assignments to label selections
        for (node_id, host_id), y_var in y_vars.items():
            label_name = self.dag.nodes[node_id].label.kind
            if (host_id, label_name) not in label_vars:
                raise EmbeddingError(
                    f"Host node {host_id} lacks selectable label {label_name}"
                )
            model.addConstr(
                y_var <= label_vars[(host_id, label_name)],
                name=f"label_link_{node_id}_{host_id}",
            )

        # Exclusive label selection and activation implication
        for host_id, labels in label_vars_per_host.items():
            vars_for_host = [label_vars[(host_id, label)] for label in labels]
            if not vars_for_host:
                continue
            model.addConstr(
                gp.quicksum(vars_for_host) <= 1, name=f"label_unique_{host_id}"
            )
            usage = gp.quicksum(
                y_var for (node, h), y_var in y_vars.items() if h == host_id
            )
            for label in labels:
                model.addConstr(
                    label_vars[(host_id, label)] <= usage,
                    name=f"label_activation_{host_id}_{label}",
                )
            model.addConstr(
                usage <= gp.quicksum(vars_for_host),
                name=f"label_cover_{host_id}",
            )

        # Flow conservation constraints
        incoming_edges: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        outgoing_edges: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        for src, dst in oriented_edges:
            outgoing_edges[src].append((src, dst))
            incoming_edges[dst].append((src, dst))

        edge_index_map = {edge: idx for idx, edge in enumerate(dag_edges)}

        # use(h) = Σ_{v : h ∈ C(v)} y_{v,h}; needed for path-correctness bounds.
        host_use_expr: Dict[int, gp.LinExpr] = {
            host_id: gp.quicksum(
                y_var for (node, h), y_var in y_vars.items() if h == host_id
            )
            for host_id in host_nodes
        }

        for edge_idx, (src_node, dst_node, _slot) in enumerate(dag_edges):
            for host_id in host_nodes:
                incoming_sum = gp.quicksum(
                    x_vars[(edge_idx, u, v)]
                    for (u, v) in incoming_edges.get(host_id, [])
                )
                outgoing_sum = gp.quicksum(
                    x_vars[(edge_idx, u, v)]
                    for (u, v) in outgoing_edges.get(host_id, [])
                )
                source_var = y_vars.get((src_node, host_id))
                sink_var = y_vars.get((dst_node, host_id))
                rhs = gp.LinExpr()
                if source_var is not None:
                    rhs += source_var
                if sink_var is not None:
                    rhs -= sink_var
                model.addConstr(
                    outgoing_sum - incoming_sum == rhs,
                    name=f"flow_{edge_idx}_{host_id}",
                )
#    # Keep each DAG edge to a simple path by bounding degree per host.
                model.addConstr(
                    incoming_sum <= 1, name=f"flow_in_degree_{edge_idx}_{host_id}"
                )
                model.addConstr(
                    outgoing_sum <= 1, name=f"flow_out_degree_{edge_idx}_{host_id}"
                )

                # Path correctness: a route may pass through h only if h is
                # unused by the embedding, or h is the source/sink of this edge.
                path_bound = 1 - host_use_expr[host_id]
                if source_var is not None:
                    path_bound = path_bound + source_var
                if sink_var is not None:
                    path_bound = path_bound + sink_var
                model.addConstr(
                    incoming_sum <= path_bound,
                    name=f"no_spurious_in_{edge_idx}_{host_id}",
                )
                model.addConstr(
                    outgoing_sum <= path_bound,
                    name=f"no_spurious_out_{edge_idx}_{host_id}",
                )

        # Host edge capacity: no oriented edge reused globally
        for src, dst in oriented_edges:
            model.addConstr(
                gp.quicksum(
                    x_vars[(edge_idx, src, dst)] for edge_idx in range(len(dag_edges))
                )
                <= 1,
                name=f"edge_capacity_{src}_{dst}",
            )

        # Undirected capacity: forbid reuse of a physical link in both directions
        undirected_edges: Dict[frozenset, List[Tuple[int, int]]] = defaultdict(list)
        for src, dst in oriented_edges:
            undirected_edges[frozenset({src, dst})].append((src, dst))
        for key, group in undirected_edges.items():
            total = gp.quicksum(
                x_vars[(edge_idx, u, v)]
                for edge_idx in range(len(dag_edges))
                for (u, v) in group
            )
            endpoints = "_".join(str(e) for e in sorted(key))
            model.addConstr(
                total <= 1, name=f"undirected_capacity_{endpoints}"
            )

        # Prevent opposite-direction reuse on the same undirected edge for each DAG edge
        for edge_idx in range(len(dag_edges)):
            for group in undirected_edges.values():
                if len(group) == 2:
                    model.addConstr(
                        gp.quicksum(
                            x_vars[(edge_idx, u, v)] for (u, v) in group
                        )
                        <= 1,
                        name=f"no_uturn_{edge_idx}_{group[0][0]}_{group[0][1]}",
                    )

        # Forbid V-turns that enter and exit the same side of a host
        if self.same_side_groups:
            for edge_idx in range(len(dag_edges)):
                for host_id, groups in self.same_side_groups.items():
                    for group in groups:
                        for src_neighbor in group:
                            for dst_neighbor in group:
                                if src_neighbor == dst_neighbor:
                                    continue
                                in_var = x_vars.get((edge_idx, src_neighbor, host_id))
                                out_var = x_vars.get((edge_idx, host_id, dst_neighbor))
                                if in_var is None or out_var is None:
                                    continue
                                model.addConstr(
                                    in_var + out_var <= 1,
                                    name=(
                                        f"same_side_vturn_{edge_idx}_{host_id}_"
                                        f"{src_neighbor}_{dst_neighbor}"
                                    ),
                                )

        # Enforce same-side ingestion for multi-input sinks
        if sink_guard_vars:
            for dst_node, edge_indices in incoming_edge_indices.items():
                if len(edge_indices) < 2:
                    continue
                for host_id in candidate_map[dst_node]:
                    groups = self.same_side_groups.get(host_id)
                    if not groups or len(groups) < 2:
                        continue
                    incoming = incoming_edges.get(host_id, [])
                    for group_idx, group in enumerate(groups):
                        guard = sink_guard_vars.get(
                            (dst_node, host_id, group_idx)
                        )
                        if guard is None:
                            continue
                        disallowed = [
                            src for (src, _) in incoming if src not in group
                        ]
                        if not disallowed:
                            continue
                        for edge_idx in edge_indices:
                            for src in disallowed:
                                x_var = x_vars.get((edge_idx, src, host_id))
                                if x_var is None:
                                    continue
                                model.addConstr(
                                    x_var + guard <= 1,
                                    name=(
                                        f"sink_side_align_{edge_idx}_{dst_node}_"
                                        f"{host_id}_{group_idx}_{src}"
                                    ),
                                )

        # Objective: minimise total routed path length (weighted by host edge length)
        objective = gp.quicksum(
            self.host.edges[(src, dst)] * x_vars[(edge_idx, src, dst)]
            for edge_idx in range(len(dag_edges))
            for (src, dst) in oriented_edges
        )
        model.setObjective(objective, GRB.MINIMIZE)
        model.Params.Method = 2

        try:
            model.optimize()
        except gp.GurobiError as err:  # pragma: no cover - external dependency
            raise EmbeddingError(f"Gurobi failed: {err}") from err

        if model.status != GRB.OPTIMAL:
            status_lookup = {
                GRB.Status.OPTIMAL: "OPTIMAL",
                GRB.Status.INFEASIBLE: "INFEASIBLE",
                GRB.Status.INF_OR_UNBD: "INF_OR_UNBD",
                GRB.Status.UNBOUNDED: "UNBOUNDED",
            }
            debug_hint = ""
            if debug_dir is not None:
                diag_dir = Path(debug_dir)
                diag_dir.mkdir(parents=True, exist_ok=True)
                model_path = diag_dir / "embedding_model.lp"
                model.write(str(model_path))
                if model.status in (GRB.Status.INFEASIBLE, GRB.Status.INF_OR_UNBD):
                    try:
                        model.computeIIS()
                        iis_path = diag_dir / "embedding_model.ilp"
                        model.write(str(iis_path))
                    except gp.GurobiError:
                        pass
                debug_hint = f" Diagnostics written to {diag_dir.resolve()}."
            status_name = status_lookup.get(model.status, "UNKNOWN")
            raise EmbeddingError(
                f"embedding ILP status {model.status} ({status_name}).{debug_hint}"
            )

        available = min(num_solutions, model.SolCount)
        if available == 0:
            raise EmbeddingError("no feasible embedding found")

        def solution_value(var: gp.Var, sol_idx: int) -> float:
            if sol_idx == 0:
                return float(var.X)
            model.Params.SolutionNumber = sol_idx
            return float(var.Xn)

        results: List[EmbeddingResult] = []
        for sol_idx in range(available):
            value = lambda var, idx=sol_idx: solution_value(var, idx)
            mapping: Dict[int, int] = {}
            for (node_id, host_id), var in y_vars.items():
                if value(var) > 0.5:
                    mapping[node_id] = host_id
            if len(mapping) != len(dag_nodes):
                raise EmbeddingError("solution missing component placements")

            chosen_labels: Dict[int, str] = {}
            for (host_id, label_name), var in label_vars.items():
                if value(var) > 0.5:
                    chosen_labels[host_id] = label_name

            x_active = {
                key: bool(value(var) > 0.5)
                for key, var in x_vars.items()
            }
            edge_paths = self._recover_edge_paths(
                mapping=mapping,
                edge_index_map=edge_index_map,
                x_active=x_active,
                oriented_edges=oriented_edges,
            )

            host_params: Dict[int, Optional[object]] = {}
            for node_id, host_id in mapping.items():
                if self.dag.nodes[node_id].label.value is not None:
                    host_params[host_id] = self.dag.nodes[node_id].label.value

            results.append(
                EmbeddingResult(
                    mapping=mapping,
                    edge_paths=edge_paths,
                    node_labels={
                        node_id: self.dag.nodes[node_id].label
                        for node_id in self.dag.nodes
                    },
                    host_assignments=chosen_labels,
                    host_params=host_params,
                )
            )

        first = results[0]
        for host_id, host_node in self.host.nodes.items():
            host_node.assigned_label = first.host_assignments.get(host_id)
            host_node.assigned_param = first.host_params.get(host_id)

        return results

    def _recover_edge_paths(
        self,
        mapping: Dict[int, int],
        edge_index_map: Dict[Tuple[int, int, int], int],
        x_active: Dict[Tuple[int, int, int], bool],
        oriented_edges: List[Tuple[int, int]],
    ) -> Dict[Tuple[int, int, int], List[Tuple[int, int]]]:
        edge_paths: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {}
        for edge, edge_idx in edge_index_map.items():
            used_edges = [
                (u, v)
                for (u, v) in oriented_edges
                if x_active.get((edge_idx, u, v), False)
            ]
            if not used_edges:
                edge_paths[edge] = []
                continue

            src_host = mapping[edge[0]]
            dst_host = mapping[edge[1]]
            adjacency = defaultdict(list)
            for u, v in used_edges:
                adjacency[u].append(v)

            path: List[Tuple[int, int]] = []
            current = src_host
            visited = set()
            while current != dst_host:
                if current not in adjacency or not adjacency[current]:
                    raise EmbeddingError(
                        f"incomplete path for edge {edge} at host {current}"
                    )
                next_node = adjacency[current].pop()
                path.append((current, next_node))
                if next_node in visited:
                    raise EmbeddingError(
                        f"cycle detected while recovering path {edge}"
                    )
                visited.add(next_node)
                current = next_node
            edge_paths[edge] = path
        return edge_paths

    def _solve_maxsat(
        self, debug_dir: Optional[Path] = None, num_solutions: int = 1
    ) -> List[EmbeddingResult]:
        assert WCNF is not None and RC2 is not None  # for mypy
        _ = debug_dir  # reserved for parity with the ILP solver interface

        dag_nodes = sorted(self.dag.nodes.keys())
        dag_edges = sorted(self.dag.edges)
        host_nodes = sorted(self.host.nodes.keys())
        oriented_edges = sorted(self.host.edges.keys())

        candidate_map = self._candidate_map()
        label_vars_per_host = self._label_candidates()
        edge_index_map = {edge: idx for idx, edge in enumerate(dag_edges)}
        incoming_edge_indices: Dict[int, List[int]] = defaultdict(list)
        for edge_idx, (_, dst, _) in enumerate(dag_edges):
            incoming_edge_indices[dst].append(edge_idx)

        # if self.same_side_groups:
        #     print("[debug] Hosts with side groups relevant to two-input components:")
        #     for node_id in dag_nodes:
        #         if self.dag.nodes[node_id].indegree < 2:
        #             continue
        #         print(f"  component {node_id} candidates:")
        #         for host_id in candidate_map[node_id]:
        #             if host_id not in self.same_side_groups:
        #                 continue
        #             groups = self.same_side_groups[host_id]
        #             print(
        #                 f"    host {host_id}:"
        #                 f" left={groups[0] if groups else []}"
        #                 f" right={groups[1] if len(groups) > 1 else []}"
        #             )

        wcnf = WCNF()
        next_var = 1

        def new_var() -> int:
            nonlocal next_var
            var = next_var
            next_var += 1
            return var

        def add_clause(lits: List[int]) -> None:
            if not lits:
                raise EmbeddingError("attempted to add empty clause to MaxSAT model")
            wcnf.append(lits)

        def add_soft_clause(lits: List[int], weight: float) -> None:
            if not lits:
                raise EmbeddingError("attempted to add empty soft clause")
            scaled = max(1, int(round(weight * 1000)))
            wcnf.append(lits, weight=scaled)

        def add_at_most_one(vars_list: List[int]) -> None:
            for i in range(len(vars_list)):
                for j in range(i + 1, len(vars_list)):
                    add_clause([-vars_list[i], -vars_list[j]])

        y_vars: Dict[Tuple[int, int], int] = {}
        for node_id in dag_nodes:
            for host_id in candidate_map[node_id]:
                y_vars[(node_id, host_id)] = new_var()

        z_vars: Dict[Tuple[int, str], int] = {}
        for host_id, labels in label_vars_per_host.items():
            for label in labels:
                z_vars[(host_id, label)] = new_var()

        x_vars: Dict[Tuple[int, int, int], int] = {}
        for edge_idx in range(len(dag_edges)):
            for src, dst in oriented_edges:
                x_vars[(edge_idx, src, dst)] = new_var()

        mode_vars: Dict[int, Tuple[int, int]] = {}
        sink_side_guards: Dict[Tuple[int, int, int], int] = {}

        # H1: each component assigned exactly once
        for node_id in dag_nodes:
            vars_for_node = [y_vars[(node_id, h)] for h in candidate_map[node_id]]
            add_clause(vars_for_node)  # at least one
            add_at_most_one(vars_for_node)

        # H2: host capacity
        for host_id in host_nodes:
            vars_for_host = [
                var for (node, h), var in y_vars.items() if h == host_id
            ]
            add_at_most_one(vars_for_host)

        # H3: label consistency
        for (node_id, host_id), y_var in y_vars.items():
            label_name = self.dag.nodes[node_id].label.kind
            label_var = z_vars.get((host_id, label_name))
            if label_var is None:
                raise EmbeddingError(
                    f"Host node {host_id} lacks selectable label {label_name}"
                )
            add_clause([-y_var, label_var])

        for host_id, labels in label_vars_per_host.items():
            z_list = [z_vars[(host_id, label)] for label in labels]
            if not z_list:
                continue
            add_at_most_one(z_list)
            host_usage = [
                y_vars[(node, host_id)]
                for node in dag_nodes
                if (node, host_id) in y_vars
            ]
            add_clause([-z_list[0]] + host_usage)  # ensure activation implies usage
            for label_var in z_list[1:]:
                add_clause([-label_var] + host_usage)

        # Flow helper variables
        out_used: Dict[Tuple[int, int], int] = {}
        in_used: Dict[Tuple[int, int], int] = {}

        outgoing_edges = defaultdict(list)
        incoming_edges = defaultdict(list)
        for src, dst in oriented_edges:
            outgoing_edges[src].append((src, dst))
            incoming_edges[dst].append((src, dst))

        for edge_idx in range(len(dag_edges)):
            for host_id in host_nodes:
                out_var = new_var()
                out_used[(edge_idx, host_id)] = out_var
                out_list = [
                    x_vars[(edge_idx, u, v)]
                    for (u, v) in outgoing_edges.get(host_id, [])
                ]
                if out_list:
                    add_clause([-out_var] + out_list)
                    for x_var in out_list:
                        add_clause([-x_var, out_var])
                    add_at_most_one(out_list)
                else:
                    add_clause([-out_var])

                in_var = new_var()
                in_used[(edge_idx, host_id)] = in_var
                in_list = [
                    x_vars[(edge_idx, u, v)]
                    for (u, v) in incoming_edges.get(host_id, [])
                ]
                if in_list:
                    add_clause([-in_var] + in_list)
                    for x_var in in_list:
                        add_clause([-x_var, in_var])
                    add_at_most_one(in_list)
                else:
                    add_clause([-in_var])

        # H4-style constraints using indicators
        for edge_idx, (src_node, dst_node, _slot) in enumerate(dag_edges):
            for host_id in host_nodes:
                out_var = out_used[(edge_idx, host_id)]
                in_var = in_used[(edge_idx, host_id)]
                source_var = y_vars.get((src_node, host_id))
                sink_var = y_vars.get((dst_node, host_id))

                if source_var is not None:
                    add_clause([-source_var, out_var])
                    add_clause([-source_var, -in_var])
                if sink_var is not None:
                    add_clause([-sink_var, in_var])
                    add_clause([-sink_var, -out_var])

                guard_clause = []
                if source_var is not None:
                    guard_clause.append(source_var)
                if sink_var is not None:
                    guard_clause.append(sink_var)
                add_clause(guard_clause + [-out_var, in_var])
                add_clause(guard_clause + [-in_var, out_var])

        # Enforce slot-to-side alignment for component outputs
        if self.same_side_groups:
            for edge_idx, (_, _, slot) in enumerate(dag_edges):
                if slot is None or slot <= 0:
                    continue
                for host_id in host_nodes:
                    groups = self.same_side_groups.get(host_id)
                    if not groups or slot > len(groups):
                        continue
                    allowed = set(groups[slot - 1])

        # H5: global edge capacity
        for src, dst in oriented_edges:
            vars_for_edge = [
                x_vars[(edge_idx, src, dst)] for edge_idx in range(len(dag_edges))
            ]
            add_at_most_one(vars_for_edge)

        # H6/H7 data: undirected edge groups
        undirected_edges: Dict[frozenset, List[Tuple[int, int]]] = defaultdict(list)
        for src, dst in oriented_edges:
            undirected_edges[frozenset({src, dst})].append((src, dst))

        # H6: forbid opposite directions across different component edges
        for group in undirected_edges.values():
            combined = []
            for edge_idx in range(len(dag_edges)):
                for src, dst in group:
                    combined.append(x_vars[(edge_idx, src, dst)])
            add_at_most_one(combined)

        # H7: prevent opposite direction reuse per DAG edge
        for edge_idx in range(len(dag_edges)):
            for group in undirected_edges.values():
                if len(group) == 2:
                    a, b = group
                    add_clause(
                        [-x_vars[(edge_idx, a[0], a[1])], -x_vars[(edge_idx, b[0], b[1])]]
                    )

        # Guard variables selecting which side a multi-input sink uses on a host
        if self.same_side_groups:
            for dst_node, edge_indices in incoming_edge_indices.items():
                if len(edge_indices) < 2:
                    continue
                for host_id in candidate_map[dst_node]:
                    groups = self.same_side_groups.get(host_id)
                    if not groups or len(groups) < 2:
                        continue
                    sink_var = y_vars[(dst_node, host_id)]
                    guard_vars: List[int] = []
                    for group_idx, _ in enumerate(groups):
                        guard = new_var()
                        sink_side_guards[(dst_node, host_id, group_idx)] = guard
                        guard_vars.append(guard)
                        add_clause([-guard, sink_var])
                    add_at_most_one(guard_vars)
                    add_clause([-sink_var] + guard_vars)
                    
        # H8a: forbid V-turns that enter/exit the same side of an unlabeled host
        if self.same_side_groups:
            for edge_idx in range(len(dag_edges)):
                for host_id, groups in self.same_side_groups.items():
                    for group in groups:
                        for src_neighbor in group:
                            for dst_neighbor in group:
                                if src_neighbor == dst_neighbor:
                                    continue
                                in_var = x_vars.get((edge_idx, src_neighbor, host_id))
                                out_var = x_vars.get((edge_idx, host_id, dst_neighbor))
                                if in_var is None or out_var is None:
                                    continue
                                add_clause([-in_var, -out_var])

        # H8b: force multi-input sinks to draw both edges from the same side
        if sink_side_guards:
            for dst_node, edge_indices in incoming_edge_indices.items():
                if len(edge_indices) < 2:
                    continue
                for host_id in candidate_map[dst_node]:
                    groups = self.same_side_groups.get(host_id)
                    if not groups or len(groups) < 2:
                        continue
                    host_incoming = incoming_edges.get(host_id, [])
                    for group_idx, group in enumerate(groups):
                        guard = sink_side_guards.get((dst_node, host_id, group_idx))
                        if guard is None:
                            continue
                        disallowed = [
                            src for (src, _) in host_incoming if src not in group
                        ]
                        if not disallowed:
                            continue
                        for edge_idx in edge_indices:
                            for neighbor in disallowed:
                                in_var = x_vars.get((edge_idx, neighbor, host_id))
                                if in_var is None:
                                    continue
                                add_clause([-guard, -in_var])

        # if mode_vars:
        #     for edge_idx in range(len(dag_edges)):
        #         for host_id, groups in self.same_side_groups.items():
        #             if host_id not in mode_vars:
        #                 continue
        #             same_var, cross_var = mode_vars[host_id]
        #             for group in groups:
        #                 for src_neighbor in group:
        #                     for dst_neighbor in group:
        #                         if src_neighbor == dst_neighbor:
        #                             continue
        #                         in_var = x_vars.get((edge_idx, src_neighbor, host_id))
        #                         out_var = x_vars.get((edge_idx, host_id, dst_neighbor))
        #                         if in_var is None or out_var is None:
        #                             continue
        #                         add_clause([-in_var, -out_var, same_var])
        #             for left_idx, left_group in enumerate(groups):
        #                 for right_idx, right_group in enumerate(groups):
        #                     if left_idx == right_idx:
        #                         continue
        #                     for src_neighbor in left_group:
        #                         for dst_neighbor in right_group:
        #                             in_var = x_vars.get(
        #                                 (edge_idx, src_neighbor, host_id)
        #                             )
        #                             out_var = x_vars.get(
        #                                 (edge_idx, host_id, dst_neighbor)
        #                             )
        #                             if in_var is None or out_var is None:
        #                                 continue
        #                             add_clause([-in_var, -out_var, cross_var])

        # Soft clauses for routing cost (edge-length weighted)
        for edge_idx in range(len(dag_edges)):
            for (src, dst) in oriented_edges:
                weight = self.host.edges[(src, dst)]
                add_soft_clause([-x_vars[(edge_idx, src, dst)]], weight)

        debug_dir = Path("artifacts")
        debug_dir.mkdir(parents=True, exist_ok=True)
        wcnf_path = debug_dir / "embedding_debug.wcnf"
        try:
            wcnf.to_file(str(wcnf_path))
            print(f"[debug] WCNF model written to {wcnf_path}")
        except Exception as exc:  # pragma: no cover - diagnostic only
            print(f"[debug] Failed to persist WCNF model: {exc}")

        try:
            with RC2(wcnf, verbose=1) as rc2:
                model = rc2.compute()
        except Exception as err:  # pragma: no cover - external dependency
            raise EmbeddingError(f"MaxSAT solver failed: {err}") from err

        if model is None:
            raise EmbeddingError("MaxSAT solver returned no model")

        assignment = {lit for lit in model if lit > 0}

        mapping: Dict[int, int] = {}
        for (node_id, host_id), var in y_vars.items():
            if var in assignment:
                mapping[node_id] = host_id

        if len(mapping) != len(dag_nodes):
            raise EmbeddingError("MaxSAT solution missing component placements")

        chosen_labels: Dict[int, str] = {}
        for (host_id, label_name), var in z_vars.items():
            if var in assignment:
                chosen_labels[host_id] = label_name

        x_active = {
            key: var in assignment for key, var in x_vars.items()
        }
        edge_paths = self._recover_edge_paths(
            mapping=mapping,
            edge_index_map=edge_index_map,
            x_active=x_active,
            oriented_edges=oriented_edges,
        )

        host_params: Dict[int, Optional[object]] = {}
        for node_id, host_id in mapping.items():
            if self.dag.nodes[node_id].label.value is not None:
                host_params[host_id] = self.dag.nodes[node_id].label.value

        for host_id, host_node in self.host.nodes.items():
            host_node.assigned_label = chosen_labels.get(host_id)
            host_node.assigned_param = host_params.get(host_id)

        return [
            EmbeddingResult(
                mapping=mapping,
                edge_paths=edge_paths,
                node_labels={
                    node_id: self.dag.nodes[node_id].label for node_id in self.dag.nodes
                },
                host_assignments=chosen_labels,
                host_params=host_params,
            )
        ]

    def _candidate_map(self) -> Dict[int, List[int]]:
        mapping: Dict[int, List[int]] = {}
        for node_id, comp_node in self.dag.nodes.items():
            label_name = comp_node.label.kind
            spec = self.label_specs.get(label_name)
            if spec is None:
                raise EmbeddingError(f"missing label specification for {label_name}")

            candidates: List[int] = []
            for host_id, host_node in self.host.nodes.items():
                if label_name not in host_node.candidates:
                    continue
                if label_name in {"input_port", "output_port"}:
                    port_value = comp_node.label.value
                    if not isinstance(port_value, int):
                        continue
                    name = (host_node.name or "").lower()
                    if not (
                        host_id == port_value
                        or name == f"port{port_value}"
                        or name == str(port_value)
                    ):
                        continue
                if spec.indegree != comp_node.indegree:
                    continue
                if spec.outdegree != comp_node.outdegree:
                    continue
                candidates.append(host_id)
            if not candidates:
                raise EmbeddingError(f"no host candidates for component {label_name}")
            mapping[node_id] = candidates
        return mapping

    def _label_candidates(self) -> Dict[int, Set[str]]:
        label_options: Dict[int, Set[str]] = {}
        for host_id, host_node in self.host.nodes.items():
            allowed = {
                label
                for label in host_node.candidates
                if label in self.label_specs
            }
            if allowed:
                label_options[host_id] = allowed
        return label_options

    def _validate_component_labels(self) -> None:
        for src, dst, _ in self.dag.edges:
            src_label = self.dag.nodes[src].label.kind
            dst_label = self.dag.nodes[dst].label.kind
            src_spec = self.label_specs.get(src_label)
            dst_spec = self.label_specs.get(dst_label)
            if src_spec and src_spec.outgoing_labels and dst_label not in src_spec.outgoing_labels:
                raise EmbeddingError(
                    f"component edge ({src_label}->{dst_label}) violates outgoing label constraint"
                )
            if dst_spec and dst_spec.incoming_labels and src_label not in dst_spec.incoming_labels:
                raise EmbeddingError(
                    f"component edge ({src_label}->{dst_label}) violates incoming label constraint"
                )

    def _same_side_groups(self) -> Dict[int, List[List[int]]]:
        groups: Dict[int, List[List[int]]] = {}
        for host_id, host_node in self.host.nodes.items():
            if not host_node.port_groups:
                continue
            node_groups: List[List[int]] = []
            for members in host_node.port_groups.values():
                normalized = [
                    int(nbr)
                    for nbr in set(members)
                    if nbr in self.host.nodes
                    and (
                        (nbr, host_id) in self.host.edges
                        or (host_id, nbr) in self.host.edges
                    )
                ]
                if normalized:
                    node_groups.append(sorted(normalized))
            if node_groups:
                groups[host_id] = node_groups
        return groups


def derive_puc_states(
    host: HostGraph,
    result: EmbeddingResult,
) -> Tuple[Dict[int, str], Dict[int, Optional[object]]]:
    """Infer PUC actuation states (bar/cross/splitter/phase/unitary) from an embedding result.

    The heuristic is:
    - Nodes hosting logical components inherit their label and parameter.
    - Any PUC traversed by a routed path but not already assigned is marked as ``cross``.
    - Every other PUC defaults to ``inactive``.
    """

    assignments: Dict[int, str] = {}
    params: Dict[int, Optional[object]] = {}

    # Seed with the solver output.
    assignments.update(result.host_assignments)
    params.update(result.host_params)

    def set_state(node_id: int, label: str, value: Optional[object]) -> None:
        assignments[node_id] = label
        params[node_id] = value

    # Ensure component nodes have explicit states.
    for comp_id, host_id in result.mapping.items():
        label = result.node_labels[comp_id]
        kind = label.kind
        value = label.value
        if kind not in {"input_port", "output_port"}:
            set_state(host_id, kind, value)

    def is_puc(node_id: int) -> bool:
        candidates = host.nodes[node_id].candidates
        return bool({"phase", "splitter", "unitary"} & candidates)

    # Mark routing-only PUCs.
    for path in result.edge_paths.values():
        for src, dst in path:
            for node_id in (src, dst):
                if node_id not in host.nodes:
                    continue
                if not is_puc(node_id):
                    continue
                if node_id not in assignments:
                    set_state(node_id, "cross", 1.0)

    # Default any remaining PUCs to inactive.
    for node_id, node in host.nodes.items():
        if not is_puc(node_id):
            continue
        if node_id not in assignments:
            set_state(node_id, "inactive", None)

    return assignments, params
