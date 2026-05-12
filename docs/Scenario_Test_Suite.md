# Scenario test suite

This document describes the YAML scenarios under [`apex/scenarios/data/suite/`](../apex/scenarios/data/suite/), what each one is meant to exercise, what to expect in the evaluation outputs, and how to run them.

## Prerequisites

- Python **3.11+** (matches `requires-python` in `pyproject.toml`).
- From the repository root, install the package with dev dependencies (PyYAML is required for `--yaml`):

  ```bash
  pip install -e ".[dev]"
  ```

- Optional: `pip install -e ".[viz]"` if you pass `--record-video` to [`scripts/run_scenario.py`](../scripts/run_scenario.py).

- If you use **MAP / Gemini** (`GEMINI_API_KEY` in `.env`), the coordinator may call the API; failures fall back to the baseline planner, but runs are noisier and may be slower. For **reproducible local checks**, run with MAP off:

  ```bash
  export APEX_MAP_ENABLED=false
  ```

## Command pattern

Every scenario is run with the evaluation CLI. You must pass exactly one of `--scenario` or `--yaml`, plus an output directory:

```bash
python scripts/run_scenario.py --yaml apex/scenarios/data/suite/<file>.yaml --output runs/<run_name>
```

The process:

1. Prints a JSON object to **stdout** ([`EpisodeMetrics`](../apex/evaluation/metrics.py): task rates, instruction counts, disruption/replan/escalation counts, `sim_duration`, `horizon`, etc.).
2. Writes under `--output`:
   - `metrics.json` — same scalars as stdout
   - `events.jsonl` — one JSON object per line: `type` + `data` (see the event list in the docstring at the top of [`apex/evaluation/metrics.py`](../apex/evaluation/metrics.py))
   - `run_manifest.json` — pinned scenario dump, fingerprint, environment metadata, and CLI snapshot

Optional flags (see the script’s `--help`):

- `--coordination cbs` | `greedy_uncoordinated`
- `--planning-mode HTN_ONLY` | `MCTS_AUGMENTED`
- `--no-replan` — disable strategic replan on escalation
- `--verbose` — disable quiet mode (more console output from the simulation)
- `--record-video` — MP4 under `<output>/videos` (requires `viz` extras)

## Catalog equivalence

Most suite files are exported from the Python catalog so they stay aligned with [`build_scenario`](../apex/scenarios/catalog.py). Re-export after changing a catalog builder:

```bash
python scripts/export_catalog_scenario_to_yaml.py \
  --scenario single_order_single_agent \
  --output apex/scenarios/data/suite/baseline_single_agent.yaml
```

| Suite YAML `id` field | Catalog `--scenario` key | File |
| --- | --- | --- |
| same as catalog `id` | `single_order_single_agent` | [`baseline_single_agent.yaml`](../apex/scenarios/data/suite/baseline_single_agent.yaml) |
| `two_agents_crossing` | `two_agents_crossing` (alias: `crossing_agents`) | [`two_agents_crossing.yaml`](../apex/scenarios/data/suite/two_agents_crossing.yaml) |
| `order_batch_queue` | `order_batch_queue` | [`order_batch_queue.yaml`](../apex/scenarios/data/suite/order_batch_queue.yaml) |
| `shelf_block_recovery` | `shelf_block_recovery` | [`shelf_block_recovery.yaml`](../apex/scenarios/data/suite/shelf_block_recovery.yaml) |
| `injected_priority_order` | `injected_priority_order` | [`injected_priority_order.yaml`](../apex/scenarios/data/suite/injected_priority_order.yaml) |

The following exist only as YAML (hand-authored): `agent_failure_escalation`, `stochastic_optional`.

**Legacy sample:** [`apex/scenarios/data/single_order.yaml`](../apex/scenarios/data/single_order.yaml) is an older standalone example. The canonical baseline for the suite is [`baseline_single_agent.yaml`](../apex/scenarios/data/suite/baseline_single_agent.yaml) (catalog export).

---

## Per-scenario reference

Metrics below are **representative** with `APEX_MAP_ENABLED=false` and current HTN/tactical behavior. They are **not** golden snapshots: `completed_instruction_count` and similar fields may change if planners or decomposition change. Use **invariants** when automating checks.

### `baseline_single_agent.yaml`

- **Purpose:** Single picker, two-line order, conveyor and bay; end-to-end smoke (strategic → adapter → tactical CBS).
- **Key parameters:** Horizon 3000, grid 16×16, scripted `disruptions: []`.
- **Expected output (invariants):**
  - `scheduled_instruction_count` and `completed_instruction_count` equal; both **≥ 8** with default HTN decomposition.
  - `disruption_count == 0`, `replan_count == 0`, `escalation_count == 0` for this static case.
  - `horizon` matches the YAML `horizon` field; `sim_duration` > 0 (max timestamp seen in instrumented events).
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/baseline_single_agent.yaml \
    --output runs/baseline_single_agent
  ```

### `two_agents_crossing.yaml`

- **Purpose:** Two pickers and two orders from t=0 so the tactical layer often sees **parallel `MOVE_TO`** (CBS batching in the executor).
- **Key parameters:** Horizon 5000, grid 14×14, no disruptions.
- **Expected output (invariants):**
  - Instruction counts equal and **≥ 16** (two full order flows).
  - Compare coordination modes, e.g. CBS vs greedy (throughput may match for this layout; see unit tests in [`tests/test_evaluation_episode_smoke.py`](../tests/test_evaluation_episode_smoke.py)).
  - Check `executed_conflict_count` / `planned_spacetime_conflict_count` in `metrics.json` when investigating path interactions.
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/two_agents_crossing.yaml \
    --output runs/two_agents_crossing
  ```
- **Variant:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/two_agents_crossing.yaml \
    --output runs/two_agents_crossing_greedy \
    --coordination greedy_uncoordinated
  ```

### `order_batch_queue.yaml`

- **Purpose:** Two agents with **staggered order arrivals** (waves at 0, 400, 900) to stress replanning/activation over a longer horizon.
- **Key parameters:** Horizon 8000, grid 18×18.
- **Expected output (invariants):**
  - Non-zero throughput: completed instruction count **≥ 20** typically.
  - `sim_duration` reflects the latest instrumented event time (often well before `horizon` if all orders finish early).
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/order_batch_queue.yaml \
    --output runs/order_batch_queue
  ```
- **Variant:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/order_batch_queue.yaml \
    --output runs/order_batch_mcts \
    --planning-mode MCTS_AUGMENTED
  ```

### `shelf_block_recovery.yaml`

- **Purpose:** Scripted `shelf_block` disruption (`EpisodeDriver._scripted_disruption`) temporarily reduces shelf capacity.
- **Key parameters:** Disruption near t=50 with duration in payload.
- **Expected output (invariants):**
  - `disruption_count >= 1`.
  - Episode should still complete work: `completed_instruction_count` ≥ 8 for the baseline catalog layout.
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/shelf_block_recovery.yaml \
    --output runs/shelf_block_recovery
  ```

### `injected_priority_order.yaml`

- **Purpose:** Scripted `inject_order` adds a high-priority order mid-episode.
- **Expected output (invariants):**
  - `disruption_count >= 1`.
  - Higher total instruction count than the single static order case (multiple order lifecycles).
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/injected_priority_order.yaml \
    --output runs/injected_priority_order
  ```

### `agent_failure_escalation.yaml`

- **Purpose:** Same layout as `two_agents_crossing` plus scripted `agent_fail` on `picker-0` after work has started; exercises local replan handling and **strategic replan** (`htn_fallback`) on escalation.
- **Key parameters:** Failure at t=150; horizon 9000.
- **Expected output (invariants):**
  - `disruption_count >= 1`, `escalation_count >= 1`, `replan_count >= 1` in typical runs.
  - Remaining agent should still contribute: `completed_instruction_count` > 0.
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/agent_failure_escalation.yaml \
    --output runs/agent_failure_escalation
  ```
- **Variant (no strategic replan):**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/agent_failure_escalation.yaml \
    --output runs/agent_failure_no_replan \
    --no-replan
  ```

### `stochastic_optional.yaml`

- **Purpose:** Same workload skeleton as `order_batch_queue` with [`StochasticEventGenerator`](../apex/simulation/events.py) enabled (`stochastic_disruption` + `run.disruption_stochastic_enabled: true`). Injects random shelf blocks and orders (agent failures stubbed off via `agent_failure_rate: 0`).
- **Important:** The generator **does not** emit `MetricsCollector` `disruption` events, so **`disruption_count` may stay 0** while the world still changes. Inspect **`events.jsonl`** only for typed metrics that the driver records; for stochastic debugging, stderr is suppressed when `quiet: true` unless you use `--verbose` or temporarily enable prints in development.
- **Expected output (invariants):**
  - Large instruction volume versus non-stochastic baselines (`completed_instruction_count` often in the thousands for an 8000 horizon with moderate `disruption_rate`).
  - `sim_duration` often tracks the maximum seen event time and may approach `horizon` when agents stay busy.
- **Command:**
  ```bash
  python scripts/run_scenario.py \
    --yaml apex/scenarios/data/suite/stochastic_optional.yaml \
    --output runs/stochastic_optional
  ```

---

## Scripted disruption coverage

Kinds handled in [`EpisodeDriver._scripted_disruption`](../apex/evaluation/episode_driver.py) today: `shelf_block`, `inject_order`, `agent_fail`. Scenario kinds `shelf_unblock` and `new_priority` exist on [`ScenarioSpec`](../apex/scenarios/models.py) but are **not** implemented in that driver branch yet—avoid them in YAML until support lands.
