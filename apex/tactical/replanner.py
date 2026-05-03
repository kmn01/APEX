"""Local disruption handling with optional escalation to strategic replanning.

:class:`LocalReplanner` attempts quick patch plans; when impossible it emits an
:class:`EscalationSignal` consumed by :class:`~apex.planner.coordinator.StrategicCoordinator`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from apex.tactical.cbs import CBSPlanner
from apex.tactical.executor import TaskInstruction


class DisruptionType(str, Enum):
    """Categories of runtime exceptions visible to the tactical layer."""

    BLOCKED_PATH = "BLOCKED_PATH"
    FAILED_PICK = "FAILED_PICK"
    NEW_PRIORITY = "NEW_PRIORITY"
    AGENT_FAILURE = "AGENT_FAILURE"


class Disruption(BaseModel):
    """A concrete disruption instance with optional context payload."""

    type: DisruptionType
    agent_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class Resolution(BaseModel):
    """Patch plan expressed as revised tactical instructions."""

    revised_instructions: list[TaskInstruction] = Field(default_factory=list)


class EscalationSignal(BaseModel):
    """Strategic replan request with structured reason."""

    reason: str
    disruption: Disruption


class LocalReplanner:
    """Fast, localized response to :class:`Disruption` events."""

    def __init__(
        self,
        horizon: float = 50.0,
        escalation_threshold: int = 3,
        cbs_planner: CBSPlanner | None = None,
    ) -> None:
        self.horizon = horizon
        self.escalation_threshold = escalation_threshold  # Escalate if >N conflicts
        self.conflict_count: dict[str, int] = {}
        self._cbs_planner = cbs_planner

    def __repr__(self) -> str:
        return f"LocalReplanner(horizon={self.horizon}, threshold={self.escalation_threshold})"

    def handle(
        self,
        disruption: Disruption,
        warehouse_state: Any,
        current_instruction: TaskInstruction | None = None,
    ) -> Resolution | EscalationSignal:
        """Return a local patch or escalate to strategic planning."""
        
        agent_id = disruption.agent_id or "unknown"
        
        if disruption.type == DisruptionType.BLOCKED_PATH:
            # Try to reroute locally
            if agent_id not in self.conflict_count:
                self.conflict_count[agent_id] = 0
            self.conflict_count[agent_id] += 1

            cbs_resolution = self._attempt_cbs_reroute(disruption, agent_id)
            if cbs_resolution is not None:
                return cbs_resolution

            if self.conflict_count[agent_id] > self.escalation_threshold:
                return EscalationSignal(
                    reason=f"Agent {agent_id} blocked path >{ self.escalation_threshold} times",
                    disruption=disruption,
                )

            # Local reroute: create detour instruction
            detour_instr = TaskInstruction(
                agent_id=agent_id,
                action_type="DETOUR",
                target_pos=disruption.context.get("alternate_pos", (0, 0)),
            )
            return Resolution(revised_instructions=[detour_instr])
        
        elif disruption.type == DisruptionType.FAILED_PICK:
            # Retry pick or mark as failed
            retry_instr = TaskInstruction(
                agent_id=agent_id,
                action_type="RETRY_PICK",
                shelf_id=disruption.context.get("shelf_id"),
            )
            return Resolution(revised_instructions=[retry_instr])
        
        elif disruption.type == DisruptionType.AGENT_FAILURE:
            # Always escalate agent failures
            return EscalationSignal(
                reason=f"Agent {agent_id} failed: {disruption.context.get('reason', 'unknown')}",
                disruption=disruption,
            )
        
        else:
            # Default: escalate unknown disruptions
            return EscalationSignal(
                reason=f"Unknown disruption type: {disruption.type}",
                disruption=disruption,
            )

    def _attempt_cbs_reroute(self, disruption: Disruption, agent_id: str) -> Resolution | None:
        """Try CBS reroute when starts/goals are provided in disruption context."""
        if self._cbs_planner is None:
            return None

        starts = disruption.context.get("cbs_starts")
        goals = disruption.context.get("cbs_goals")
        if not isinstance(starts, dict) or not isinstance(goals, dict):
            return None
        if agent_id not in starts or agent_id not in goals:
            return None

        paths = self._cbs_planner.plan_paths(starts=starts, goals=goals)
        if paths is None:
            return None

        agent_path = paths.get(agent_id)
        if not agent_path or len(agent_path) <= 1:
            return None

        revised = [
            TaskInstruction(agent_id=agent_id, action_type="MOVE_TO", target_pos=waypoint)
            for waypoint in agent_path[1:]
        ]
        if not revised:
            return None
        return Resolution(revised_instructions=revised)


if __name__ == "__main__":
    from apex.tactical.executor import TaskInstruction
    
    lr = LocalReplanner()
    print(repr(lr))
    print()
    
    print("=== Test: Blocked Path (Local Resolution) ===")
    disruption1 = Disruption(
        type=DisruptionType.BLOCKED_PATH,
        agent_id="picker-1",
        context={"alternate_pos": (3, 4)},
    )
    result1 = lr.handle(disruption1, None)
    print(f"Result type: {type(result1).__name__}")
    if isinstance(result1, Resolution):
        print(f"Revised instructions: {result1.revised_instructions}")
    print()
    
    print("=== Test: Failed Pick (Local Retry) ===")
    disruption2 = Disruption(
        type=DisruptionType.FAILED_PICK,
        agent_id="picker-1",
        context={"shelf_id": "shelf_a"},
    )
    result2 = lr.handle(disruption2, None)
    print(f"Result type: {type(result2).__name__}")
    if isinstance(result2, Resolution):
        print(f"Revised instructions: {result2.revised_instructions}")
    print()
    
    print("=== Test: Agent Failure (Escalation) ===")
    disruption3 = Disruption(
        type=DisruptionType.AGENT_FAILURE,
        agent_id="picker-2",
        context={"reason": "Battery depleted"},
    )
    result3 = lr.handle(disruption3, None)
    print(f"Result type: {type(result3).__name__}")
    if isinstance(result3, EscalationSignal):
        print(f"Escalation reason: {result3.reason}")