"""Tests for M5 Strategic Planner."""

import pytest
import simpy

from apex.planner.htn.planner import HTNPlanner, TaskGraph, TaskNode
from apex.planner.htn.operators import TaskType
from apex.simulation.grid import Grid
from apex.simulation.order import Order, OrderBatch, OrderItem, OrderStatus
from apex.simulation.warehouse import LoadingBay, ShelfZone, WarehouseState


@pytest.fixture
def warehouse():
    """Create test warehouse."""
    env = simpy.Environment()
    grid = Grid(20, 20, env)
    shelf = ShelfZone(id="shelf_a", positions=[(5, 5)], capacity=100)
    bay = LoadingBay(id="bay_out", position=(15, 15))
    
    return WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[bay],
        pending_orders=[],
        active_orders=[],
    )


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
    assert len(graph.edges) >= 0


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])