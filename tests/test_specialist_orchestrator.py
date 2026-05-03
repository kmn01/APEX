"""MAP orchestrator tests with an injected JSON client (no network)."""

from typing import TypeVar

from pydantic import BaseModel

from apex.agents.registry import AgentRegistry
from apex.config.settings import ApexSettings
from apex.planner.graph_delta import TaskGraphDelta
from apex.planner.htn.operators import TaskType
from apex.planner.htn.planner import TaskGraph, TaskNode
from apex.planner.specialists.models import (
    CoordinationOutput,
    DecompositionOutput,
    MonitoringOutput,
    StatePredictionOutput,
)
from apex.planner.specialists.orchestrator import MapOrchestrator
from apex.simulation.order import Order, OrderBatch, OrderItem, OrderStatus
from apex.tactical.replanner import Disruption, DisruptionType, EscalationSignal

T = TypeVar("T", bound=BaseModel)


class _FakeJsonClient:
    def complete_json(self, system: str, user: str, model_cls: type[T]) -> T:
        if model_cls is DecompositionOutput:
            return DecompositionOutput(subgoals=["fulfill"], method_ranking=[], rationale="d")  # type: ignore[return-value]
        if model_cls is StatePredictionOutput:
            return StatePredictionOutput(task_risk={}, predicted_bottlenecks=[], rationale="p")  # type: ignore[return-value]
        if model_cls is MonitoringOutput:
            return MonitoringOutput(issues=[], severity="low", suggested_remove_task_ids=[], rationale="m")  # type: ignore[return-value]
        if model_cls is CoordinationOutput:
            return CoordinationOutput(delta=TaskGraphDelta(), rationale="c")  # type: ignore[return-value]
        raise AssertionError(f"unexpected model_cls {model_cls}")


def test_plan_refine_empty_delta_returns_valid_graph(warehouse):
    """Empty coordination delta should yield merged graph equal in structure to baseline."""
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    batch = OrderBatch(orders=[order])
    n1 = TaskNode(id="t1", task_type=TaskType.PICK, order_id=order.id)
    n2 = TaskNode(id="t2", task_type=TaskType.TRANSPORT, order_id=order.id)
    baseline = TaskGraph(nodes=[n1, n2], edges=[("t1", "t2")])

    fake = _FakeJsonClient()
    settings = ApexSettings(
        gemini_api_key="fake",
        map_enabled=True,
    )
    orch = MapOrchestrator(settings=settings, gemini_client=fake)
    merged, trace = orch.plan_refine(
        order_batch=batch,
        warehouse_state=warehouse,
        agent_registry=AgentRegistry(),
        baseline_graph=baseline,
    )
    assert merged is not None
    assert len(merged.nodes) == 2
    assert trace.decomposition is not None
    assert trace.coordination is not None


def test_replan_propose_delta_returns_valid_delta(warehouse):
    n1 = TaskNode(id="t1", task_type=TaskType.PICK, order_id="o1")
    current = TaskGraph(nodes=[n1], edges=[])
    esc = EscalationSignal(
        reason="blocked",
        disruption=Disruption(type=DisruptionType.BLOCKED_PATH, agent_id="a1"),
    )
    fake = _FakeJsonClient()
    settings = ApexSettings(gemini_api_key="fake", map_enabled=True)
    orch = MapOrchestrator(settings=settings, gemini_client=fake)
    delta, trace = orch.replan_propose_delta(
        escalation=esc,
        warehouse_state=warehouse,
        agent_registry=AgentRegistry(),
        current_graph=current,
    )
    assert delta is not None
    assert trace.coordination is not None


def test_plan_refine_without_client_returns_none():
    settings = ApexSettings(map_enabled=True, gemini_api_key=None)
    orch = MapOrchestrator(settings=settings, gemini_client=None)
    g = TaskGraph(nodes=[TaskNode(id="a", task_type=TaskType.PICK)], edges=[])
    merged, trace = orch.plan_refine(
        order_batch=OrderBatch(orders=[]),
        warehouse_state=None,  # type: ignore[arg-type]
        agent_registry=AgentRegistry(),
        baseline_graph=g,
    )
    assert merged is None
    assert trace.fallback_used


def test_plan_refine_with_client_requires_warehouse():
    """When an LLM client is present, missing warehouse must not raise."""
    settings = ApexSettings(map_enabled=True, gemini_api_key="fake")
    orch = MapOrchestrator(settings=settings, gemini_client=_FakeJsonClient())
    g = TaskGraph(nodes=[TaskNode(id="a", task_type=TaskType.PICK)], edges=[])
    merged, trace = orch.plan_refine(
        order_batch=OrderBatch(orders=[]),
        warehouse_state=None,  # type: ignore[arg-type]
        agent_registry=AgentRegistry(),
        baseline_graph=g,
    )
    assert merged is None
    assert trace.fallback_used
    assert any("warehouse_state" in err for err in trace.raw_errors)
