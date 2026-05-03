"""MCTS tree nodes over assignment states for strategic planning.

Wraps :class:`AssignmentState` snapshots used by :class:`~apex.planner.mcts.search.MCTSSearch`
when refining task-to-agent pairings after HTN structure is fixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class AssignmentState(BaseModel):
    """Factored state for which agent executes each abstract task.

    ``task_to_agent`` maps each assigned HTN task node id to an agent id. Multiple
    tasks may share the same agent (sequential responsibilities). Unassigned work
    lives in ``unassigned_tasks`` until MCTS or heuristics commit an agent.
    """

    task_to_agent: dict[str, str] = Field(default_factory=dict)
    unassigned_tasks: list[str] = Field(default_factory=list)
    estimated_cost: float = 0.0


@dataclass
class MCTSNode:
    """Node in the assignment MCTS tree."""

    state: AssignmentState
    parent: MCTSNode | None
    #: Move from parent to this node: (task_id, agent_id); root has ``None``.
    move_from_parent: tuple[str, str] | None = None
    children: list[MCTSNode] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0


if __name__ == "__main__":
    st = AssignmentState(
        task_to_agent={"t1": "a1"},
        unassigned_tasks=[],
        estimated_cost=0.0,
    )
    root = MCTSNode(state=st, parent=None)
    print(repr(root))
