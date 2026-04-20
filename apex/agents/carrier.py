"""Carrier robot agent for totes and pallets across the floor.

Bridges shelf zones, conveyors, and bays under tactical instructions issued by
the CBS-backed executor.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy

from apex.agents.base import Agent, AgentCapabilities, AgentStatus, AgentType


class CarrierBot(Agent):
    """Higher-payload agent for transport legs."""

    def __init__(
        self,
        id: str,
        position: tuple[int, int],
        status: AgentStatus = AgentStatus.IDLE,
        capabilities: AgentCapabilities | None = None,
        assigned_task: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
            type=AgentType.CARRIER,
            position=position,
            status=status,
            capabilities=capabilities,
            assigned_task=assigned_task,
        )

    def run(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """SimPy loop: load, follow path, unload at destination."""
        raise NotImplementedError("TODO: carrier transport SimPy loop")

    def can_perform(self, task_type: str) -> bool:
        """Carriers accept transport-heavy abstract tasks."""
        raise NotImplementedError("TODO: map task_type to carrier skills")

    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Move while honoring payload and dynamic obstacles."""
        raise NotImplementedError("TODO: carrier motion with reservations")


if __name__ == "__main__":
    bot = CarrierBot("c1", (1, 1))
    print(repr(bot))
