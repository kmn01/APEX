"""Assignment search domain for MCTS.

This module defines **moves**, **successors**, and **terminal scoring** for the
assignment subtree used by :class:`~apex.planner.mcts.search.MCTSSearch`.

Design (keep the tree search dumb, the domain explicit):

1. A state lists tasks still lacking an agent (``unassigned_tasks``) and maps
   every assigned task to an agent (``task_to_agent``). One agent may appear
   many times — this matches sequential HTN tasks executed by the same robot.

2. A **move** picks one unassigned task and an agent that can perform it
   (registry ``can_perform`` in production; injectable predicate for tests).

3. Rollouts repeatedly sample legal moves until no tasks remain, then score the
   complete assignment with a simple sum of per-task costs (lower is better).
   The search loop converts that to a **reward** (negative cost) so standard
   “maximize Q” UCT applies.

Flow through an iteration (see ``search.py``): select → expand one untried move
→ simulate → backpropagate reward → optionally remember the best complete state.
"""

from __future__ import annotations

from collections.abc import Callable

from apex.planner.htn.planner import TaskNode
from apex.planner.htn.operators import TaskType
from apex.planner.mcts.node import AssignmentState

# Frozen cost table aligned loosely with ``BUILT_IN_OPERATORS`` magnitudes.
_TASK_TYPE_COST: dict[str, float] = {
    TaskType.PICK.value: 2.0,
    TaskType.TRANSPORT.value: 4.0,
    TaskType.STAGE.value: 3.0,
    TaskType.STORE.value: 2.5,
    TaskType.DISPATCH.value: 3.5,
}


def task_type_str(node: TaskNode) -> str:
    """Normalize ``TaskNode.task_type`` (enum or string) to a canonical string."""
    tt = node.task_type
    if isinstance(tt, TaskType):
        return tt.value
    return str(tt)


def default_assignment_cost(tasks_by_id: dict[str, TaskNode], state: AssignmentState) -> float:
    """Sum static per-task costs for all tasks in the plan graph.

    Called only for **terminal** states (every task has an agent). Lower cost is
    better planning quality under this crude surrogate.
    """
    total = 0.0
    for tid in tasks_by_id:
        agent_id = state.task_to_agent.get(tid)
        if agent_id is None:
            return float("inf")
        node = tasks_by_id[tid]
        key = task_type_str(node)
        total += _TASK_TYPE_COST.get(key, 1.0)
    return total


class AssignmentDomain:
    """Feasible (task, agent) moves for partial assignment states."""

    def __init__(
        self,
        tasks_by_id: dict[str, TaskNode],
        agent_ids: list[str],
        can_assign: Callable[[str, str], bool],
    ) -> None:
        #: All tasks being planned (HTN node id → task metadata).
        self.tasks_by_id = tasks_by_id
        #: Agents considered for assignment (sorted for deterministic move ordering).
        self.agent_ids = sorted(agent_ids)
        #: ``can_assign(agent_id, task_type_str) -> bool`` — typically wraps registry.
        self._can_assign = can_assign

    def legal_moves(self, state: AssignmentState) -> list[tuple[str, str]]:
        """Enumerate legal (task_id, agent_id) pairs in deterministic order.

        Tasks are tried in sorted ``unassigned_tasks`` order; agents in sorted
        ``agent_ids``. Only pairs passing ``can_assign`` are returned.
        """
        moves: list[tuple[str, str]] = []
        for task_id in sorted(state.unassigned_tasks):
            node = self.tasks_by_id.get(task_id)
            if node is None:
                continue
            tts = task_type_str(node)
            for agent_id in self.agent_ids:
                if self._can_assign(agent_id, tts):
                    moves.append((task_id, agent_id))
        return moves

    def apply_move(
        self,
        state: AssignmentState,
        move: tuple[str, str],
    ) -> AssignmentState:
        """Return a deep copy of ``state`` after committing one assignment."""
        task_id, agent_id = move
        if task_id not in state.unassigned_tasks:
            raise ValueError(f"task {task_id!r} is not unassigned")

        new_assignments = dict(state.task_to_agent)
        new_assignments[task_id] = agent_id
        new_unassigned = [t for t in state.unassigned_tasks if t != task_id]

        return AssignmentState(
            task_to_agent=new_assignments,
            unassigned_tasks=new_unassigned,
            estimated_cost=state.estimated_cost,
        )

    def is_terminal(self, state: AssignmentState) -> bool:
        """All tasks in ``tasks_by_id`` must be assigned for a terminal state."""
        return len(state.unassigned_tasks) == 0


def assignment_state_from_graph(nodes: list[TaskNode]) -> AssignmentState:
    """Build the MCTS root state from HTN nodes (respects preset ``agent_id``)."""
    task_to_agent: dict[str, str] = {}
    unassigned: list[str] = []
    for n in nodes:
        if n.agent_id is not None:
            task_to_agent[n.id] = n.agent_id
        else:
            unassigned.append(n.id)
    return AssignmentState(
        task_to_agent=task_to_agent,
        unassigned_tasks=sorted(unassigned),
    )


def terminal_reward_from_cost(cost: float) -> float:
    """Planner maximizes reward; costs are minimized via ``reward = -cost``."""
    return -cost
