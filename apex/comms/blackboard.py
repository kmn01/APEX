"""Shared blackboard for agent intentions and coarse predictions.

Supports decentralized coordination: agents :meth:`post` intentions; peers
:meth:`read` or :meth:`read_all` for situational awareness without tight
coupling to the tactical executor.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentIntention(BaseModel):
    """Published trajectory and task context for one agent."""

    agent_id: str
    current_task: str | None = None
    next_positions: list[tuple[int, int]] = Field(default_factory=list)
    estimated_completion: float = 0.0


class SharedBlackboard:
    """Process-safe enough store for short-lived intention objects."""

    def __init__(self) -> None:
        self._board: dict[str, AgentIntention] = {}

    def __repr__(self) -> str:
        return f"SharedBlackboard(entries={len(self._board)})"

    def __len__(self) -> int:
        return len(self._board)

    def post(self, intention: AgentIntention) -> None:
        """Upsert ``intention`` keyed by ``agent_id``."""
        self._board[intention.agent_id] = intention

    def read(self, agent_id: str) -> AgentIntention | None:
        """Return the latest intention for ``agent_id``."""
        return self._board.get(agent_id)

    def read_all(self) -> list[AgentIntention]:
        """Snapshot of all intentions."""
        return list(self._board.values())

    def clear_stale(self, cutoff_time: float) -> None:
        """Remove intentions whose ``estimated_completion`` is before ``cutoff_time``."""
        stale = [aid for aid, v in self._board.items() if v.estimated_completion < cutoff_time]
        for aid in stale:
            del self._board[aid]


if __name__ == "__main__":
    bb = SharedBlackboard()
    bb.post(AgentIntention(agent_id="a1", current_task="PICK"))
    print(repr(bb))
