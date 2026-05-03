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

from apex.tactical.cbs import CBSPlanner


class TaskInstruction(BaseModel):
    """Single executable directive for one agent."""

    agent_id: str
    action_type: str
    target_pos: tuple[int, int] | None = None
    order_id: str | None = None
    shelf_id: str | None = None
    conveyor_id: str | None = None
    bay_id: str | None = None
    deadline: float = 0.0


class TacticalExecutor:
    """Dispatches :class:`TaskInstruction` records and advances simulation."""

    def __init__(self, env: simpy.Environment, cbs_planner: CBSPlanner | None = None) -> None:
        self.env = env
        self._cbs_planner = cbs_planner
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

    def assign_batch(
        self,
        instructions: list[TaskInstruction],
        *,
        agent_positions: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        """Queue multiple instructions efficiently."""
        if self._cbs_planner is not None and agent_positions is not None:
            instructions = self.plan_move_batch_with_cbs(instructions, agent_positions)
        for instr in instructions:
            self.assign(instr)

    def plan_move_batch_with_cbs(
        self,
        instructions: list[TaskInstruction],
        agent_positions: dict[str, tuple[int, int]],
    ) -> list[TaskInstruction]:
        """Expand simultaneous MOVE_TO instructions into conflict-free waypoint moves."""
        if self._cbs_planner is None:
            return instructions

        move_instrs = [
            instr
            for instr in instructions
            if instr.action_type == "MOVE_TO" and instr.target_pos is not None
        ]
        if len(move_instrs) < 2:
            return instructions

        starts: dict[str, tuple[int, int]] = {}
        goals: dict[str, tuple[int, int]] = {}
        for instr in move_instrs:
            if instr.agent_id not in agent_positions:
                return instructions
            starts[instr.agent_id] = agent_positions[instr.agent_id]
            goals[instr.agent_id] = instr.target_pos  # guarded above

        planned_paths = self._cbs_planner.plan_paths(starts=starts, goals=goals)
        if planned_paths is None:
            return instructions

        expanded: list[TaskInstruction] = []
        for instr in instructions:
            if instr.action_type != "MOVE_TO" or instr.target_pos is None:
                expanded.append(instr)
                continue

            path = planned_paths.get(instr.agent_id)
            if not path or len(path) <= 1:
                expanded.append(instr)
                continue

            for waypoint in path[1:]:
                expanded.append(instr.model_copy(update={"target_pos": waypoint}))
        return expanded

    def peek_next_instruction(self, agent_id: str) -> TaskInstruction | None:
        """Return next queued instruction without removing it (scheduler aid)."""
        queue = self._agent_queues.get(agent_id)
        if queue and len(queue) > 0:
            return queue[0]
        return None

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

    def clear_all_queues(self) -> None:
        """Remove all queued (not-yet-delivered) instructions; keeps completion history."""
        self._agent_queues.clear()


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