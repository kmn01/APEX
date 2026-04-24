"""Local disruption handling with optional escalation to strategic replanning.

:class:`LocalReplanner` attempts quick patch plans; when impossible it emits an
:class:`EscalationSignal` consumed by :class:`~apex.planner.coordinator.StrategicCoordinator`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

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

    def __init__(self, horizon: float = 50.0, escalation_threshold: int = 3) -> None:
        self.horizon = horizon
        self.escalation_threshold = escalation_threshold  # Escalate if >N conflicts
        self.conflict_count: dict[str, int] = {}

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