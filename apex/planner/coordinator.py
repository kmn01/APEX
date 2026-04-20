"""Strategic coordination across HTN, MCTS, and future MARL modes.

:class:`StrategicCoordinator` owns the high-level planning mode and bridges batch
orders to :class:`~apex.planner.htn.planner.TaskGraph` structures, including
incremental updates after tactical :class:`~apex.tactical.replanner.EscalationSignal`
events.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field

from apex.agents.registry import AgentRegistry
from apex.planner.htn.planner import TaskGraph, TaskNode
from apex.simulation.order import OrderBatch
from apex.simulation.warehouse import WarehouseState
from apex.tactical.replanner import EscalationSignal


class PlanningMode(str, Enum):
    """Which strategic stack is active."""

    HTN_ONLY = "HTN_ONLY"
    MCTS_AUGMENTED = "MCTS_AUGMENTED"
    MARL_POLICY = "MARL_POLICY"


class TaskGraphDelta(BaseModel):
    """Incremental edits to an existing task graph."""

    added: list[TaskNode] = Field(default_factory=list)
    removed: list[TaskNode] = Field(default_factory=list)
    modified: list[TaskNode] = Field(default_factory=list)


class StrategicCoordinator:
    """Facade over HTN/MCTS/MARL for batch planning and replanning."""

    def __init__(
        self,
        mode: PlanningMode,
        warehouse_state: WarehouseState,
        agent_registry: AgentRegistry,
    ) -> None:
        self.mode = mode
        self.warehouse_state = warehouse_state
        self.agent_registry = agent_registry

    def __repr__(self) -> str:
        return (
            f"StrategicCoordinator(mode={self.mode!r}, "
            f"warehouse_state={self.warehouse_state!r}, "
            f"agent_registry={self.agent_registry!r})"
        )

    def plan(self, order_batch: OrderBatch) -> TaskGraph:
        """Produce a fresh :class:`TaskGraph` for ``order_batch``."""
        raise NotImplementedError("TODO: dispatch HTN/MCTS/MARL per mode")

    def replan(self, escalation: EscalationSignal) -> TaskGraphDelta:
        """Translate ``escalation`` into graph edits."""
        raise NotImplementedError("TODO: diff graphs after disruption context")


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
