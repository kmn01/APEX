# APEX AGI Planning and Strategy Audit

Evaluation lens: how close the current system is to an AGI-style planning stack that can form, execute, monitor, and revise strategy under uncertainty and multi-agent constraints.

## Executive Snapshot

- **Current maturity:** Research prototype
- **Planning architecture:** Hierarchical + tactical
- **Strategic closure:** Partial (**`plan`** with HTN+MCTS; **`replan`** optional MAP/Gemini path + validated deltas)
- **Readiness for AGI claim:** Early-stage

**Bottom line:**  
The project demonstrates HTN decomposition, **MCTS-augmented task assignment** in code, and tactical execution—but AGI-grade planning still requires **richer strategic objectives**, **closed-loop replanning**, **belief-level uncertainty**, and **reliability benchmarking**.

## Capability Scorecard

| Capability | Assessment | Evidence in APEX |
| --- | --- | --- |
| Hierarchical goal decomposition | Strong | HTN planner decomposes `fulfill_order` into ordered subtasks with method selection. |
| Long-horizon plan optimization | Weak–Moderate | In-tree **UCT MCTS** refines task→agent assignment under `PlanningMode.MCTS_AUGMENTED` (`mcts/search.py`, `mcts/domain.py`); objective is a **static per-task cost** plus **feasibility** via `Agent.can_perform`. **Strategic replan** (`StrategicCoordinator.replan`) can run a **MAP/Gemini** pipeline and emit **validated** `TaskGraphDelta` values when enabled (`docs/MAP_Gemini_Rollout.md`); richer objectives and rollback-safe production wiring remain open. |
| Execution-time adaptation | Moderate | Local replanner handles blocked path/pick failure, but globally limited escalation path. |
| Uncertainty handling | Weak | Stochastic events are injected, but no belief-state or probabilistic policy updates. |
| Multi-agent coordination | Moderate | Reservation-style path constraints exist; no full joint policy or negotiation protocol. |
| Learning from experience | Weak | No in-tree learning policy loop is implemented; adaptation remains search/rule driven. |
| Reliability evaluation | Weak | No pass^k-style consistency harness or benchmark-style repeatability metrics. |

## Literature Signals (2024-2026)

| Source | Implication for this codebase |
| --- | --- |
| Plan-and-Act (ICML 2025) | Planner/executor split with dynamic replanning improves long-horizon task success. |
| τ-bench (2024) + τ²-bench (2025) | Reliability and policy-following degrade sharply without explicit consistency-focused evaluation. |
| Thought of Search (NeurIPS 2024) | Planning systems should preserve soundness/completeness and avoid expensive unsystematic search. |
| LLMCompiler (ICML 2024) | Compile plans into dependency graphs and parallel execution to improve latency/cost/accuracy. |
| SWE-agent (NeurIPS 2024) | Task-specific agent-computer interfaces and constrained actions materially improve autonomous performance. |
| WebArena (ICLR 2024) + updates | Long-horizon real-world tasks expose failure recovery and coordination bottlenecks. |

## Where APEX Is Strong Today

- Structured HTN decomposition
- Explicit task graph abstractions
- Tactical disruption hooks

This is a good substrate for AGI planning research because strategic, adapter, tactical, and simulation layers are already separated. That modularity is aligned with modern planner-executor literature.

## Primary AGI Gaps

- **Closed-loop strategic revision (optional MAP path):** `replan` can consume `EscalationSignal` and emit a validated `TaskGraphDelta` when `APEX_MAP_*` flags and `GEMINI_API_KEY` are enabled; otherwise it returns an empty delta (deterministic baseline unchanged).
- No reliability/pass^k evaluation
- No learned adaptive policy in production path

Assignment search is now **stochastic tree search (MCTS)** in one planning mode, but behavior remains mostly **symbolic and rule-driven** for replanning, learning, and rich multi-criteria utilities (proximity, load, congestion are not yet in the MCTS leaf evaluator).

## Implementation Roadmap to AGI-Grade Planning

| Phase | Concrete deliverable |
| --- | --- |
| Phase 1: Strategic closure | **Partial:** `MCTSSearch.search` + `PlanningMode.MCTS_AUGMENTED` wired in `StrategicCoordinator.plan`. **Remaining:** richer replan policies/objectives, broader end-to-end integration, and production-grade rollback/reliability benchmarking. |
| Phase 2: Planner-executor contract | Add typed plan schema, executable checks, and automatic repair loop before dispatching instructions. |
| Phase 3: Reliability harness | Create benchmark tasks with dynamic disruptions; track success, pass^k consistency, policy violations, and recovery time. |
| Phase 4: Learning and adaptation | Add data-driven adaptation loops (e.g., learned heuristics) and evaluate generalization under disruption-heavy curricula. |
| Phase 5: Agentic interfaces | Add richer tactical tools and constrained action APIs so strategic models reason over stable, verifiable primitives. |

## Final Assessment

Credible claim today: APEX demonstrates a modular prototype for hierarchical planning plus tactical adaptation in a realistic simulator.  
Credible AGI claim after roadmap: APEX can execute strategic closed-loop planning, recover from disruptions, and maintain reliable performance across repeated evaluation protocols.

## Implementation Checklist (Open Items)

### Strategic Planning Core

- [x] Implement `MCTSSearch.search` main loop in `apex/planner/mcts/search.py`
- [x] Implement `MCTSSearch._select` (UCT traversal) in `apex/planner/mcts/search.py`
- [x] Implement `MCTSSearch._expand` (legal assignment expansion) in `apex/planner/mcts/search.py`
- [x] Implement `MCTSSearch._rollout` (random playout to terminal assignment) in `apex/planner/mcts/search.py`
- [x] Implement `MCTSSearch._backpropagate` in `apex/planner/mcts/search.py`
- [x] Wire `PlanningMode.MCTS_AUGMENTED` in `StrategicCoordinator.plan` (`apex/planner/coordinator.py`) via `AssignmentDomain` / `assignment_state_from_graph` in `apex/planner/mcts/domain.py`
- [x] Wire `StrategicCoordinator.replan` to consume `EscalationSignal` and optionally emit validated `TaskGraphDelta` via MAP/Gemini (`apex/planner/coordinator.py`, `apex/planner/specialists/`)

### Learning and Communication Stack

- [ ] Define and implement an optional data-driven adaptation module (heuristic learning or policy guidance)
- [ ] Add interfaces to consume adaptation signals in tactical or strategic planning

### Evaluation and Reliability

- [ ] Implement `MetricsCollector.compute_episode_metrics` in `apex/evaluation/metrics.py`
- [ ] Implement `ExperimentRunner.run_episode` in `apex/evaluation/runner.py`
- [ ] Implement `ExperimentRunner.run_sweep` in `apex/evaluation/runner.py`
- [ ] Add repeatability/reliability benchmarks (success rate, pass^k, recovery latency) under `tests/` and/or `experiments/`

### CLI and Operational Entry Points

- [ ] Implement scenario CLI in `scripts/run_scenario.py` (currently a placeholder)

### Tactical-System Integration Gaps

- [ ] Replace stub failure injection in `apex/simulation/events.py` with agent-aware disruption logic
- [ ] Add end-to-end tests that validate escalation -> strategic `replan` -> translated tasks -> resumed execution
