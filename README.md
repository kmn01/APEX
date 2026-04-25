# APEX

**APEX** (Adaptive Planning EXecution) is a hierarchical multi-agent planning system for a grid-based warehouse simulation. The strategic layer takes incoming order batches and breaks them into a structured set of tasks (what needs to happen, in what order). A domain adapter then turns those abstract tasks into concrete locations the simulation understands—shelves, conveyor segments, loading bays, and similar IDs—so “pick in zone C” becomes something the world can act on. The tactical layer plans routes and motion for different agent types (e.g. pickers, carriers, sorters) using conflict-aware methods so robots don’t get in each other’s way, and it can adjust locally when the floor changes or something goes wrong. SimPy drives the whole thing by stepping time forward in a discrete-event way so the warehouse and agents evolve together.

## Architecture

| Layer | Role | Key modules |
| --- | --- | --- |
| Simulation | Grid, warehouse state, orders, stochastic events | `apex/simulation/` |
| Agents | Picker, carrier, sorter bots; fleet registry | `apex/agents/` |
| Tactical | CBS-style pathfinding, task executor, local replanner | `apex/tactical/` |
| Adapter | SKU/bay/conveyor resolution and task translation | `apex/adapter/` |
| Planner | HTN operators/methods/planner, MCTS assignment, MARL stubs | `apex/planner/` |
| Comms | Shared blackboard; GNN comms stub (Phase 3) | `apex/comms/` |
| Evaluation | Metrics collector and scenario runner | `apex/evaluation/` |

**Conventions**

- **Positions** are `Pos = tuple[int, int]` as `(row, col)`.
- The **SimPy environment** is always passed explicitly (no global `env`).
- **`WarehouseState`** is the single shared snapshot passed into planners and processes.
- **Data** uses **Pydantic v2** `BaseModel`; **algorithms** use `ABC` or `dataclass` as appropriate.
- Optional **pygame-ce** (visualization) and **torch / torch-geometric** (GNN) are optional extras, not required for core imports.

## Install

```bash
# Clone & enter repo
cd APEX
# Create virtual environment
python -m venv .venv
source .venv/bin/activate
# Install with development + visualization
pip install -e ".[dev,viz]"
```

Optional groups: `viz` (pygame-ce), `gnn` (torch stack).


## Test a module

From the repo root (with the package on `PYTHONPATH`, or after `pip install -e .`):

```bash
python -m apex.simulation.grid
python -m apex.simulation.warehouse
```
## Test Individual Modules

```bash
# M3: Tactical Executor
python -m apex.tactical.executor

# M3: Local Replanner
python -m apex.tactical.replanner

# M4: Domain Adapter
python -m apex.adapter.translator

# M5: Strategic Planner
python -m apex.planner.htn.planner
```
## Run End-to-End Demo with Visualization

```bash
python examples/end_to_end_demo.py
```

This will:
- Create a 20×20 warehouse grid
- Plan 2 orders into 8 task nodes
- Generate 6 concrete instructions
- Display live visualization with 2 agents

---

## Tests

```bash
pytest

or

pytest tests/ -v
```

(Add tests under `tests/` as behavior is implemented.)
