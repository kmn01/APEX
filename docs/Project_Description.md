# APEX: Adaptive Planning EXecution for multi-agent warehouse orchestration

## Overview
APEX (**Adaptive Planning EXecution**) is a hierarchical multi-agent planning system for warehouse logistics research. It coordinates a fleet of heterogeneous robot agents (picker, carrier, sorter) across a strategic planning layer and a tactical execution layer, with a domain adapter translating abstract tasks into concrete warehouse instructions (shelf IDs, conveyor segments, loading bays).

The system is designed as a practical research substrate for symbolic planning, search-augmented assignment, and disruption recovery in dynamic environments.

## Core Architecture
The architecture is composed of five interacting components:

- **Strategic Planner (Layer 1)** — Receives order batches and performs goal decomposition and assignment. It uses hand-authored HTN methods (`HTNPlanner`) and can optionally run UCT MCTS assignment via `PlanningMode.MCTS_AUGMENTED`. Output is a `TaskGraph` with task types, dependencies, and optional `agent_id` assignments.
- **Domain Adapter (Layer 2)** — Resolves abstract tasks into concrete resources and instructions. `TaskResolver` maps warehouse entities; `DomainTranslator` emits executable `TaskInstruction` records.
- **Tactical Executor (Layer 3)** — Runs per-agent instruction queues and local repair. Tactical routing now includes full Conflict-Based Search (`CBSPlanner`) with constrained low-level A* (`SimplePathfinder.find_path_with_constraints`) for concurrent `MOVE_TO` coordination; reservation-table A* (`SimplePathfinder` + `ReservationTable`) remains available as a fallback path. Disruption handling uses `LocalReplanner` with escalation to strategic replanning when local repair is insufficient.
- **Agent Pool** — Heterogeneous agents with different capabilities and constraints; strategic assignment checks feasibility through `Agent.can_perform`.
- **Warehouse Simulation Environment** — Grid-based SimPy environment modeling shelves, conveyors, bays, and stochastic disruptions/events.

## Key Technical Contributions
- **Hierarchical planning with escalation:** strategic decomposition + tactical local repair, with escalation boundaries via `EscalationSignal`.
- **Search-augmented assignment:** HTN-generated tasks can be post-processed by UCT MCTS to improve task-agent allocation quality.
- **MAP-style specialist integration (optional):** `StrategicCoordinator` can run a modular MAP/Gemini pipeline (decompose, predict, monitor, coordinate) for both `plan` and `replan`, with strict schema and graph validation plus deterministic fallback.
- **Typed contracts:** strategic edits flow through `TaskGraphDelta` with validation (`validate_task_graph_delta`, `apply_task_graph_delta`).

## Scenario and Evaluation Status
APEX combines unit tests with a **typed episodic harness** built on **`ScenarioSpec`** (`apex/scenarios/models.py`): YAML or catalog-backed layouts, scripted order releases, deterministic seeds, horizon bounds, optional **`StochasticEventGenerator`** (when enabled on the **`RunConfig`**), and disruption scripts.

**`EpisodeDriver`** (`apex/evaluation/episode_driver.py`) runs one episode headlessly through **`StrategicCoordinator`** ( **`PlanningMode.HTN_ONLY`** or **`MCTS_AUGMENTED`** ), **`DomainTranslator`**, graph-to-instruction materialization (**`apex/evaluation/graph_flow.py`** ), and **`TacticalExecutor`** with optional **`CBSPlanner`** injection. Per-episode knobs live on **`RunConfig`** (`apex/evaluation/run_config.py`): **`TacticalCoordination`** (**CBS batch expansion** vs **greedy uncoordinated** **`MOVE_TO`**), **`StrategicReplanMode`** (escalations may trigger **`replan`** + delta apply or **`HTN` fallback**, or escalation may be logged only when disabled), **`quiet`** logging, stochastic disruption toggle, and optional **`VideoRecordingConfig`** (**pygame** step loop + **`VideoRecorder`** / **imageio** MP4).

**`ExperimentRunner`** (`apex/evaluation/runner.py`) implements **`run_episode`** and **`run_sweep`** by delegating to **`EpisodeDriver`**. **`scripts/run_scenario.py`** persists runs (**`apex/evaluation/io.py`**: JSON/JSONL artifacts) from catalog ids or **`--yaml`** paths; **`examples/end_to_end_demo.py`** remains the lighter HTN→adapter→executor walkthrough with optional **`--record-video`**.

Current reliability hooks include fallback counters and plan-run hashing support (`MapReliabilityMetrics`) for pass^k-style consistency tracking; sweep automation beyond sequential **`run_sweep`** is optional future work.

**Reproducibility (quick reference):** for offline invariant checks, set `APEX_MAP_ENABLED=false`, run `pip install -e ".[dev]"`, run `pytest`, and use the YAML suite commands in [Scenario_Test_Suite.md](Scenario_Test_Suite.md) and the root [README.md](../README.md).

## Implementation Snapshot
- Strategic: `apex/planner/htn/`, `apex/planner/mcts/`, `apex/planner/coordinator.py`, `apex/planner/specialists/`
- Adapter: `apex/adapter/`
- Tactical: `apex/tactical/`
- Simulation: `apex/simulation/`
- Scenarios: `apex/scenarios/` (specs, `catalog`, `builder`, sample YAML)
- Evaluation: `apex/evaluation/` (`EpisodeDriver`, `ExperimentRunner`, `run_config`, `metrics`, `io`)
- Visualization: `apex/visualization/viewer.py`, `apex/visualization/recorder.py` (optional MP4)
- CLI: `scripts/run_scenario.py`

## Keywords
hierarchical planning, HTN, MCTS, MAP-style orchestration, Gemini integration, task-graph validation, tactical replanning, multi-agent warehouse simulation
