"""HTN planner producing a :class:`TaskGraph` for an order batch.

Consumes :class:`~apex.simulation.order.OrderBatch` and
:class:`~apex.simulation.warehouse.WarehouseState`, applying methods and
operators from sibling modules to emit an acyclic task graph for downstream MCTS
or tactical execution.
"""

from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from apex.common.geometry import manhattan_distance
from apex.planner.htn.methods import BUILT_IN_METHODS
from apex.planner.htn.operators import TaskType
from apex.simulation.order import Order, OrderBatch


class TaskNode(BaseModel):
    """Vertex in the planner task graph."""

    id: str = Field(default_factory=lambda: f"task_{uuid4().hex}")
    task_type: TaskType | str
    agent_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    deadline: float = 0.0
    order_id: str | None = None


class TaskGraph(BaseModel):
    """Dependency graph over :class:`TaskNode` instances."""

    nodes: list[TaskNode] = Field(default_factory=list)
    edges: list[tuple[str, str]] = Field(default_factory=list)

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the graph (without duplicate checking - IDs are unique)."""
        self.nodes.append(node)  # Changed: remove duplicate check since IDs are unique

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge (from -> to)."""
        if (from_id, to_id) not in self.edges:
            self.edges.append((from_id, to_id))

    def get_node(self, node_id: str) -> TaskNode | None:
        """Retrieve a node by ID."""
        return next((n for n in self.nodes if n.id == node_id), None)

class HTNPlanner:
    """Decomposes goals using configured HTN methods and operators."""

    def __init__(self, max_depth: int = 32) -> None:
        self.max_depth = max_depth
        self._depth_counter = 0
        self._applicability_checks: dict[str, Callable[[Order, Any], bool]] = {
            "always_true": self._always_true,
            "order_items_available": self._order_items_available,
            "bay_adjacent_to_pick": self._bay_adjacent_to_pick,
        }

    def __repr__(self) -> str:
        return f"HTNPlanner(max_depth={self.max_depth})"

    def _always_true(self, order: Order, warehouse_state: Any) -> bool:
        return True

    def _order_items_available(self, order: Order, warehouse_state: Any) -> bool:
        if not order.items:
            return False
        if warehouse_state is None or not hasattr(warehouse_state, "shelf_zones"):
            return True
        available_shelves = {shelf.id for shelf in warehouse_state.shelf_zones}
        return all(item.shelf_zone_id in available_shelves for item in order.items)

    def _bay_adjacent_to_pick(self, order: Order, warehouse_state: Any) -> bool:
        if warehouse_state is None:
            return False
        if not getattr(warehouse_state, "bays", None):
            return False
        if not getattr(warehouse_state, "shelf_zones", None):
            return False
        if not order.items:
            return False

        shelf_positions_by_id = {
            shelf.id: shelf.positions for shelf in warehouse_state.shelf_zones
        }
        for item in order.items:
            positions = shelf_positions_by_id.get(item.shelf_zone_id, [])
            for shelf_pos in positions:
                if any(
                    manhattan_distance(shelf_pos, bay.position) <= 1
                    for bay in warehouse_state.bays
                ):
                    return True
        return False

    def _is_method_applicable(self, check_name: str, order: Order, warehouse_state: Any) -> bool:
        check_fn = self._applicability_checks.get(check_name)
        if check_fn is None:
            return False
        return check_fn(order, warehouse_state)

    def _select_method(self, goal_task: str, order: Order, warehouse_state: Any) -> Any | None:
        matching_methods = [m for m in BUILT_IN_METHODS if m.task == goal_task]
        applicable_methods = [
            method
            for method in matching_methods
            if self._is_method_applicable(method.applicability_check_fn, order, warehouse_state)
        ]
        if not applicable_methods:
            return None
        return max(applicable_methods, key=lambda m: (m.priority, m.name))

    def decompose(
        self,
        goal_task: str,
        order: Order,
        warehouse_state: Any,
        depth: int = 0,
    ) -> list[TaskNode]:
        """Expand ``goal_task`` into an ordered list of :class:`TaskNode`.
        
        Recursively applies HTN methods to decompose abstract tasks.
        """
        if depth > self.max_depth:
            return []

        nodes: list[TaskNode] = []

        method = self._select_method(goal_task, order, warehouse_state)
        if method is not None:
            prev_node_id = None
            for subtask_type in method.subtask_types:
                node = TaskNode(
                    task_type=subtask_type,
                    dependencies=[prev_node_id] if prev_node_id else [],
                    deadline=order.deadline if order else 0.0,
                    order_id=order.id if order else None,
                )
                nodes.append(node)
                prev_node_id = node.id
            return nodes

        # If no method matches, create primitive task
        node = TaskNode(
            task_type=goal_task,
            deadline=order.deadline if order else 0.0,
            order_id=order.id if order else None,
        )
        nodes.append(node)
        return nodes

    def plan_batch(
        self,
        order_batch: OrderBatch,
        warehouse_state: Any,
    ) -> TaskGraph:
        """Build a :class:`TaskGraph` covering all orders in ``order_batch``.
        
        Decomposes each order into a chain of tasks, then wires dependencies.
        """
        graph = TaskGraph()

        for order in order_batch.orders:
            # Decompose order into tasks
            task_nodes = self.decompose("fulfill_order", order, warehouse_state)

            # Add nodes to graph
            for node in task_nodes:
                graph.add_node(node)

            # Add edges between nodes (sequential dependency chain)
            for i in range(len(task_nodes) - 1):
                graph.add_edge(task_nodes[i].id, task_nodes[i + 1].id)

        return graph


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import Grid
    from apex.simulation.order import Order, OrderBatch, OrderItem, OrderStatus
    from apex.simulation.warehouse import (
        LoadingBay,
        ShelfZone,
        WarehouseState,
    )

    env = simpy.Environment()
    grid = Grid(20, 20, env)

    # Setup warehouse
    shelf_a = ShelfZone(id="shelf_a", positions=[(5, 5)], capacity=100)
    bay_out = LoadingBay(id="bay_out", position=(15, 15))
    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf_a],
        conveyors=[],
        bays=[bay_out],
        pending_orders=[],
        active_orders=[],
    )

    planner = HTNPlanner()
    print("=== Testing HTNPlanner ===")
    print(repr(planner))
    print()

    print("=== Create Sample Order ===")
    order = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    batch = OrderBatch(orders=[order])
    print(f"Order batch: {batch}")
    print()

    print("=== Decompose Single Order ===")
    nodes = planner.decompose("fulfill_order", order, warehouse)
    for node in nodes:
        print(f"  {node.task_type}: {node.id}")
    print()

    print("=== Plan Batch ===")
    graph = planner.plan_batch(batch, warehouse)
    print(f"Graph nodes: {len(graph.nodes)}")
    for node in graph.nodes:
        print(f"  {node.task_type}: {node.id} (deps: {node.dependencies})")
    print(f"Graph edges: {len(graph.edges)}")
    for edge in graph.edges:
        print(f"  {edge[0]} -> {edge[1]}")