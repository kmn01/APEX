"""Base agent abstraction and shared agent types.

All agents (picker, carrier, sorter) inherit from :class:`Agent` and implement
a SimPy process coroutine :meth:`Agent.run`. Agents are stateful and track
position, status, capabilities, and assigned tasks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from enum import Enum
from typing import Any

import simpy
from pydantic import BaseModel


class AgentType(str, Enum):
    """Different robot types in the warehouse."""

    PICKER = "PICKER"
    CARRIER = "CARRIER"
    SORTER = "SORTER"


class AgentStatus(str, Enum):
    """State of an agent during simulation."""

    IDLE = "IDLE"
    MOVING = "MOVING"
    WORKING = "WORKING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class AgentCapabilities(BaseModel):
    """Define what an agent can do."""

    max_speed: float = 1.0  # cells per time unit
    max_payload: int = 1  # items it can carry
    sensor_range: float = 5.0  # how far it can "see"
    battery_capacity: float = 100.0  # energy available
    battery_consumption_rate: float = 0.1  # energy used per time unit


class Agent(ABC):
    """Abstract base class for all warehouse agents."""

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
        self.current_payload = 0  # items currently carrying
        self.battery_level = self.capabilities.battery_capacity
        self.total_distance_traveled = 0.0
        self.total_work_done = 0  # item picks/transports completed

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id={self.id!r}, type={self.type!r}, "
            f"position={self.position}, status={self.status!r})"
        )

    @abstractmethod
    def run(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """SimPy process coroutine: agent's main loop.
        
        Must be a generator that yields SimPy events.
        Implementations should handle task assignment, movement, and actions.
        """
        raise NotImplementedError("Subclasses must implement run()")

    @abstractmethod
    def can_perform(self, task_type: str) -> bool:
        """Return True if this agent can perform the given task type."""
        raise NotImplementedError("Subclasses must implement can_perform()")

    @abstractmethod
    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """SimPy process: move the agent from current position to pos.
        
        Should yield time-consuming events (e.g., timeout for travel time).
        Updates self.position and battery_level.
        """
        raise NotImplementedError("Subclasses must implement _move_to()")

    def manhattan_distance(self, other_pos: tuple[int, int]) -> float:
        """Calculate Manhattan distance from current position to other_pos."""
        r1, c1 = self.position
        r2, c2 = other_pos
        return abs(r1 - r2) + abs(c1 - c2)

    def euclidean_distance(self, other_pos: tuple[int, int]) -> float:
        """Calculate Euclidean distance from current position to other_pos."""
        r1, c1 = self.position
        r2, c2 = other_pos
        return ((r1 - r2) ** 2 + (c1 - c2) ** 2) ** 0.5

    def consume_battery(self, amount: float) -> None:
        """Consume battery and check if agent is still operational."""
        self.battery_level -= amount
        if self.battery_level < 0:
            self.battery_level = 0
            self.status = AgentStatus.FAILED

    def recharge_battery(self, amount: float) -> None:
        """Recharge battery up to max capacity."""
        self.battery_level = min(
            self.battery_level + amount,
            self.capabilities.battery_capacity,
        )

    def add_to_payload(self, quantity: int) -> bool:
        """Try to add items to payload. Return True if successful."""
        if self.current_payload + quantity <= self.capabilities.max_payload:
            self.current_payload += quantity
            return True
        return False

    def remove_from_payload(self, quantity: int) -> bool:
        """Try to remove items from payload. Return True if successful."""
        if self.current_payload >= quantity:
            self.current_payload -= quantity
            return True
        return False


if __name__ == "__main__":
    # Smoke test: create agent instances (can't call run() yet, it's abstract)
    
    caps = AgentCapabilities(
        max_speed=2.0,
        max_payload=5,
        sensor_range=10.0,
        battery_capacity=200.0,
    )
    
    print("=== Agent Capabilities ===")
    print(f"Capabilities: {repr(caps)}")
    print()
    
    print("=== Agent Enums ===")
    print(f"Agent types: {[t.value for t in AgentType]}")
    print(f"Agent statuses: {[s.value for s in AgentStatus]}")
    print()
    
    # Test distance calculations with a mock agent
    class MockAgent(Agent):
        def run(self, env, warehouse_state):
            yield env.timeout(0)
        
        def can_perform(self, task_type: str) -> bool:
            return True
        
        def _move_to(self, pos, env, warehouse_state):
            yield env.timeout(0)
    
    agent = MockAgent(
        id="test-1",
        type=AgentType.PICKER,
        position=(0, 0),
        capabilities=caps,
    )
    
    print("=== Agent Instance ===")
    print(f"Agent: {repr(agent)}")
    print(f"Position: {agent.position}")
    print(f"Status: {agent.status}")
    print(f"Battery: {agent.battery_level}/{agent.capabilities.battery_capacity}")
    print(f"Payload: {agent.current_payload}/{agent.capabilities.max_payload}")
    print()
    
    print("=== Distance Calculations ===")
    print(f"Manhattan distance to (3, 4): {agent.manhattan_distance((3, 4))}")
    print(f"Euclidean distance to (3, 4): {agent.euclidean_distance((3, 4)):.2f}")
    print()
    
    print("=== Battery Operations ===")
    print(f"Initial battery: {agent.battery_level}")
    agent.consume_battery(50)
    print(f"After consuming 50: {agent.battery_level}")
    agent.recharge_battery(30)
    print(f"After recharging 30: {agent.battery_level}")
    print()
    
    print("=== Payload Operations ===")
    print(f"Initial payload: {agent.current_payload}/{agent.capabilities.max_payload}")
    success = agent.add_to_payload(3)
    print(f"Add 3 items: {success}, Payload now: {agent.current_payload}")
    success = agent.add_to_payload(3)
    print(f"Add 3 more items: {success}, Payload now: {agent.current_payload}")
    success = agent.remove_from_payload(2)
    print(f"Remove 2 items: {success}, Payload now: {agent.current_payload}")