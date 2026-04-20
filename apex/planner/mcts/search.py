"""Monte Carlo Tree Search over :class:`~apex.planner.mcts.node.AssignmentState`.

Refines strategic assignments using UCT-style selection; intended to augment HTN
outputs when multiple allocations compete under cost uncertainty.
"""

from __future__ import annotations

from apex.planner.mcts.node import AssignmentState, MCTSNode


class MCTSSearch:
    """Configurable MCTS loop for assignment refinement."""

    def __init__(self, n_iterations: int = 100, exploration_weight: float = 1.414) -> None:
        self.n_iterations = n_iterations
        self.exploration_weight = exploration_weight

    def __repr__(self) -> str:
        return (
            f"MCTSSearch(n_iterations={self.n_iterations}, "
            f"exploration_weight={self.exploration_weight})"
        )

    def search(self, root_state: AssignmentState) -> AssignmentState:
        """Run MCTS from ``root_state`` and return the best-found assignment."""
        raise NotImplementedError("TODO: build tree, select best child after budget")

    def _select(self, node: MCTSNode) -> MCTSNode:
        """UCT selection until a leaf or unexpanded node."""
        raise NotImplementedError("TODO: UCT walk down the tree")

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Add a child representing a feasible assignment move."""
        raise NotImplementedError("TODO: enumerate legal assignment expansions")

    def _rollout(self, node: MCTSNode) -> float:
        """Playout heuristic from ``node`` to terminal estimate."""
        raise NotImplementedError("TODO: random or heuristic rollout policy")

    def _backpropagate(self, node: MCTSNode, value: float) -> None:
        """Propagate ``value`` up to ancestors."""
        raise NotImplementedError("TODO: update visits and accumulated value")


if __name__ == "__main__":
    s = MCTSSearch()
    print(repr(s))
