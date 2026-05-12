"""Monte Carlo Tree Search over :class:`~apex.planner.mcts.node.AssignmentState`.

Refines strategic assignments using UCT-style selection; intended to augment HTN
outputs when multiple allocations compete under cost uncertainty.

How to read this file (high-level flow)
---------------------------------------

1. ``search`` builds a tree rooted at the HTN-derived assignment snapshot.

2. Each iteration performs four classic steps:

   - **Select** walk from the root using UCB1 until hitting either a terminal
     state or a node that still has **untried** legal moves (expansion frontier).

   - **Expand** attaches one new child for a move that has not been tried yet.

   - **Rollout** follows random legal moves until all tasks are assigned, then
     scores the completion with ``terminal_reward`` (default: negative static cost).

   - **Backpropagate** adds the simulated reward along the ancestor chain so
     parent statistics reflect accumulated experience.

3. After the budget is spent we return the **best complete assignment**
    discovered (highest rollout reward). If nothing completed, we fall back to
    the root snapshot unchanged.

UCT references: Kocsis & Szepesvári, bandit-based Monte-Carlo planning (2006).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from apex.planner.mcts.domain import AssignmentDomain, default_assignment_cost, terminal_reward_from_cost
from apex.planner.mcts.node import AssignmentState, MCTSNode


class MCTSSearch:
    """Configurable MCTS loop for assignment refinement."""

    def __init__(
        self,
        domain: AssignmentDomain,
        n_iterations: int = 100,
        exploration_weight: float = 1.414,
        rng: random.Random | None = None,
        terminal_reward: Callable[[AssignmentState], float] | None = None,
    ) -> None:
        #: Domain operations (legal moves, transitions, terminal test).
        self._domain = domain
        self.n_iterations = n_iterations
        #: Exploration constant ``c`` in ``mean + c * sqrt(log N / n)``.
        self.exploration_weight = exploration_weight
        self._rng = rng or random.Random()
        if terminal_reward is None:
            self._terminal_reward: Callable[[AssignmentState], float] = (
                lambda s: terminal_reward_from_cost(
                    default_assignment_cost(domain.tasks_by_id, s)
                )
            )
        else:
            self._terminal_reward = terminal_reward

        self._best_reward: float = float("-inf")
        self._best_state: AssignmentState | None = None
        self.last_summary: dict[str, float | int] = {}

    def __repr__(self) -> str:
        return (
            f"MCTSSearch(n_iterations={self.n_iterations}, "
            f"exploration_weight={self.exploration_weight})"
        )

    def search(self, root_state: AssignmentState) -> AssignmentState:
        """Run MCTS from ``root_state`` and return the best-found assignment."""
        self._best_reward = float("-inf")
        self._best_state = None
        rollout_dead_ends = 0
        rollout_count = 0

        root = MCTSNode(state=root_state.model_copy(deep=True), parent=None)

        # Nothing to decide — HTN or a prior pass already fixed every agent slot.
        if self._domain.is_terminal(root.state):
            self.last_summary = {
                "iterations": 0,
                "terminal_at_root": 1,
                "rollout_count": 0,
                "rollout_dead_ends": 0,
            }
            return root.state.model_copy(deep=True)

        # Degenerate: tasks lack any feasible agent under ``can_assign``.
        if not self._domain.legal_moves(root.state):
            self.last_summary = {
                "iterations": 0,
                "terminal_at_root": 0,
                "rollout_count": 0,
                "rollout_dead_ends": 1,
            }
            return root.state.model_copy(deep=True)

        for _ in range(self.n_iterations):
            path_leaf = self._select(root)

            if self._domain.is_terminal(path_leaf.state):
                reward = self._terminal_reward(path_leaf.state)
                self._maybe_track_best(path_leaf.state, reward)
                self._backpropagate(path_leaf, reward)
                continue

            child = self._expand(path_leaf)
            reward, end_state = self._rollout(child)
            rollout_count += 1
            if reward == float("-inf"):
                rollout_dead_ends += 1
            self._maybe_track_best(end_state, reward)
            self._backpropagate(child, reward)

        self.last_summary = {
            "iterations": self.n_iterations,
            "rollout_count": rollout_count,
            "rollout_dead_ends": rollout_dead_ends,
            "best_reward": self._best_reward if self._best_state is not None else float("-inf"),
        }
        if self._best_state is not None:
            return self._best_state.model_copy(deep=True)

        return root.state.model_copy(deep=True)

    def _maybe_track_best(self, terminal_state: AssignmentState, reward: float) -> None:
        """Remember the highest-reward complete assignment seen so far."""
        if reward > self._best_reward:
            self._best_reward = reward
            self._best_state = terminal_state.model_copy(deep=True)

    def _select(self, node: MCTSNode) -> MCTSNode:
        """UCT selection until a leaf or an expandable node.

        Stops at:

        - a terminal state (no further assignments), or
        - an internal node that still has at least one legal child not created yet,
          which becomes the expansion point for this iteration.
        """
        current = node
        while True:
            if self._domain.is_terminal(current.state):
                return current

            if not self._fully_expanded(current):
                return current

            if not current.children:
                # Should not happen when expanded but guard against empty child lists.
                return current

            current = self._best_child_ucb(current)

    def _fully_expanded(self, node: MCTSNode) -> bool:
        """True when every legal move already has a child node."""
        if self._domain.is_terminal(node.state):
            return True
        legal = self._domain.legal_moves(node.state)
        return len(node.children) >= len(legal)

    def _best_child_ucb(self, node: MCTSNode) -> MCTSNode:
        """Pick the child maximizing UCB1 (maximize reward → exploit high mean)."""
        log_n = math.log(max(1, node.visits))
        best_score = float("-inf")
        best_child = node.children[0]

        for child in node.children:
            if child.visits == 0:
                score = float("inf")
            else:
                exploit = child.value / child.visits
                explore = self.exploration_weight * math.sqrt(log_n / child.visits)
                score = exploit + explore

            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Create one child for the first legal move not yet represented."""
        tried = {c.move_from_parent for c in node.children if c.move_from_parent is not None}
        for move in self._domain.legal_moves(node.state):
            if move in tried:
                continue
            child_state = self._domain.apply_move(node.state, move)
            child = MCTSNode(state=child_state, parent=node, move_from_parent=move)
            node.children.append(child)
            return child

        raise RuntimeError("expand called but no untried moves exist")

    def _rollout(self, node: MCTSNode) -> tuple[float, AssignmentState]:
        """Random playout to a terminal state; return reward and final snapshot.

        If we reach a dead-end where tasks remain but no legal agents exist,
        return large negative reward — that trajectory should look unattractive
        to UCB during backpropagation.
        """
        state = node.state.model_copy(deep=True)
        max_steps = len(state.unassigned_tasks) + len(self._domain.tasks_by_id) + 4

        steps = 0
        while not self._domain.is_terminal(state):
            moves = self._domain.legal_moves(state)
            if not moves:
                return float("-inf"), state
            pick = self._rng.choice(moves)
            state = self._domain.apply_move(state, pick)
            steps += 1
            if steps > max_steps:
                return float("-inf"), state

        return self._terminal_reward(state), state

    def _backpropagate(self, node: MCTSNode, value: float) -> None:
        """Propagate ``value`` through ancestors, updating visit counts and totals."""
        cur: MCTSNode | None = node
        while cur is not None:
            cur.visits += 1
            cur.value += value
            cur = cur.parent


if __name__ == "__main__":
    from apex.planner.htn.planner import TaskNode
    from apex.planner.htn.operators import TaskType

    domain = AssignmentDomain(
        tasks_by_id={
            "x": TaskNode(id="x", task_type=TaskType.PICK),
        },
        agent_ids=["alice"],
        can_assign=lambda _a, _t: True,
    )
    m = MCTSSearch(domain, n_iterations=5)
    root_st = AssignmentState(unassigned_tasks=["x"], task_to_agent={})
    print(repr(m))
    print(m.search(root_st))
