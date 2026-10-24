"""PIC-Bench-48: ExactCritic + TaskContract on every golden GF fixture."""

from __future__ import annotations

from gd_picasso.agents.exact_critic import ExactCritic
from gd_picasso.bench import evaluate_submission, load_benchmark
from gd_picasso.bench.contracts import TASK_CONTRACTS, evaluate_task_contract
from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.build_formal_benchmarks import (
    MESH_TASKS,
    MESH_TOPOLOGY_KIND,
    UNREALIZABLE_TASKS,
    UPGRADED_STUB_TASKS,
    gf_fixture_path,
    picbench_catalog,
    reject_unrealizable,
    saved_gf_tasks,
)
from gd_picasso.pcg.store import PCGStore
from gd_picasso.pcg.types import PCGNode, RefLevel


def test_picbench_48_validity() -> None:
    catalog = picbench_catalog()
    assert len(catalog) == 48
    critic = ExactCritic()
    checked = 0
    for task in catalog:
        if task.kind == "unrealizable":
            assert task.task_id in UNREALIZABLE_TASKS
            assert not gf_fixture_path(task.task_id).is_file()
            continue
        path = gf_fixture_path(task.task_id)
        assert path.is_file(), path
        store = from_gf_yaml(path.read_text())
        critique = critic.review(store)
        assert critique.ok, (task.task_id, critique.problems[:8])
        contract = TASK_CONTRACTS[task.task_id]
        assert evaluate_task_contract(store, contract), (
            task.task_id,
            len(store.nodes),
            len(store.exported_ports),
        )
        result = evaluate_submission(task.task_id, store)
        assert result.ok, (task.task_id, result.as_dict())
        checked += 1
    assert checked == len(saved_gf_tasks())
    assert checked == 46


def test_load_benchmark_exposes_46_contracts() -> None:
    bench = load_benchmark()
    assert len(bench) == 48
    gf = [t for t in bench if t.kind == "gf"]
    assert len(gf) == 46
    assert all(t.contract is not None for t in gf)


def test_trivial_straight_fails_clements_contract() -> None:
    """Closes the 1-node ExactCritic loophole on Task 20."""
    store = PCGStore()
    store.add_node(
        PCGNode(id="s", component="straight", params={"length": 10.0}, level=RefLevel.L1_CIRCUIT),
        skip_component_check=True,
    )
    store.set_exported_ports({"in1": "s,o1", "out1": "s,o2"})
    assert ExactCritic().review(store).ok
    result = evaluate_submission(20, store)
    assert not result.ok
    assert result.exact_critic_ok
    assert not result.contract_ok


def test_mesh_fixtures_are_dealiased() -> None:
    for task_id, (_n, _name) in MESH_TASKS.items():
        text = gf_fixture_path(task_id).read_text()
        assert "aliased" not in text.lower() or "de-aliased" in text.lower()
        assert MESH_TOPOLOGY_KIND[task_id] in text or "authentic" in text
        store = from_gf_yaml(text)
        assert ExactCritic().review(store).ok
        # Crossbar / Spanke / Benes must not all collapse to Clements 24/112.
        if task_id in (11, 13, 15, 17):
            if task_id == 11:
                assert len(store.nodes) >= 64
            if task_id in (13, 15, 17):
                assert any(n.component == "crossing" for n in store.nodes.values()) or task_id == 11


def test_upgraded_stubs_are_gf_fixtures() -> None:
    for task_id in sorted(UPGRADED_STUB_TASKS):
        path = gf_fixture_path(task_id)
        assert path.is_file(), task_id
        store = from_gf_yaml(path.read_text())
        assert evaluate_submission(task_id, store).ok


def test_hadamard_and_dft_are_24_node_meshes() -> None:
    for task_id in (37, 38):
        store = from_gf_yaml(gf_fixture_path(task_id).read_text())
        assert len(store.nodes) == 24, (task_id, len(store.nodes))


def test_multipdk_fixtures_contain_tapers() -> None:
    for task_id in range(39, 47):
        store = from_gf_yaml(gf_fixture_path(task_id).read_text())
        assert any(n.component == "taper" for n in store.nodes.values()), task_id
        critique = ExactCritic().review(store)
        assert critique.ok, (task_id, critique.problems[:6])


def test_unrealizable_tasks_rejected_by_psd_gate() -> None:
    for task_id in sorted(UNREALIZABLE_TASKS):
        message = reject_unrealizable(task_id)
        assert "unrealizable" in message.lower()
        assert not gf_fixture_path(task_id).is_file()
