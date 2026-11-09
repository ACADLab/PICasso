# N1 confirmatory pre-registration (`n1-confirm-v1`)

Frozen **before** the confirmatory PIC-Bench-48 campaign. Tag: `n1-confirm-v1` on branch `dac27-confirm`.

## Metric

Headline for **all arms**:

```text
pass_uniform = exact_critic_pass AND contract_pass
```

Implemented in `gd_picasso/pcg/run_n1_campaign.py` `_score_store` (no per-arm headline split).

Tasks **47 and 48** are scored **separately** and are **not** in the 1–46 tables:

- Pass iff the model emits an explicit refusal / infeasibility verdict **and** no circuit store.
- A generated netlist is a fail even if it mentions refusal.

## Arms

| Arm | System prompt | Repair feedback | Requirements block |
|---|---|---|---|
| A `A_yaml_pilot` | `BasePilotGenerator` (unchanged) | YAML pilot validator | identical `Requirements:` block |
| B `B_yaml_exact_critic` | short YAML-only system (unchanged) | ExactCritic + TaskContract | identical block |
| C `C_typed_exact_critic` | `ARM_C_SYSTEM_PROMPT` (unchanged) | ExactCritic + TaskContract | identical block |

The Requirements block is rendered by `format_requirements_block` in `gd_picasso/bench/contracts.py` and appended to the **user/task text only**. System prompts are otherwise untouched.

## Tasks and samples

- Tasks 1–48 (`PICBENCH48_TASK_IDS`).
- Samples per task per arm: **5**.
- Model pin: `claude-sonnet-5-5` (`N1_LLM_MODEL_ID`).
- Temperature `0.3`, max tokens `4096`, max repair rounds `3`.
- Seeds: API sampling is stochastic at temperature 0.3; bootstrap seed is **0** (not an LLM seed).

## Statistical tests (tasks 1–46, and slices 1–36 and 37–46)

1. Wilson 95% CI on sample-level `pass_uniform`.
2. Task-clustered bootstrap 95% CI: 10 000 resamples of tasks, seed **0**.
3. Exact McNemar on task-level majority (≥3/5).
4. Wilcoxon signed-rank on per-task pass rates.

## Exclusion rule

Infrastructure errors (credit, connection, rate limit, timeout, 5xx) are retried up to **3** times, then **reported** in the CSV (`infra_retries`, problems text). They are never silently dropped.

## Manifest requirements

`n1_manifest.json` must show `worktree_clean: true` and a non-null `prompts_untouched_after_dry_run` (true iff frozen artifact hashes still match at end of run).
