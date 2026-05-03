"""MAP-style orchestration: sequential specialist calls with shared context."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from apex.agents.registry import AgentRegistry
from apex.config.settings import ApexSettings, get_settings
from apex.planner.graph_delta import (
    TaskGraphDelta,
    apply_task_graph_delta,
    validate_task_graph,
    validate_task_graph_delta,
)
from apex.planner.htn.planner import TaskGraph
from apex.planner.specialists.gemini_client import GeminiJsonClient
from apex.planner.specialists.interfaces import JsonCompletionClient
from apex.planner.specialists.models import (
    CoordinationOutput,
    DecompositionOutput,
    FleetSummary,
    MonitoringOutput,
    OrderSummary,
    PlanningContext,
    ReplanContext,
    SpecialistTrace,
    StatePredictionOutput,
    WarehouseSummary,
)
from apex.simulation.order import OrderBatch
from apex.simulation.warehouse import WarehouseState
from apex.tactical.replanner import EscalationSignal

if TYPE_CHECKING:
    pass


def _warehouse_summary(ws: WarehouseState) -> WarehouseSummary:
    return WarehouseSummary(
        shelf_zone_ids=[s.id for s in ws.shelf_zones],
        bay_ids=[b.id for b in ws.bays],
        conveyor_count=len(ws.conveyors),
    )


def _fleet_summary(registry: AgentRegistry) -> list[FleetSummary]:
    out: list[FleetSummary] = []
    for a in registry.get_all_agents():
        out.append(FleetSummary(agent_id=a.id, roles=[a.type.value]))
    return out


def _graph_digest(graph: TaskGraph) -> list[dict[str, object]]:
    return [
        {
            "id": n.id,
            "task_type": n.task_type.value if hasattr(n.task_type, "value") else str(n.task_type),
            "order_id": n.order_id,
            "agent_id": n.agent_id,
            "deadline": n.deadline,
            "dependencies": list(n.dependencies),
        }
        for n in graph.nodes
    ]


def _build_planning_context(
    order_batch: OrderBatch,
    warehouse_state: WarehouseState,
    agent_registry: AgentRegistry,
    baseline_graph: TaskGraph,
) -> PlanningContext:
    orders = [
        OrderSummary(
            order_id=o.id,
            priority=o.priority,
            deadline=o.deadline,
            item_count=len(o.items),
            skus=[it.sku for it in o.items],
        )
        for o in order_batch.orders
    ]
    return PlanningContext(
        orders=orders,
        warehouse=_warehouse_summary(warehouse_state),
        fleet=_fleet_summary(agent_registry),
        baseline_graph=baseline_graph,
    )


def _build_replan_context(
    escalation: EscalationSignal,
    warehouse_state: WarehouseState,
    agent_registry: AgentRegistry,
    current_graph: TaskGraph,
) -> ReplanContext:
    return ReplanContext(
        escalation=escalation,
        current_graph=current_graph,
        warehouse=_warehouse_summary(warehouse_state),
        fleet=_fleet_summary(agent_registry),
    )


class MapOrchestrator:
    """Runs decomposition → prediction → monitoring → coordination (MAP-style)."""

    def __init__(
        self,
        *,
        settings: ApexSettings | None = None,
        gemini_client: JsonCompletionClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._injected_client = gemini_client
        self.last_trace: SpecialistTrace | None = None

    def _resolve_client(self) -> JsonCompletionClient | None:
        if self._injected_client is not None:
            return self._injected_client
        if not self._settings.gemini_api_key:
            return None
        return GeminiJsonClient.from_settings(self._settings)

    def plan_refine(
        self,
        *,
        order_batch: OrderBatch,
        warehouse_state: WarehouseState,
        agent_registry: AgentRegistry,
        baseline_graph: TaskGraph,
    ) -> tuple[TaskGraph | None, SpecialistTrace]:
        trace = SpecialistTrace()
        self.last_trace = trace
        client = self._resolve_client()
        if client is None:
            trace.raw_errors.append("MAP: no Gemini client (missing GEMINI_API_KEY or inject client).")
            trace.fallback_used = True
            return None, trace

        ctx = _build_planning_context(
            order_batch, warehouse_state, agent_registry, baseline_graph
        )
        base_json = json.dumps(
            {
                "context": ctx.model_dump(mode="json"),
                "baseline_graph": _graph_digest(baseline_graph),
            },
            indent=2,
        )

        sys_dec = (
            "You are the Decomposition specialist in a warehouse MAP stack. "
            "Output strict JSON matching the schema for DecompositionOutput: "
            "subgoals (strings), method_ranking (strings), rationale (string). "
            "subgoals should reflect high-level steps to fulfill the batch."
        )
        sys_pred = (
            "You are the StatePrediction specialist. Output JSON for StatePredictionOutput: "
            "task_risk (map task_id -> 0..1 float), predicted_bottlenecks, rationale."
        )
        sys_mon = (
            "You are the Monitoring/Critique specialist. Output JSON for MonitoringOutput: "
            "issues (strings), severity (low|medium|high), suggested_remove_task_ids, rationale."
        )
        sys_coord = (
            "You are the Coordination specialist. Output JSON for CoordinationOutput: "
            "delta with keys added (list of TaskNode objects), removed (list of task id strings), "
            "modified (list of TaskNode objects), rationale. "
            "TaskNode fields: id, task_type (PICK|TRANSPORT|STAGE|STORE|DISPATCH), "
            "agent_id (optional), dependencies (string ids), deadline (number), order_id (optional). "
            "Prefer minimal edits to the baseline graph. Use empty delta if no change."
        )

        try:
            dec = client.complete_json(sys_dec, base_json, DecompositionOutput)
            trace.decomposition = dec

            pred_in = base_json + "\n\nDecomposition:\n" + dec.model_dump_json()
            pred = client.complete_json(sys_pred, pred_in, StatePredictionOutput)
            trace.prediction = pred

            mon_in = pred_in + "\n\nPrediction:\n" + pred.model_dump_json()
            mon = client.complete_json(sys_mon, mon_in, MonitoringOutput)
            trace.monitoring = mon

            coord_in = mon_in + "\n\nMonitoring:\n" + mon.model_dump_json()
            coord = client.complete_json(sys_coord, coord_in, CoordinationOutput)
            trace.coordination = coord

            delta = coord.delta
            derr = validate_task_graph_delta(baseline_graph, delta)
            if derr:
                trace.raw_errors.extend(derr)
                trace.fallback_used = True
                return None, trace

            merged = apply_task_graph_delta(baseline_graph, delta)
            verr = validate_task_graph(merged)
            if verr:
                trace.raw_errors.extend(verr)
                trace.fallback_used = True
                return None, trace

            return merged, trace
        except Exception as exc:  # noqa: BLE001
            trace.raw_errors.append(str(exc))
            trace.fallback_used = True
            return None, trace

    def replan_propose_delta(
        self,
        *,
        escalation: EscalationSignal,
        warehouse_state: WarehouseState,
        agent_registry: AgentRegistry,
        current_graph: TaskGraph,
    ) -> tuple[TaskGraphDelta | None, SpecialistTrace]:
        trace = SpecialistTrace()
        self.last_trace = trace
        client = self._resolve_client()
        if client is None:
            trace.raw_errors.append("MAP: no Gemini client (missing GEMINI_API_KEY or inject client).")
            trace.fallback_used = True
            return None, trace

        ctx = _build_replan_context(escalation, warehouse_state, agent_registry, current_graph)
        base_json = json.dumps(
            {
                "context": ctx.model_dump(mode="json"),
                "current_graph": _graph_digest(current_graph),
            },
            indent=2,
        )

        sys_dec = (
            "You are the Decomposition specialist for replanning after a disruption. "
            "Output JSON for DecompositionOutput (subgoals, method_ranking, rationale)."
        )
        sys_pred = (
            "You are the StatePrediction specialist. Output JSON for StatePredictionOutput."
        )
        sys_mon = (
            "You are the Monitoring specialist. Output JSON for MonitoringOutput, including "
            "suggested_remove_task_ids for tasks that should be dropped or redone."
        )
        sys_coord = (
            "You are the Coordination specialist. Output JSON for CoordinationOutput with a "
            "minimal TaskGraphDelta under key delta. Only use valid TaskType values. "
            "Prefer modify over remove/add when possible."
        )

        try:
            dec = client.complete_json(sys_dec, base_json, DecompositionOutput)
            trace.decomposition = dec

            pred_in = base_json + "\n\nDecomposition:\n" + dec.model_dump_json()
            pred = client.complete_json(sys_pred, pred_in, StatePredictionOutput)
            trace.prediction = pred

            mon_in = pred_in + "\n\nPrediction:\n" + pred.model_dump_json()
            mon = client.complete_json(sys_mon, mon_in, MonitoringOutput)
            trace.monitoring = mon

            coord_in = mon_in + "\n\nMonitoring:\n" + mon.model_dump_json()
            coord = client.complete_json(sys_coord, coord_in, CoordinationOutput)
            trace.coordination = coord

            delta = coord.delta
            derr = validate_task_graph_delta(current_graph, delta)
            if derr:
                trace.raw_errors.extend(derr)
                trace.fallback_used = True
                return None, trace

            merged = apply_task_graph_delta(current_graph, delta)
            verr = validate_task_graph(merged)
            if verr:
                trace.raw_errors.extend(verr)
                trace.fallback_used = True
                return None, trace

            return delta, trace
        except Exception as exc:  # noqa: BLE001
            trace.raw_errors.append(str(exc))
            trace.fallback_used = True
            return None, trace
