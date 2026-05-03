"""Tests for M5 Strategic Planner."""

from __future__ import annotations

import pytest

from apex.agents.base import AgentCapabilities
from apex.agents.carrier import CarrierBot
from apex.agents.picker import PickerBot
from apex.agents.registry import AgentRegistry
from apex.agents.sorter import SorterBot
from apex.config.settings import ApexSettings
from apex.planner.coordinator import PlanningMode, StrategicCoordinator
from apex.planner.graph_delta import TaskGraphDelta
from apex.planner.specialists.metrics import MapReliabilityMetrics
from apex.planner.specialists.models import (
    CoordinationOutput,
    DecompositionOutput,
    MonitoringOutput,
    StatePredictionOutput,
)
from apex.planner.specialists.orchestrator import MapOrchestrator
from apex.planner.htn.planner import HTNPlanner, TaskGraph, TaskNode
from apex.planner.htn.operators import TaskType
from apex.simulation.order import Order, OrderBatch, OrderItem, OrderStatus
from apex.tactical.replanner import Disruption, DisruptionType, EscalationSignal


class _FakeJsonClient:
    """Returns canned specialist outputs for any number of MAP pipeline runs."""

    def complete_json(self, system: str, user: str, model_cls: type):
        if model_cls is DecompositionOutput:
            return DecompositionOutput(subgoals=["g"], method_ranking=[], rationale="d")  # type: ignore[return-value]
        if model_cls is StatePredictionOutput:
            return StatePredictionOutput(task_risk={}, predicted_bottlenecks=[], rationale="p")  # type: ignore[return-value]
        if model_cls is MonitoringOutput:
            return MonitoringOutput(issues=[], severity="low", suggested_remove_task_ids=[], rationale="m")  # type: ignore[return-value]
        if model_cls is CoordinationOutput:
            return CoordinationOutput(delta=TaskGraphDelta(), rationale="c")  # type: ignore[return-value]
        raise AssertionError(f"unexpected model_cls {model_cls}")


def test_htn_planner_creation():
    """Test planner initialization."""
    planner = HTNPlanner()
    assert planner.max_depth == 32


def test_decompose_order():
    """Test order decomposition."""
    planner = HTNPlanner()
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    
    nodes = planner.decompose("fulfill_order", order, None)
    assert len(nodes) > 0
    assert all(isinstance(n, TaskNode) for n in nodes)


def test_plan_single_order(warehouse):
    """Test planning a single order."""
    planner = HTNPlanner()
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    batch = OrderBatch(orders=[order])
    
    graph = planner.plan_batch(batch, warehouse)
    assert len(graph.nodes) > 0
    assert len(graph.edges) == max(0, len(graph.nodes) - 1)


def test_plan_multiple_orders(warehouse):
    """Test planning multiple orders."""
    planner = HTNPlanner()
    orders = [
        Order(
            id=f"ord-{i}",
            items=[OrderItem(sku=f"SKU-{i}", shelf_zone_id="shelf_a", quantity=1)],
            priority=i,
            deadline=100.0 + i*10,
            status=OrderStatus.PENDING,
        )
        for i in range(3)
    ]
    batch = OrderBatch(orders=orders)
    
    graph = planner.plan_batch(batch, warehouse)
    assert len(graph.nodes) >= len(orders)


def test_task_graph_operations():
    """Test TaskGraph add/get operations."""
    graph = TaskGraph()
    
    node1 = TaskNode(task_type=TaskType.PICK, id="node-1")  # Fixed: provide explicit IDs
    node2 = TaskNode(task_type=TaskType.TRANSPORT, id="node-2")
    
    graph.add_node(node1)
    graph.add_node(node2)
    graph.add_edge("node-1", "node-2")
    
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.get_node("node-1") is not None


def test_coordinator_plan_htn_mode(warehouse):
    """Coordinator should delegate planning in HTN_ONLY mode."""
    coordinator = StrategicCoordinator(
        mode=PlanningMode.HTN_ONLY,
        warehouse_state=warehouse,
        agent_registry=AgentRegistry(),
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    graph = coordinator.plan(OrderBatch(orders=[order]))
    assert len(graph.nodes) > 0


def test_coordinator_plan_mcts_augmented_assigns_agents(warehouse):
    """MCTS mode should populate agent slots on HTN tasks when fleet is registered."""
    registry = AgentRegistry()
    caps = AgentCapabilities()
    registry.register(PickerBot("picker-1", (0, 0), capabilities=caps))
    registry.register(CarrierBot("carrier-1", (1, 1), capabilities=caps))
    registry.register(SorterBot("sorter-1", (2, 2), capabilities=caps))

    coordinator = StrategicCoordinator(
        mode=PlanningMode.MCTS_AUGMENTED,
        warehouse_state=warehouse,
        agent_registry=registry,
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    graph = coordinator.plan(OrderBatch(orders=[order]))
    assert len(graph.nodes) >= 1
    assert all(n.agent_id is not None for n in graph.nodes)


def test_coordinator_plan_invalid_mode_raises(warehouse):
    """Unsupported planning modes raise explicitly."""
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    batch = OrderBatch(orders=[order])

    invalid_mode = "INVALID_MODE"
    coordinator = StrategicCoordinator(
        mode=invalid_mode,  # type: ignore[arg-type]
        warehouse_state=warehouse,
        agent_registry=AgentRegistry(),
    )
    with pytest.raises(ValueError):
        coordinator.plan(batch)


def test_task_node_ids_are_unique_by_default():
    """Auto-generated task IDs should be unique."""
    ids = {TaskNode(task_type=TaskType.PICK).id for _ in range(200)}
    assert len(ids) == 200


def test_decompose_selects_direct_bay_method_when_applicable(warehouse_adjacent_bay):
    """When bay is adjacent to pick shelf, direct-bay method should be chosen."""
    planner = HTNPlanner()
    order = Order(
        id="ord-adj",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_adj", quantity=1)],
        priority=1,
        deadline=50.0,
        status=OrderStatus.PENDING,
    )

    nodes = planner.decompose("fulfill_order", order, warehouse_adjacent_bay)
    task_types = [n.task_type for n in nodes]
    assert len(task_types) == 3
    assert TaskType.STAGE not in task_types


def test_map_plan_refine_success_increments_metrics(warehouse):
    settings = ApexSettings(
        gemini_api_key="fake",
        map_enabled=True,
        map_apply_plan=True,
    )
    fake = _FakeJsonClient()
    orch = MapOrchestrator(settings=settings, gemini_client=fake)
    metrics = MapReliabilityMetrics()
    coordinator = StrategicCoordinator(
        PlanningMode.HTN_ONLY,
        warehouse,
        AgentRegistry(),
        settings=settings,
        map_orchestrator=orch,
        map_metrics=metrics,
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    graph = coordinator.plan(OrderBatch(orders=[order]))
    assert len(graph.nodes) >= 1
    assert metrics.map_plan_invocations == 1
    assert metrics.map_plan_successes == 1
    assert metrics.map_plan_fallbacks == 0


def test_map_plan_disabled_no_extra_invocations(warehouse):
    settings = ApexSettings(map_enabled=False)
    metrics = MapReliabilityMetrics()
    coordinator = StrategicCoordinator(
        PlanningMode.HTN_ONLY,
        warehouse,
        AgentRegistry(),
        settings=settings,
        map_metrics=metrics,
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    coordinator.plan(OrderBatch(orders=[order]))
    assert metrics.map_plan_invocations == 0


def test_map_replan_shadow_does_not_return_delta(warehouse):
    settings = ApexSettings(
        gemini_api_key="fake",
        map_enabled=True,
        map_replan_shadow=True,
        map_apply_replan=True,
    )
    fake = _FakeJsonClient()
    orch = MapOrchestrator(settings=settings, gemini_client=fake)
    metrics = MapReliabilityMetrics()
    coordinator = StrategicCoordinator(
        PlanningMode.HTN_ONLY,
        warehouse,
        AgentRegistry(),
        settings=settings,
        map_orchestrator=orch,
        map_metrics=metrics,
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    coordinator.plan(OrderBatch(orders=[order]))
    esc = EscalationSignal(
        reason="test",
        disruption=Disruption(type=DisruptionType.BLOCKED_PATH, agent_id="a1"),
    )
    delta = coordinator.replan(esc)
    assert delta == TaskGraphDelta()
    assert metrics.map_replan_shadow_proposals == 1


def test_map_replan_apply_returns_valid_delta(warehouse):
    settings = ApexSettings(
        gemini_api_key="fake",
        map_enabled=True,
        map_apply_replan=True,
        map_replan_shadow=False,
    )
    fake = _FakeJsonClient()
    orch = MapOrchestrator(settings=settings, gemini_client=fake)
    metrics = MapReliabilityMetrics()
    coordinator = StrategicCoordinator(
        PlanningMode.HTN_ONLY,
        warehouse,
        AgentRegistry(),
        settings=settings,
        map_orchestrator=orch,
        map_metrics=metrics,
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    coordinator.plan(OrderBatch(orders=[order]))
    esc = EscalationSignal(
        reason="test",
        disruption=Disruption(type=DisruptionType.BLOCKED_PATH, agent_id="a1"),
    )
    delta = coordinator.replan(esc)
    assert isinstance(delta, TaskGraphDelta)
    assert metrics.map_replan_successes == 1


def test_pass_k_style_plan_hash_recorded(warehouse):
    import hashlib
    import json

    settings = ApexSettings(map_enabled=False)
    metrics = MapReliabilityMetrics()
    coordinator = StrategicCoordinator(
        PlanningMode.HTN_ONLY,
        warehouse,
        AgentRegistry(),
        settings=settings,
        map_metrics=metrics,
    )
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    g = coordinator.plan(OrderBatch(orders=[order]))
    payload = json.dumps(
        [[n.id, str(n.task_type), n.order_id] for n in sorted(g.nodes, key=lambda x: x.id)],
        sort_keys=True,
    )
    h = hashlib.sha256(payload.encode()).hexdigest()
    metrics.record_plan_run_hash(h)
    assert len(metrics.plan_run_hashes) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])