"""Strategic coordination across HTN and MCTS modes.

:class:`StrategicCoordinator` owns the high-level planning mode and bridges batch
orders to :class:`~apex.planner.htn.planner.TaskGraph` structures, including
incremental updates after tactical :class:`~apex.tactical.replanner.EscalationSignal`
events.
"""

from __future__ import annotations

from enum import Enum
from hashlib import sha256
from typing import Any, Callable
from uuid import uuid4

from apex.agents.registry import AgentRegistry
from apex.config.settings import ApexSettings, get_settings
from apex.planner.graph_delta import (
    TaskGraphDelta,
    apply_task_graph_delta,
    validate_task_graph,
    validate_task_graph_delta,
)
from apex.planner.htn.planner import HTNPlanner
from apex.planner.htn.planner import TaskGraph, TaskNode
from apex.planner.mcts.domain import AssignmentDomain, assignment_state_from_graph
from apex.planner.mcts.search import MCTSSearch
from apex.planner.specialists.metrics import MapReliabilityMetrics
from apex.planner.specialists.orchestrator import MapOrchestrator
from apex.simulation.order import OrderBatch
from apex.simulation.warehouse import WarehouseState
from apex.tactical.replanner import EscalationSignal


class PlanningMode(str, Enum):
    """Which strategic stack is active."""

    HTN_ONLY = "HTN_ONLY"
    MCTS_AUGMENTED = "MCTS_AUGMENTED"


class StrategicCoordinator:
    """Facade over HTN/MCTS for batch planning and replanning."""

    def __init__(
        self,
        mode: PlanningMode,
        warehouse_state: WarehouseState,
        agent_registry: AgentRegistry,
        *,
        settings: ApexSettings | None = None,
        map_orchestrator: MapOrchestrator | None = None,
        map_metrics: MapReliabilityMetrics | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.mode = mode
        self.warehouse_state = warehouse_state
        self.agent_registry = agent_registry
        self._settings = settings or get_settings()
        self._event_sink = event_sink
        self._map_orchestrator = map_orchestrator or MapOrchestrator(
            settings=self._settings, event_sink=self._emit
        )
        self._map_metrics = map_metrics or MapReliabilityMetrics()
        self._htn_planner = HTNPlanner(event_sink=self._emit)
        self._last_task_graph: TaskGraph | None = None
        self._last_plan_run_id: str | None = None
        self._last_graph_version_id: str | None = None

    def __repr__(self) -> str:
        return (
            f"StrategicCoordinator(mode={self.mode!r}, "
            f"warehouse_state={self.warehouse_state!r}, "
            f"agent_registry={self.agent_registry!r})"
        )

    @property
    def last_plan_run_id(self) -> str | None:
        return self._last_plan_run_id

    @property
    def last_graph_version_id(self) -> str | None:
        return self._last_graph_version_id

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_sink is not None:
            self._event_sink(event_type, payload)

    def _graph_version(self, graph: TaskGraph) -> str:
        digest = sha256(
            repr(
                sorted(
                    (
                        n.id,
                        str(n.task_type),
                        n.agent_id,
                        n.order_id,
                        tuple(n.dependencies),
                        float(n.deadline),
                    )
                    for n in graph.nodes
                )
            ).encode("utf-8")
        ).hexdigest()
        return f"graph_{digest[:16]}"

    def plan(self, order_batch: OrderBatch) -> TaskGraph:
        """Produce a fresh :class:`TaskGraph` for ``order_batch``."""
        self._last_plan_run_id = f"plan_{uuid4().hex}"
        self._emit(
            "planning.plan_started",
            {
                "plan_run_id": self._last_plan_run_id,
                "mode": self.mode.value if isinstance(self.mode, PlanningMode) else str(self.mode),
                "order_count": len(order_batch.orders),
            },
        )
        if self.mode == PlanningMode.HTN_ONLY:
            graph = self._htn_planner.plan_batch(order_batch, self.warehouse_state)
            graph = self._maybe_map_refine_plan(order_batch, graph)
            self._last_task_graph = graph
            self._last_graph_version_id = self._graph_version(graph)
            self._emit(
                "planning.plan_completed",
                {
                    "plan_run_id": self._last_plan_run_id,
                    "graph_version_id": self._last_graph_version_id,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                },
            )
            return graph

        if self.mode == PlanningMode.MCTS_AUGMENTED:
            graph = self._htn_planner.plan_batch(order_batch, self.warehouse_state)
            graph = self._apply_mcts_assignments(graph)
            graph = self._maybe_map_refine_plan(order_batch, graph)
            self._last_task_graph = graph
            self._last_graph_version_id = self._graph_version(graph)
            self._emit(
                "planning.plan_completed",
                {
                    "plan_run_id": self._last_plan_run_id,
                    "graph_version_id": self._last_graph_version_id,
                    "node_count": len(graph.nodes),
                    "edge_count": len(graph.edges),
                },
            )
            return graph

        raise ValueError(f"Unsupported planning mode: {self.mode}")

    def _maybe_map_refine_plan(self, order_batch: OrderBatch, baseline: TaskGraph) -> TaskGraph:
        """Optional MAP refinement; falls back to ``baseline`` on any failure."""
        s = self._settings
        if not s.map_enabled:
            self._emit("planning.map_skipped", {"reason": "disabled"})
            return baseline
        self._map_metrics.map_plan_invocations += 1
        try:
            refined, trace = self._map_orchestrator.plan_refine(
                order_batch=order_batch,
                warehouse_state=self.warehouse_state,
                agent_registry=self.agent_registry,
                baseline_graph=baseline,
            )
        except Exception as exc:  # noqa: BLE001 — deliberate fallback
            self._map_metrics.map_plan_fallbacks += 1
            trace = self._map_orchestrator.last_trace
            if trace is not None:
                trace.raw_errors.append(str(exc))
                trace.fallback_used = True
            self._emit("planning.map_failed", {"reason": "exception", "error": str(exc)})
            return baseline

        if refined is None:
            self._map_metrics.map_plan_fallbacks += 1
            if trace is not None:
                trace.fallback_used = True
            self._emit("planning.map_failed", {"reason": "null_refined_graph"})
            return baseline

        if s.map_plan_shadow:
            self._map_metrics.map_plan_shadow_proposals += 1
            self._emit("planning.map_shadowed", {"reason": "map_plan_shadow"})
            return baseline

        if not s.map_apply_plan:
            self._map_metrics.map_plan_fallbacks += 1
            self._emit("planning.map_failed", {"reason": "map_apply_plan_disabled"})
            return baseline

        err = validate_task_graph(refined)
        if err:
            self._map_metrics.map_plan_fallbacks += 1
            if trace is not None:
                trace.raw_errors.extend(err)
                trace.fallback_used = True
            self._emit("planning.map_failed", {"reason": "validate_task_graph", "error_count": len(err)})
            return baseline

        self._map_metrics.map_plan_successes += 1
        self._emit("planning.map_applied", {"node_count": len(refined.nodes), "edge_count": len(refined.edges)})
        return refined

    def _apply_mcts_assignments(self, graph: TaskGraph) -> TaskGraph:
        """Fill unset ``TaskNode.agent_id`` slots using MCTS over assignment states."""
        agents = self.agent_registry.get_all_agents()
        if not agents:
            self._emit("planning.mcts_skipped", {"reason": "no_agents"})
            return graph

        tasks_by_id: dict[str, TaskNode] = {n.id: n for n in graph.nodes}
        root_state = assignment_state_from_graph(graph.nodes)
        if not root_state.unassigned_tasks:
            self._emit("planning.mcts_skipped", {"reason": "no_unassigned_tasks"})
            return graph

        agent_ids = [a.id for a in agents]

        def can_assign(agent_id: str, task_type: str) -> bool:
            agent = self.agent_registry.get_agent(agent_id)
            return agent.can_perform(task_type)

        domain = AssignmentDomain(tasks_by_id, agent_ids, can_assign)
        mcts = MCTSSearch(domain, n_iterations=128)
        best = mcts.search(root_state)
        self._emit("planning.mcts_search_summary", dict(mcts.last_summary))

        new_nodes = [
            n.model_copy(update={"agent_id": best.task_to_agent.get(n.id, n.agent_id)})
            for n in graph.nodes
        ]
        return TaskGraph(nodes=new_nodes, edges=list(graph.edges))

    def replan(
        self,
        escalation: EscalationSignal,
        *,
        current_graph: TaskGraph | None = None,
    ) -> TaskGraphDelta:
        """Translate ``escalation`` into graph edits.

        When MAP is enabled, pass ``current_graph`` (or call :meth:`plan` first so
        the coordinator retains :attr:`_last_task_graph`) for validated deltas.

        When MAP is disabled, this returns an empty :class:`~apex.planner.graph_delta.TaskGraphDelta`.
        Evaluation code should fall back with a fresh :meth:`plan` call on surviving orders
        (see :mod:`apex.evaluation.episode_driver`).
        """
        baseline = current_graph or self._last_task_graph
        self._emit("replan.started", {"reason": escalation.reason})
        s = self._settings
        if not s.map_enabled or baseline is None:
            self._emit("replan.skipped", {"reason": "map_disabled_or_no_baseline"})
            return TaskGraphDelta()

        self._map_metrics.map_replan_invocations += 1
        try:
            delta, trace = self._map_orchestrator.replan_propose_delta(
                escalation=escalation,
                warehouse_state=self.warehouse_state,
                agent_registry=self.agent_registry,
                current_graph=baseline,
            )
        except Exception as exc:  # noqa: BLE001
            self._map_metrics.map_replan_fallbacks += 1
            lt = self._map_orchestrator.last_trace
            if lt is not None:
                lt.raw_errors.append(str(exc))
                lt.fallback_used = True
            self._emit("replan.delta_rejected", {"reason": "exception", "error": str(exc)})
            return TaskGraphDelta()

        if delta is None:
            self._map_metrics.map_replan_fallbacks += 1
            self._emit("replan.delta_rejected", {"reason": "delta_none"})
            return TaskGraphDelta()

        if s.map_replan_shadow:
            self._map_metrics.map_replan_shadow_proposals += 1
            if trace is not None:
                trace.debug["shadow_delta"] = delta.model_dump()
            self._emit("replan.delta_shadowed", {"reason": "map_replan_shadow"})
            return TaskGraphDelta()

        if not s.map_apply_replan:
            self._map_metrics.map_replan_fallbacks += 1
            self._emit("replan.delta_rejected", {"reason": "map_apply_replan_disabled"})
            return TaskGraphDelta()

        derr = validate_task_graph_delta(baseline, delta)
        if derr:
            self._map_metrics.map_replan_fallbacks += 1
            if trace is not None:
                trace.raw_errors.extend(derr)
                trace.fallback_used = True
            self._emit("replan.delta_rejected", {"reason": "validate_task_graph_delta", "error_count": len(derr)})
            return TaskGraphDelta()

        try:
            merged = apply_task_graph_delta(baseline, delta)
        except ValueError:
            self._map_metrics.map_replan_fallbacks += 1
            if trace is not None:
                trace.fallback_used = True
            self._emit("replan.delta_rejected", {"reason": "apply_task_graph_delta"})
            return TaskGraphDelta()

        err = validate_task_graph(merged)
        if err:
            self._map_metrics.map_replan_fallbacks += 1
            if trace is not None:
                trace.raw_errors.extend(err)
                trace.fallback_used = True
            self._emit("replan.delta_rejected", {"reason": "validate_task_graph", "error_count": len(err)})
            return TaskGraphDelta()

        self._map_metrics.map_replan_successes += 1
        self._emit(
            "replan.delta_applied",
            {"added": len(delta.added), "removed": len(delta.removed), "modified": len(delta.modified)},
        )
        if current_graph is None:
            self._last_task_graph = merged
        return delta


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import Grid

    g = Grid(2, 2, simpy.Environment())
    ws = WarehouseState(
        grid=g,
        shelf_zones=[],
        conveyors=[],
        bays=[],
        pending_orders=[],
        active_orders=[],
    )
    coord = StrategicCoordinator(PlanningMode.HTN_ONLY, ws, AgentRegistry())
    print(repr(coord))
