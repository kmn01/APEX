"""Tactical execution: assign concrete instructions and drive agent loops.

Bridges planner output to SimPy processes, tracking per-agent action labels for
debugging and visualization. Uses explicit ``env`` and
:class:`~apex.simulation.warehouse.WarehouseState` references.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy
from pydantic import BaseModel, Field


class TaskInstruction(BaseModel):
    """Single executable directive for one agent."""

    agent_id: str
    action_type: str
    target_pos: tuple[int, int] | None = None
    shelf_id: str | None = None
    bay_id: str | None = None
    deadline: float = 0.0


class TacticalExecutor:
    """Dispatches :class:`TaskInstruction` records and advances simulation."""

    def __init__(self, env: simpy.Environment) -> None:
        self.env = env
        self._agent_actions: dict[str, str] = {}

    def __repr__(self) -> str:
        return f"TacticalExecutor(env={self.env!r})"

    def assign(self, instruction: TaskInstruction) -> None:
        """Queue or immediately apply ``instruction`` to the named agent."""
        raise NotImplementedError("TODO: route instruction to agent process")

    def run(self, warehouse_state: Any) -> Generator[simpy.Event, None, None]:
        """SimPy loop pulling queued work until shutdown."""
        raise NotImplementedError("TODO: poll instruction queue and step agents")

    def get_agent_actions(self) -> dict[str, str]:
        """Latest action label per agent for telemetry."""
        return dict(self._agent_actions)


if __name__ == "__main__":
    ex = TacticalExecutor(simpy.Environment())
    print(repr(ex))
