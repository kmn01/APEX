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

    def __init__(self, horizon: float = 50.0) -> None:
        self.horizon = horizon

    def __repr__(self) -> str:
        return f"LocalReplanner(horizon={self.horizon})"

    def handle(
        self,
        disruption: Disruption,
        warehouse_state: Any,
    ) -> Resolution | EscalationSignal:
        """Return a local patch or escalate to strategic planning."""
        raise NotImplementedError("TODO: CBS/local heuristic vs escalation policy")


if __name__ == "__main__":
    lr = LocalReplanner()
    print(repr(lr))
