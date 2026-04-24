# Implementation Plan

## Incremental module structure

* The project is organized into six modules, each buildable and testable in isolation before wiring up to the next. The dependency flows from the bottom up — later modules consume APIs from earlier ones but don't reach back down.
* Each module has a clear scope and a testable milestone. M1 is just a working grid simulation with no agents. M2 adds dumb agents that can be placed and moved by hand. M3 gives them autonomous navigation. M4 teaches them to understand warehouse-specific instructions. M5 adds the brain that issues those instructions. M6 wraps everything with observability.

### Module Breakdown
* M1 — Simulation Core (simulation/) The warehouse world: grid, shelves, conveyors, bays, orders, and the SimPy environment. Everything else depends on this.
* M2 — Agent Pool (agents/) Heterogeneous agents (picker, carrier, sorter) as SimPy processes. Each agent is a class with capabilities and a run() coroutine.
* M3 — Tactical Executor (tactical/) Per-agent pathfinding (CBS) and local replanning. Handles collisions and small disruptions without escalating to the strategic planner.
* M4 — Domain Adapter (adapter/) Bridges abstract task specs ("pick item from zone C") to physical warehouse references (shelf ID, conveyor segment, bay slot).
* M5 — Strategic Planner (planner/) HTN decomposition → MCTS task assignment → (eventually) MAPPO warm-start. Produces a TaskGraph that the adapter and executor consume.
* M6 — Comms & Evaluation (comms/, evaluation/) Shared blackboard for Phase 1 agent coordination; metrics collection and experiment runner.
* M7 — Visualization 


## Project structure

apex/
│
├── pyproject.toml
├── README.md
├── .env.example
│
├── config/
│   ├── warehouse_default.yaml     # grid size, shelf layout, agent counts
│   └── experiment_base.yaml       # scenario params, seeds, disruption rate
│
├── apex/
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── grid.py                # Grid, CellType — occupancy + walkability
│   │   ├── warehouse.py           # WarehouseState, ShelfZone, ConveyorSegment, LoadingBay
│   │   ├── order.py               # Order, OrderItem, OrderBatch, OrderStatus
│   │   └── events.py              # StochasticEventGenerator (SimPy-based)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # Agent ABC, AgentCapabilities, AgentStatus
│   │   ├── picker.py
│   │   ├── carrier.py
│   │   ├── sorter.py
│   │   └── registry.py            # AgentRegistry — fleet queries
│   │
│   ├── tactical/
│   │   ├── __init__.py
│   │   ├── pathfinder.py          # CBS, ReservationTable
│   │   ├── executor.py            # TacticalExecutor — instruction → actions
│   │   └── replanner.py           # LocalReplanner — disruption handling
│   │
│   ├── adapter/
│   │   ├── __init__.py
│   │   ├── translator.py          # DomainTranslator — abstract → concrete
│   │   └── resolver.py            # TaskResolver — SKU/zone → shelf/bay/conveyor
│   │
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── htn/
│   │   │   ├── operators.py       # HTNOperator, TaskType enum
│   │   │   ├── methods.py         # HTNMethod decomposition rules
│   │   │   └── planner.py         # HTNPlanner.decompose(), .plan_batch()
│   │   ├── mcts/
│   │   │   ├── node.py            # MCTSNode, AssignmentState
│   │   │   └── search.py          # MCTSSearch.search()
│   │   ├── marl/
│   │   │   ├── policy.py          # MAPPOPolicy stub (Phase 3)
│   │   │   └── trainer.py         # SelfPlayTrainer stub (Phase 3)
│   │   └── coordinator.py         # StrategicCoordinator — top-level API
│   │
│   ├── comms/
│   │   ├── __init__.py
│   │   ├── blackboard.py          # SharedBlackboard, AgentIntention
│   │   └── gnn.py                 # GNNComm stub (Phase 3)
│   │
│   └── evaluation/
│       ├── __init__.py
│       ├── metrics.py             # MetricsCollector, EpisodeMetrics
│       └── runner.py              # ExperimentRunner, ScenarioConfig
│
├── viz/
│   ├── renderer.py                # Pygame-CE grid view (import-guarded)
│   └── dashboard.py               # Optional FastAPI + htmx live view
│
├── scripts/
│   ├── run_scenario.py            # CLI entry point
│   └── train_marl.py              # MAPPO training (Phase 3)
│
├── experiments/
│   ├── baseline_cbs.yaml
│   ├── htn_only.yaml
│   └── full_system.yaml
│
└── tests/
    ├── test_grid.py
    ├── test_warehouse.py
    ├── test_pathfinder.py
    ├── test_htn_planner.py
    └── test_domain_adapter.py
