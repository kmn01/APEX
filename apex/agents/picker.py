"""Picker robot agent specialized for shelf-facing retrieval.

Implements the :class:`~apex.agents.base.Agent` contract for pick tasks in the
tactical executor and registers with the fleet
:class:`~apex.agents.registry.AgentRegistry`.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy

from apex.agents.base import Agent, AgentCapabilities, AgentStatus, AgentType


class PickerBot(Agent):
    """Agent that travels to shelves and performs picks."""

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
            type=AgentType.PICKER,
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
        """SimPy loop: accept tasks, move, pick, signal completion."""
        raise NotImplementedError("TODO: picker SimPy behavior loop")

    def can_perform(self, task_type: str) -> bool:
        """Pickers handle shelf-facing work types."""
        raise NotImplementedError("TODO: map task_type strings to picker skills")

    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Navigate using grid walkability and reservations."""
        raise NotImplementedError("TODO: grid motion with conflict avoidance")


if __name__ == "__main__":
    bot = PickerBot("p1", (0, 0))
    print(repr(bot))
