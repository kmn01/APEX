# Implementation Plan

## Incremental module structure

- The project is organized into layered modules that can be tested in isolation before full integration.
- Early modules provide simulation and execution primitives; later modules add strategic search, optional LLM augmentation, and evaluation.

### Module Breakdown
- **M1 — Simulation Core (`simulation/`)**: Grid, warehouse state, orders, and SimPy event model.
- **M2 — Agent Pool (`agents/`)**: Picker/carrier/sorter agents and fleet registry.
- **M3 — Tactical Executor (`tactical/`)**: A* pathfinding with reservation-table conflict avoidance, tactical instruction execution, local replanning and escalation.
- **M4 — Domain Adapter (`adapter/`)**: Abstract-task-to-concrete-resource translation.
- **M5 — Strategic Planner (`planner/`)**: HTN decomposition and optional MCTS assignment (`PlanningMode.MCTS_AUGMENTED`), plus optional MAP/Gemini specialist pipeline for plan/replan with validation and fallback.
- **M6 — Comms & Evaluation (`comms/`, `evaluation/`)**: Shared blackboard and reliability/evaluation harness (runner still partial).
- **M7 — Visualization**: Optional rendering/dashboard surfaces.

## Current project structure (high-level)

```
apex/
├── pyproject.toml
├── README.md
├── .env.example
├── apex/
│   ├── simulation/
│   ├── agents/
│   ├── tactical/
│   ├── adapter/
│   ├── planner/
│   │   ├── htn/
│   │   ├── mcts/
│   │   ├── specialists/
│   │   ├── graph_delta.py
│   │   └── coordinator.py
│   ├── comms/
│   └── evaluation/
├── config/
├── docs/
├── examples/
├── experiments/
├── scripts/
└── tests/
```

## Strategic planner state

- `HTNPlanner.plan_batch` is implemented and produces `TaskGraph`.
- `MCTSSearch` and `PlanningMode.MCTS_AUGMENTED` are implemented for assignment refinement.
- `StrategicCoordinator.replan` supports an optional MAP/Gemini path that emits validated `TaskGraphDelta` when enabled.
- MAP outputs are schema-checked and graph-validated; failures fallback to deterministic baseline behavior.

## Tests

Current suite is authoritative under `tests/` (run `pytest`):

- `test_domain_adapter.py`
- `test_local_replanner.py`
- `test_mcts.py`
- `test_settings.py`
- `test_simulation_events.py`
- `test_specialist_orchestrator.py`
- `test_strategic_planner.py`
- `test_tactical_executor.py`
- `test_task_graph_delta_application.py`

(As features evolve, rely on `pytest` output rather than static lists in docs.)
