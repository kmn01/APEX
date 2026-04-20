"""Central registry of active agents for planners and coordination.

The strategic coordinator and tactical executor query this registry for idle
capacity, spatial proximity, and fleet-wide status summaries.
"""

from __future__ import annotations

import math
from typing import Any

from apex.agents.base import Agent, AgentStatus, AgentType


class AgentRegistry:
    """In-memory fleet index with simple spatial queries."""

    def __init__(self, agents: list[Agent] | None = None) -> None:
        self._agents: list[Agent] = agents if agents is not None else []

    def __repr__(self) -> str:
        return f"AgentRegistry(n_agents={len(self._agents)})"

    def __len__(self) -> int:
        return len(self._agents)

    def register(self, agent: Agent) -> None:
        """Add ``agent`` to the fleet if not already present."""
        if agent not in self._agents:
            self._agents.append(agent)

    def get_idle_agents(self) -> list[Agent]:
        """Return agents whose status is :attr:`~apex.agents.base.AgentStatus.IDLE`."""
        return [a for a in self._agents if a.status == AgentStatus.IDLE]

    def get_by_type(self, agent_type: AgentType) -> list[Agent]:
        """Return agents matching ``agent_type``."""
        return [a for a in self._agents if a.type == agent_type]

    def get_agents_near(self, pos: tuple[int, int], radius: float) -> list[Agent]:
        """Agents within Chebyshev or Euclidean ``radius`` of ``pos``."""
        row, col = pos
        out: list[Agent] = []
        for a in self._agents:
            ar, ac = a.position
            if math.hypot(ar - row, ac - col) <= radius:
                out.append(a)
        return out

    def fleet_status(self) -> dict[str, Any]:
        """Aggregate counts by type and status for dashboards."""
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for a in self._agents:
            by_status[a.status.value] = by_status.get(a.status.value, 0) + 1
            by_type[a.type.value] = by_type.get(a.type.value, 0) + 1
        return {"by_status": by_status, "by_type": by_type, "total": len(self._agents)}


if __name__ == "__main__":
    from apex.agents.picker import PickerBot

    reg = AgentRegistry()
    reg.register(PickerBot("p1", (0, 0)))
    print(repr(reg))
