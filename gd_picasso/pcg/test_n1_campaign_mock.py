"""Mocked N1 dry-run — checkpointing, taxonomy, ExactCritic final oracle."""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from gd_picasso.pcg.run_n1_campaign import MockLLM, run_campaign
from gd_picasso.pcg.spa_protocol import N1_ABLATION_ARMS, N1_DRY_RUN_TASK_IDS


def test_mock_dry_run_checkpoint_and_csv(tmp_path: Path) -> None:
    llm = MockLLM()

    async def _go():
        return await run_campaign(
            task_ids=list(N1_DRY_RUN_TASK_IDS),
            arms=list(N1_ABLATION_ARMS),
            samples_per_task=1,
            llm=llm,
            out_dir=tmp_path,
            require_clean=False,
            require_model_pin=False,
            concurrency=2,
            dry_run=True,
        )

    results = asyncio.run(_go())
    # 2 tasks × 3 arms × 1 sample
    assert len(results) == 6
    csv_path = tmp_path / "n1_dryrun.csv"
    assert csv_path.is_file()
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 6
    assert {"pass", "pilot_pass", "exact_critic_pass", "error_class"} <= set(rows[0])
    # Headline pass aliases exact_critic_pass
    for r in rows:
        assert r["pass"] == r["exact_critic_pass"]
    # Fixture-backed mock should mostly ExactCritic-pass for A/B
    ab = [r for r in results if r.arm.startswith("A_") or r.arm.startswith("B_")]
    assert any(r.exact_critic_pass for r in ab)
    ckpt = tmp_path / "n1_dryrun.jsonl"
    assert ckpt.is_file()
    lines = [ln for ln in ckpt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 6

    # Resume: second run should not re-call LLM for completed keys
    calls_before = llm.calls
    results2 = asyncio.run(_go())
    assert len(results2) == 6
    assert llm.calls == calls_before


def test_mock_arm_b_unparseable_taxonomy() -> None:
    from gd_picasso.pcg.run_n1_campaign import map_error_class
    from gd_picasso.pcg.spa_protocol import N1_UNPARSEABLE_YAML

    assert map_error_class([], unparseable=True) == N1_UNPARSEABLE_YAML
    assert map_error_class(["out_of_bounds_param: x"]) == "out_of_bounds_param"
