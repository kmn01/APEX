"""MCTS tree nodes over assignment states for strategic planning.

Wraps :class:`AssignmentState` snapshots used by :class:`~apex.planner.mcts.search.MCTSSearch`
when refining task-to-agent pairings after HTN structure is fixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class AssignmentState(BaseModel):
    """Factored state for who does which abstract task."""

    agent_assignments: dict[str, str] = Field(default_factory=dict)
    unassigned_tasks: list[str] = Field(default_factory=list)
    estimated_cost: float = 0.0


@dataclass
class MCTSNode:
    """Node in the assignment MCTS tree."""

    state: AssignmentState
    parent: MCTSNode | None
    children: list[MCTSNode] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0


if __name__ == "__main__":
    st = AssignmentState(agent_assignments={"a1": "t1"}, unassigned_tasks=[], estimated_cost=0.0)
    root = MCTSNode(state=st, parent=None)
    print(repr(root))
