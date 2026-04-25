"""Agent fleet registry and queries for tactical coordination.

The :class:`AgentRegistry` maintains a live roster of all agents in the
warehouse, tracks their capabilities, and provides efficient queries for task
assignment and status monitoring.
"""

from __future__ import annotations

from typing import Any

from apex.agents.base import Agent, AgentStatus, AgentType


class AgentRegistry:
    """Central registry for all warehouse agents."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}  # agent_id -> Agent instance

    def __repr__(self) -> str:
        return f"AgentRegistry(agents={len(self._agents)})"

    def register(self, agent: Agent) -> None:
        """Add an agent to the registry."""
        if agent.id in self._agents:
            raise ValueError(f"Agent {agent.id} already registered")
        self._agents[agent.id] = agent
        print(f"Registered {agent.type.value} agent: {agent.id}")

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")
        self._agents.pop(agent_id)
        print(f"Unregistered agent: {agent_id}")

    def get_agent(self, agent_id: str) -> Agent:
        """Get an agent by ID, or raise KeyError."""
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")
        return self._agents[agent_id]

    def get_all_agents(self) -> list[Agent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def get_agents_by_type(self, agent_type: AgentType) -> list[Agent]:
        """Return all agents of a specific type."""
        return [a for a in self._agents.values() if a.type == agent_type]

    def get_agents_by_status(self, status: AgentStatus) -> list[Agent]:
        """Return all agents with a specific status."""
        return [a for a in self._agents.values() if a.status == status]

    def get_idle_agents(self) -> list[Agent]:
        """Return all idle agents (ready for new tasks)."""
        return self.get_agents_by_status(AgentStatus.IDLE)

    def get_available_agents(self) -> list[Agent]:
        """Return agents that are idle AND have battery > 0."""
        return [
            a for a in self.get_idle_agents()
            if a.battery_level > 0 and a.status != AgentStatus.FAILED
        ]

    def get_failed_agents(self) -> list[Agent]:
        """Return all failed agents (out of battery or error)."""
        return self.get_agents_by_status(AgentStatus.FAILED)

    def find_agent_for_task(self, task_type: str) -> Agent | None:
        """Find the best available agent for a task type.
        
        Returns the first idle agent that can perform the task.
        Prioritizes by: battery level (higher is better) -> distance traveled (lower is better).
        """
        candidates = [
            a for a in self.get_available_agents()
            if a.can_perform(task_type)
        ]
        
        if not candidates:
            return None
        
        # Sort by battery (descending) then by distance traveled (ascending)
        candidates.sort(
            key=lambda a: (-a.battery_level, a.total_distance_traveled)
        )
        return candidates[0]

    def find_agents_for_task(
        self, task_type: str, count: int = 1
    ) -> list[Agent]:
        """Find multiple available agents for a task type."""
        candidates = [
            a for a in self.get_available_agents()
            if a.can_perform(task_type)
        ]
        
        # Sort by battery (descending) then by distance traveled (ascending)
        candidates.sort(
            key=lambda a: (-a.battery_level, a.total_distance_traveled)
        )
        
        return candidates[:count]

    def get_pickers(self) -> list[Agent]:
        """Shortcut: get all picker agents."""
        return self.get_agents_by_type(AgentType.PICKER)

    def get_carriers(self) -> list[Agent]:
        """Shortcut: get all carrier agents."""
        return self.get_agents_by_type(AgentType.CARRIER)

    def get_sorters(self) -> list[Agent]:
        """Shortcut: get all sorter agents."""
        return self.get_agents_by_type(AgentType.SORTER)

    def get_fleet_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about the fleet."""
        all_agents = self.get_all_agents()
        
        total_battery = sum(a.battery_level for a in all_agents)
        avg_battery = total_battery / len(all_agents) if all_agents else 0.0
        
        total_distance = sum(a.total_distance_traveled for a in all_agents)
        total_work = sum(a.total_work_done for a in all_agents)
        
        idle_count = len(self.get_idle_agents())
        moving_count = len(self.get_agents_by_status(AgentStatus.MOVING))
        working_count = len(self.get_agents_by_status(AgentStatus.WORKING))
        failed_count = len(self.get_failed_agents())
        
        return {
            "total_agents": len(all_agents),
            "pickers": len(self.get_pickers()),
            "carriers": len(self.get_carriers()),
            "sorters": len(self.get_sorters()),
            "idle_agents": idle_count,
            "moving_agents": moving_count,
            "working_agents": working_count,
            "failed_agents": failed_count,
            "total_battery": total_battery,
            "avg_battery": avg_battery,
            "total_distance_traveled": total_distance,
            "total_work_completed": total_work,
        }

    def print_fleet_status(self) -> None:
        """Print human-readable fleet status."""
        all_agents = self.get_all_agents()
        if not all_agents:
            print("No agents registered")
            return
        
        print("\n" + "=" * 80)
        print("FLEET STATUS")
        print("=" * 80)
        
        for agent in all_agents:
            status_icon = {
                AgentStatus.IDLE: "✓",
                AgentStatus.MOVING: "→",
                AgentStatus.WORKING: "◆",
                AgentStatus.BLOCKED: "✗",
                AgentStatus.FAILED: "☠",
            }.get(agent.status, "?")
            
            print(
                f"{status_icon} {agent.id:12} | {agent.type.value:7} | "
                f"Pos: {agent.position} | Battery: {agent.battery_level:6.1f} | "
                f"Work: {agent.total_work_done:3} | Distance: {agent.total_distance_traveled:6.1f}"
            )
        
        print("=" * 80)
        stats = self.get_fleet_stats()
        print(f"Total: {stats['total_agents']} agents | "
              f"Idle: {stats['idle_agents']} | "
              f"Moving: {stats['moving_agents']} | "
              f"Working: {stats['working_agents']} | "
              f"Failed: {stats['failed_agents']}")
        print(f"Avg Battery: {stats['avg_battery']:.1f} | "
              f"Total Distance: {stats['total_distance_traveled']:.1f} | "
              f"Total Work: {stats['total_work_completed']}")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    from apex.agents.base import AgentCapabilities
    from apex.agents.carrier import CarrierBot
    from apex.agents.picker import PickerBot
    from apex.agents.sorter import SorterBot

    # Create registry
    registry = AgentRegistry()
    print(f"Created: {repr(registry)}\n")

    # Create agents with different capabilities
    picker_caps = AgentCapabilities(
        max_speed=2.0,
        max_payload=10,
        battery_capacity=100.0,
        battery_consumption_rate=0.5,
    )

    carrier_caps = AgentCapabilities(
        max_speed=1.5,
        max_payload=20,
        battery_capacity=150.0,
        battery_consumption_rate=0.4,
    )

    sorter_caps = AgentCapabilities(
        max_speed=0.8,
        max_payload=1,
        battery_capacity=120.0,
        battery_consumption_rate=0.3,
    )

    # Create and register agents
    print("=== Registering Agents ===")
    picker1 = PickerBot("picker-1", (0, 0), capabilities=picker_caps)
    picker2 = PickerBot("picker-2", (1, 1), capabilities=picker_caps)
    carrier1 = CarrierBot("carrier-1", (2, 2), capabilities=carrier_caps)
    carrier2 = CarrierBot("carrier-2", (3, 3), capabilities=carrier_caps)
    sorter1 = SorterBot("sorter-1", (5, 5), capabilities=sorter_caps)

    registry.register(picker1)
    registry.register(picker2)
    registry.register(carrier1)
    registry.register(carrier2)
    registry.register(sorter1)
    print()

    # Query agents
    print("=== Querying Agents ===")
    print(f"Total agents: {len(registry.get_all_agents())}")
    print(f"Pickers: {len(registry.get_pickers())}")
    print(f"Carriers: {len(registry.get_carriers())}")
    print(f"Sorters: {len(registry.get_sorters())}")
    print(f"Idle agents: {len(registry.get_idle_agents())}")
    print()

    # Find agents for tasks
    print("=== Task Assignment ===")
    picker_for_pick = registry.find_agent_for_task("PICK")
    print(f"Best picker for PICK task: {picker_for_pick.id if picker_for_pick else 'None'}")

    carrier_for_transport = registry.find_agent_for_task("TRANSPORT")
    print(f"Best carrier for TRANSPORT task: {carrier_for_transport.id if carrier_for_transport else 'None'}")

    sorter_for_sort = registry.find_agent_for_task("SORT")
    print(f"Best sorter for SORT task: {sorter_for_sort.id if sorter_for_sort else 'None'}")

    no_agent = registry.find_agent_for_task("UNKNOWN_TASK")
    print(f"Agent for UNKNOWN_TASK: {no_agent.id if no_agent else 'None'}")
    print()

    # Simulate work
    print("=== Simulating Work ===")
    picker1.total_work_done = 5
    picker1.total_distance_traveled = 25.5
    picker1.battery_level = 75.0
    picker1.status = AgentStatus.IDLE

    picker2.total_work_done = 8
    picker2.total_distance_traveled = 30.0
    picker2.battery_level = 60.0
    picker2.status = AgentStatus.MOVING

    carrier1.total_work_done = 12
    carrier1.total_distance_traveled = 100.0
    carrier1.battery_level = 120.0
    carrier1.status = AgentStatus.IDLE

    carrier2.total_work_done = 9
    carrier2.total_distance_traveled = 75.0
    carrier2.battery_level = 50.0
    carrier2.status = AgentStatus.FAILED

    sorter1.total_work_done = 20
    sorter1.total_distance_traveled = 5.0
    sorter1.battery_level = 90.0
    sorter1.status = AgentStatus.WORKING

    # Print fleet status
    registry.print_fleet_status()

    # Get stats
    print("=== Fleet Statistics ===")
    stats = registry.get_fleet_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    print()

    # Find multiple agents
    print("=== Finding Multiple Agents ===")
    available_pickers = registry.find_agents_for_task("PICK", count=2)
    print(f"Best 2 pickers: {[a.id for a in available_pickers]}")

    available_carriers = registry.find_agents_for_task("TRANSPORT", count=3)
    print(f"Best 2 carriers (requested 3): {[a.id for a in available_carriers]}")
    print()

    # Test agent lookup
    print("=== Agent Lookup ===")
    try:
        agent = registry.get_agent("picker-1")
        print(f"Found: {agent.id}")
    except KeyError as e:
        print(f"Error: {e}")

    try:
        agent = registry.get_agent("invalid-id")
    except KeyError as e:
        print(f"Error (expected): {e}")