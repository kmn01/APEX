"""Sorter robot agent for divert and staging near conveyors.

Aligns with abstract STAGE/DISPATCH-style tasks after HTN decomposition and
feeds metrics on throughput at sortation points.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy

from apex.agents.base import Agent, AgentCapabilities, AgentStatus, AgentType


class SorterBot(Agent):
    """Agent stationed on or near conveyor logic for sortation."""

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
            type=AgentType.SORTER,
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
        """SimPy loop: monitor conveyor, execute diverts, stage to bays."""
        raise NotImplementedError("TODO: sorter SimPy loop")

    def can_perform(self, task_type: str) -> bool:
        """Sorters specialize in sort/stage task families."""
        raise NotImplementedError("TODO: map task_type to sorter skills")

    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Short-range repositioning along conveyor adjacency."""
        raise NotImplementedError("TODO: sorter motion near conveyor graph")


if __name__ == "__main__":
    bot = SorterBot("s1", (2, 0))
    print(repr(bot))
