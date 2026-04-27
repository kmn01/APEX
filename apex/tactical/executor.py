"""Tactical execution: assign concrete instructions and drive agent loops.

Bridges planner output to SimPy processes, tracking per-agent action labels for
debugging and visualization. Uses explicit ``env`` and
:class:`~apex.simulation.warehouse.WarehouseState` references.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Generator
from typing import Any

import simpy
from pydantic import BaseModel


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
        self._agent_queues: dict[str, deque[TaskInstruction]] = defaultdict(deque)
        self._completed_instructions: list[TaskInstruction] = []

    def __repr__(self) -> str:
        queued_total = sum(len(queue) for queue in self._agent_queues.values())
        active_agents = sum(1 for queue in self._agent_queues.values() if queue)
        return (
            "TacticalExecutor("
            f"env={self.env!r}, queued={queued_total}, active_agents={active_agents}"
            ")"
        )

    def assign(self, instruction: TaskInstruction) -> None:
        """Queue instruction for the named agent."""
        self._agent_queues[instruction.agent_id].append(instruction)
        self._agent_actions[instruction.agent_id] = f"QUEUED: {instruction.action_type}"

    def assign_batch(self, instructions: list[TaskInstruction]) -> None:
        """Queue multiple instructions efficiently."""
        for instr in instructions:
            self.assign(instr)

    def get_next_instruction(self, agent_id: str) -> TaskInstruction | None:
        """Retrieve next instruction for an agent, or None if queue empty."""
        queue = self._agent_queues.get(agent_id, deque())
        if queue:
            return queue.popleft()
        return None

    def mark_completed(self, instruction: TaskInstruction) -> None:
        """Record instruction as completed for metrics."""
        self._completed_instructions.append(instruction)

    def run(self, warehouse_state: Any) -> Generator[simpy.Event, None, None]:
        """SimPy loop pulling queued work until shutdown."""
        while True:
            # Check all agent queues for work
            for agent_id, queue in self._agent_queues.items():
                if queue:
                    instr = queue[0]  # Peek (don't remove yet, agent does)
                    self._agent_actions[agent_id] = f"EXECUTING: {instr.action_type}"
            
            yield self.env.timeout(0.1)  # Poll frequency

    def set_agent_action(self, agent_id: str, label: str) -> None:
        """Update the debug label returned by :meth:`get_agent_actions` (e.g. SimPy drivers)."""
        self._agent_actions[agent_id] = label

    def get_agent_actions(self) -> dict[str, str]:
        """Latest action label per agent for telemetry."""
        return dict(self._agent_actions)

    def get_completed_count(self) -> int:
        """Total instructions completed."""
        return len(self._completed_instructions)


if __name__ == "__main__":
    import simpy

    env = simpy.Environment()
    ex = TacticalExecutor(env)
    print(repr(ex))
    
    # Create sample instructions
    instr1 = TaskInstruction(
        agent_id="picker-1",
        action_type="MOVE_TO",
        target_pos=(5, 5),
    )
    instr2 = TaskInstruction(
        agent_id="picker-1",
        action_type="PICK",
        shelf_id="shelf_a",
    )
    
    print("\n=== Assigning Instructions ===")
    ex.assign(instr1)
    ex.assign(instr2)
    print(f"Agent actions: {ex.get_agent_actions()}")
    
    print("\n=== Retrieving Instructions ===")
    next_instr = ex.get_next_instruction("picker-1")
    print(f"Next instruction: {next_instr}")
    
    print("\n=== Marking Completed ===")
    ex.mark_completed(instr1)
    print(f"Completed count: {ex.get_completed_count()}")