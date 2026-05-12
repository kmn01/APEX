# APEX

**APEX (Adaptive Planning and Execution System)** is a **hierarchical multi-agent planning system** for warehouse logistics simulation. The system coordinates a fleet of heterogeneous robot agents, like pickers, carriers, and sorters, across a two-layer planning architecture: a strategic layer that decomposes order batches into structured task graphs using Hierarchical Task Networks (HTN) and Monte Carlo Tree Search (MCTS), and a tactical layer that executes those tasks using Conflict-Based Search (CBS) pathfinding with real-time disruption recovery. A domain adapter bridges the two layers by translating abstract task types into concrete warehouse instructions grounded in physical shelf IDs, conveyor segments, and loading bays. APEX further integrates Google Gemini as the large language model (LLM) backbone via a Modular Agentic Planning (MAP) pipeline, which refines HTN-generated plans using language-driven reasoning while guaranteeing deterministic fallback. We evaluate the system across seven scenarios covering normal operation, multi-agent coordination, staggered order waves, and scripted disruptions including shelf blocks, order injection, and agent failure. APEX achieves 100\% task completion rate across all evaluated scenarios with near zero collisions in coordinated runs, providing concrete evidence of end-to-end correctness and adaptability.

## Project overview

| Concern | Role | Primary location |
| --- | --- | --- |
| Simulation | Grid, warehouse state, orders, scripted or stochastic events | `apex/simulation/` |
| Agents | Picker, carrier, sorter bots; fleet registry | `apex/agents/` |
| Strategic planning | HTN decomposition, MCTS assignment, coordinator, MAP / Google Gemini specialists | `apex/planner/` |
| Adapter | SKU / layout resolution; task → instructions | `apex/adapter/` |
| Tactical | Executor, CBS + constrained A*, reservation fallback, replanner | `apex/tactical/` |
| Evaluation | Episode driver, metrics, run artifacts, experiment sweeps | `apex/evaluation/` |
| Scenarios | Typed `ScenarioSpec`, YAML + catalog builders | `apex/scenarios/` |
| Comms | Shared blackboard for agent intentions | `apex/comms/` |

**Conventions**

- **Positions** are `Pos = tuple[int, int]` as `(row, col)`.
- The **SimPy environment** is always passed explicitly (no global `env`).
- **`WarehouseState`** is the single shared snapshot passed into planners and processes.
- **Data** uses **Pydantic v2** `BaseModel`; **algorithms** use `ABC` or `dataclass` as appropriate.

## Requirements

- **Python 3.11+** (see `pyproject.toml`).

## Setup

```bash
cd APEX
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Core library, tests, YAML scenarios, and Google GenAI client for MAP / Gemini
pip install -e ".[dev,llm]"
```

The **`[llm]`** dependency group in `pyproject.toml` pins **`google-genai`** and **`python-dotenv`** used by `apex/planner/specialists/`; it is part of the default install command above, not a separate add-on.

**Visualizations**:

| Name | Purpose |
| --- | --- |
| `viz` | pygame-ce, imageio (+ ffmpeg) for MP4 from `examples/end_to_end_demo.py` and `--record-video` on the scenario CLI |
| `eval` | matplotlib, PyYAML for `scripts/plot_benchmarks.py` and analysis-style workflows |
| `dashboard` | FastAPI, uvicorn, Jinja2 for the local runs browser under `viz/` |

Copy [`.env.example`](.env.example) to `.env` and set **`GEMINI_API_KEY`** (and any `APEX_*` overrides) for live Gemini calls; see [docs/MAP_Gemini_Rollout.md](docs/MAP_Gemini_Rollout.md).

## Usage

### Evaluation CLI

[`scripts/run_scenario.py`](scripts/run_scenario.py) loads a **`ScenarioSpec`** from the **catalog** or a **YAML** file, runs **`EpisodeDriver`**, prints **`EpisodeMetrics`** JSON to stdout, and writes a run directory.

```bash
# Catalog scenario (see table below)
python scripts/run_scenario.py --scenario two_agents_crossing --output runs/demo

# YAML scenario (suite lives under apex/scenarios/data/suite/)
python scripts/run_scenario.py \
  --yaml apex/scenarios/data/suite/baseline_single_agent.yaml \
  --output runs/baseline

# Overrides (see --help for full list)
python scripts/run_scenario.py --scenario order_batch_queue --output runs/mcts \
  --planning-mode MCTS_AUGMENTED --coordination cbs --verbose
```

**Catalog scenario IDs** (`--scenario`): `single_order_single_agent`, `two_agents_crossing`, `crossing_agents` (alias), `order_batch_queue`, `shelf_block_recovery`, `injected_priority_order`.

**Common flags** (see `python scripts/run_scenario.py --help` for the full list):

- `--coordination` — `cbs` (default in most builders) or `greedy_uncoordinated`
- `--planning-mode` — `HTN_ONLY` or `MCTS_AUGMENTED`
- `--no-replan` — disable strategic replan on escalation
- `--verbose` — extra console logging (default runs are quiet)
- `--record-video` — MP4 under `<output>/videos` (requires `pip install -e ".[viz]"`)

**Run directory artifacts** (under `--output`): `metrics.json`, `events.jsonl`, `run_manifest.json` (pinned scenario, CLI snapshot, environment metadata); optional `videos/*.mp4`.

### Runs dashboard

Browse folders produced by the CLI. Each run should contain at least `metrics.json`, `events.jsonl`, and `run_manifest.json`.

```bash
pip install -e ".[dashboard]"
python viz/dashboard.py --runs runs
# Open the printed URL (default bind http://127.0.0.1:8765/)
```

### Interactive end-to-end demo (HTN → adapter → executor → pygame)

Lighter than **`EpisodeDriver`**: one picker queue, no CBS batching path. Good for understanding the pipeline.

```bash
pip install -e ".[viz]"   # only if you want the window or --record-video
python examples/end_to_end_demo.py
python examples/end_to_end_demo.py --record-video --video-output artifacts/videos
```

### MAP / Google Gemini

Strategic planning runs the **MAP** pipeline (Gemini-backed specialists) by default when a client can be initialized; set **`GEMINI_API_KEY`** in `.env` (see [`.env.example`](.env.example)). Unset keys, failed init, or invalid model output **fall back** to the deterministic HTN/MCTS baseline. 

### Plotting metrics

```bash
pip install -e ".[eval]"
python scripts/plot_benchmarks.py --input runs/sweep_folder --output runs/summary.png
```

## Reproducing core functionality and results

1. **Tests**

   ```bash
   pytest
   # or
   pytest tests/ -v
   ```

2. **Scenario suite**  
   After `pip install -e ".[dev,llm]"`, run representative YAML cases and inspect `metrics.json` / `events.jsonl`:

   ```bash
   export APEX_MAP_ENABLED=false   # recommended for invariant checks
   python scripts/run_scenario.py --yaml apex/scenarios/data/suite/baseline_single_agent.yaml --output runs/baseline_single_agent
   python scripts/run_scenario.py --yaml apex/scenarios/data/suite/two_agents_crossing.yaml --output runs/two_agents_crossing
   ```

   [docs/Scenario_Test_Suite.md](docs/Scenario_Test_Suite.md).

3. **Align YAML with catalog after editing builders**

   ```bash
   python scripts/export_catalog_scenario_to_yaml.py \
     --scenario single_order_single_agent \
     --output apex/scenarios/data/suite/baseline_single_agent.yaml
   ```

4. **Module entrypoints** (quick smoke without pytest)

   ```bash
   python -m apex.simulation.grid
   python -m apex.simulation.warehouse
   python -m apex.tactical.executor
   python -m apex.tactical.replanner
   python -m apex.adapter.translator
   python -m apex.planner.htn.planner
   ```

## Packaging

Project name and Python requirement are declared in `pyproject.toml` (`name = "apex"`, `requires-python = ">=3.11"`).
