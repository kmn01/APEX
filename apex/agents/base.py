"""Abstract agent interface for SimPy-driven warehouse robots.

Concrete bots (picker, carrier, sorter) subclass :class:`Agent` and implement
task suitability and motion. The environment and
:class:`~apex.simulation.warehouse.WarehouseState` are always passed explicitly
into processes—there is no global simulation handle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from enum import Enum
from typing import Any

import simpy
from pydantic import BaseModel


class AgentType(str, Enum):
    """Categories of physical agents in the fleet."""

    PICKER = "PICKER"
    CARRIER = "CARRIER"
    SORTER = "SORTER"


class AgentStatus(str, Enum):
    """High-level motion and work state."""

    IDLE = "IDLE"
    MOVING = "MOVING"
    PICKING = "PICKING"
    CARRYING = "CARRYING"
    CHARGING = "CHARGING"
    FAILED = "FAILED"


class AgentCapabilities(BaseModel):
    """Kinematic and payload limits for planning and CBS."""

    max_payload: int = 1
    speed: float = 1.0
    sensor_range: float = 5.0
    battery_capacity: float = 100.0


class Agent(ABC):
    """Behavioral base class for all warehouse agents."""

    def __init__(
        self,
        id: str,
        type: AgentType,
        position: tuple[int, int],
        status: AgentStatus = AgentStatus.IDLE,
        capabilities: AgentCapabilities | None = None,
        assigned_task: str | None = None,
    ) -> None:
        self.id = id
        self.type = type
        self.position = position
        self.status = status
        self.capabilities = capabilities or AgentCapabilities()
        self.assigned_task = assigned_task

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.id!r}, type={self.type!r}, "
            f"position={self.position!r}, status={self.status!r})"
        )

    @abstractmethod
    def run(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Main SimPy process for this agent."""

    @abstractmethod
    def can_perform(self, task_type: str) -> bool:
        """Return True if this agent can execute ``task_type``."""

    @abstractmethod
    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Low-level motion primitive until ``pos`` is reached."""


if __name__ == "__main__":
    # Agent is abstract; exercise capabilities model
    cap = AgentCapabilities(max_payload=3, speed=1.2)
    print(repr(cap))
