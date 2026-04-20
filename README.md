# APEX

**APEX** (Adaptive Planning EXecution) is a hierarchical multi-agent planning stack for grid-based warehouse logistics simulation. A strategic layer decomposes order batches into task structure; a domain adapter grounds abstract tasks in shelf, conveyor, and bay identifiers; a conflict-based tactical layer moves heterogeneous agents under disruptions; and SimPy advances discrete time.

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
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional groups: `viz` (pygame-ce), `gnn` (torch stack).

## Layout

See `docs/Implementation_Plan.md` for the full module layout. Generated skeletons under `apex/` include module docstrings, typed stubs (`NotImplementedError` where behavior is pending), and a small `if __name__ == "__main__":` smoke block per file.

## Smoke-check a module

From the repo root (with the package on `PYTHONPATH`, or after `pip install -e .`):

```bash
python -m apex.simulation.grid
python -m apex.simulation.warehouse
```

## Tests

```bash
pytest
```

(Add tests under `tests/` as behavior is implemented.)
