"""HTN planner producing a :class:`TaskGraph` for an order batch.

Consumes :class:`~apex.simulation.order.OrderBatch` and
:class:`~apex.simulation.warehouse.WarehouseState`, applying methods and
operators from sibling modules to emit an acyclic task graph for downstream MCTS
or tactical execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apex.planner.htn.methods import BUILT_IN_METHODS, HTNMethod
from apex.planner.htn.operators import TaskType
from apex.simulation.order import Order, OrderBatch


class TaskNode(BaseModel):
    """Vertex in the planner task graph."""

    id: str = Field(default_factory=lambda: f"task_{id(object())}")
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

    def __repr__(self) -> str:
        return f"HTNPlanner(max_depth={self.max_depth})"

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

        # Find matching method for goal_task
        for method in BUILT_IN_METHODS:
            if method.task == goal_task:
                # Create subtasks from method
                prev_node_id = None
                for i, subtask_type in enumerate(method.subtask_types):
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
        ConveyorSegment,
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