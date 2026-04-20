"""HTN planner producing a :class:`TaskGraph` for an order batch.

Consumes :class:`~apex.simulation.order.OrderBatch` and
:class:`~apex.simulation.warehouse.WarehouseState`, applying methods and
operators from sibling modules to emit an acyclic task graph for downstream MCTS
or tactical execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apex.planner.htn.operators import TaskType
from apex.simulation.order import OrderBatch


class TaskNode(BaseModel):
    """Vertex in the planner task graph."""

    task_type: TaskType | str
    agent_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    deadline: float = 0.0


class TaskGraph(BaseModel):
    """Dependency graph over :class:`TaskNode` instances."""

    nodes: list[TaskNode] = Field(default_factory=list)
    edges: list[tuple[str, str]] = Field(default_factory=list)


class HTNPlanner:
    """Decomposes goals using configured HTN methods and operators."""

    def __init__(self, max_depth: int = 32) -> None:
        self.max_depth = max_depth

    def __repr__(self) -> str:
        return f"HTNPlanner(max_depth={self.max_depth})"

    def decompose(self, goal_task: str, warehouse_state: Any) -> list[TaskNode]:
        """Expand ``goal_task`` into an ordered list of :class:`TaskNode`."""
        raise NotImplementedError("TODO: HTN recursion using BUILT_IN_METHODS")

    def plan_batch(self, order_batch: OrderBatch, warehouse_state: Any) -> TaskGraph:
        """Build a :class:`TaskGraph` covering all orders in ``order_batch``."""
        raise NotImplementedError("TODO: batch decomposition + dependency wiring")


if __name__ == "__main__":
    g = TaskGraph(nodes=[TaskNode(task_type=TaskType.PICK, agent_id=None)], edges=[])
    print(repr(g))
