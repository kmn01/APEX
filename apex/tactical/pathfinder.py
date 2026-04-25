"""Conflict-Based Search (CBS) pathfinding with reservation tables.

Multi-agent pathfinding that respects temporal and spatial conflicts,
producing collision-free paths for heterogeneous agents. The reservation
table tracks occupied cells over time to prevent collisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import heapq


@dataclass(frozen=True)
class Reservation:
    """A space-time reservation: agent cannot occupy pos at time t."""

    agent_id: str
    position: tuple[int, int]
    time: float


class ReservationTable:
    """Tracks space-time occupancy to prevent multi-agent collisions."""

    def __init__(self) -> None:
        # Set of (agent_id, pos, time) reservations
        self._reservations: set[Reservation] = set()
        # Dict: pos -> set of times reserved
        self._spatial_index: dict[tuple[int, int], set[float]] = {}
        # Dict: agent_id -> list of reservations
        self._agent_index: dict[str, list[Reservation]] = {}

    def __repr__(self) -> str:
        return f"ReservationTable(reservations={len(self._reservations)})"

    def reserve(
        self, agent_id: str, position: tuple[int, int], time: float
    ) -> None:
        """Reserve a position at a specific time for an agent."""
        res = Reservation(agent_id, position, time)
        self._reservations.add(res)

        # Update spatial index
        if position not in self._spatial_index:
            self._spatial_index[position] = set()
        self._spatial_index[position].add(time)

        # Update agent index
        if agent_id not in self._agent_index:
            self._agent_index[agent_id] = []
        self._agent_index[agent_id].append(res)

    def clear_agent_reservations(self, agent_id: str) -> None:
        """Clear all reservations for an agent (e.g., after replanning)."""
        if agent_id not in self._agent_index:
            return

        for res in self._agent_index[agent_id]:
            self._reservations.discard(res)
            if res.position in self._spatial_index:
                self._spatial_index[res.position].discard(res.time)

        del self._agent_index[agent_id]

    def is_reserved(self, position: tuple[int, int], time: float) -> bool:
        """Check if a position is reserved at a specific time."""
        if position not in self._spatial_index:
            return False
        return time in self._spatial_index[position]

    def get_reservations_at(self, position: tuple[int, int]) -> set[float]:
        """Get all times at which a position is reserved."""
        return self._spatial_index.get(position, set()).copy()

    def get_agent_path(self, agent_id: str) -> list[tuple[int, int]]:
        """Get the reserved path for an agent (positions only, in order)."""
        if agent_id not in self._agent_index:
            return []

        reservations = sorted(self._agent_index[agent_id], key=lambda r: r.time)
        return [r.position for r in reservations]

    def get_agent_timeline(self, agent_id: str) -> list[tuple[float, tuple[int, int]]]:
        """Get the reserved path for an agent as (time, position) pairs."""
        if agent_id not in self._agent_index:
            return []

        reservations = sorted(self._agent_index[agent_id], key=lambda r: r.time)
        return [(r.time, r.position) for r in reservations]


class SimplePathfinder:
    """A* pathfinder with support for reservation tables."""

    def __init__(self, warehouse_grid: Any) -> None:
        self.grid = warehouse_grid

    def __repr__(self) -> str:
        return f"SimplePathfinder(grid={self.grid.rows}x{self.grid.cols})"

    def manhattan_distance(
        self, pos1: tuple[int, int], pos2: tuple[int, int]
    ) -> float:
        """Heuristic: Manhattan distance."""
        r1, c1 = pos1
        r2, c2 = pos2
        return abs(r1 - r2) + abs(c1 - c2)

    def find_path(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        agent_id: str = "default",
        reservation_table: ReservationTable | None = None,
        max_time: float = 1000.0,
    ) -> list[tuple[int, int]] | None:
        """Find collision-free path using A* with reservation table checks.
        
        Args:
            start: Starting position
            goal: Goal position
            agent_id: For reservation checking
            reservation_table: Optional table to check for conflicts
            max_time: Maximum simulation time allowed (prevents infinite loops)
        
        Returns:
            List of positions from start to goal (inclusive), or None if no path.
        """
        if not self.grid.is_walkable(start) or not self.grid.is_walkable(goal):
            return None

        if start == goal:
            return [start]

        # A* search: (f_score, counter, position, path, current_time)
        counter = 0
        open_set: list[tuple[float, int, tuple[int, int], list, float]] = [
            (0, counter, start, [start], 0.0)
        ]
        closed_set: set[tuple[tuple[int, int], float]] = set()

        while open_set:
            f_score, _, current_pos, path, current_time = heapq.heappop(open_set)

            # Check if we reached the goal
            if current_pos == goal:
                return path

            # Prevent infinite loops
            if current_time > max_time:
                return None

            state = (current_pos, current_time)
            if state in closed_set:
                continue
            closed_set.add(state)

            # Explore neighbors
            for neighbor_pos in self.grid.neighbors(current_pos):
                if not self.grid.is_walkable(neighbor_pos):
                    continue

                # Check reservation table
                next_time = current_time + 1.0
                if reservation_table and reservation_table.is_reserved(
                    neighbor_pos, next_time
                ):
                    continue

                g_score = len(path)  # Cost = number of steps
                h_score = self.manhattan_distance(neighbor_pos, goal)
                f_score_new = g_score + h_score

                new_state = (neighbor_pos, next_time)
                if new_state not in closed_set:
                    counter += 1
                    new_path = path + [neighbor_pos]
                    heapq.heappush(
                        open_set,
                        (f_score_new, counter, neighbor_pos, new_path, next_time),
                    )

        return None  # No path found


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import CellType, Grid

    # Create a small test grid
    env = simpy.Environment()
    grid = Grid(10, 10, env)

    # Add some obstacles
    grid.set_cell((2, 2), CellType.OBSTACLE)
    grid.set_cell((2, 3), CellType.OBSTACLE)
    grid.set_cell((2, 4), CellType.OBSTACLE)

    print("=== Reservation Table ===")
    rt = ReservationTable()
    print(f"Created: {repr(rt)}")
    print()

    # Test basic reservations
    print("=== Testing Reservations ===")
    rt.reserve("agent-1", (1, 1), 0.0)
    rt.reserve("agent-1", (1, 2), 1.0)
    rt.reserve("agent-1", (1, 3), 2.0)
    print(f"Reserved path for agent-1: {rt.get_agent_path('agent-1')}")
    print(f"Timeline for agent-1: {rt.get_agent_timeline('agent-1')}")
    print()

    # Test conflict detection
    print("=== Testing Conflict Detection ===")
    print(f"(1, 1) reserved at time 0.0: {rt.is_reserved((1, 1), 0.0)}")
    print(f"(1, 1) reserved at time 1.0: {rt.is_reserved((1, 1), 1.0)}")
    print(f"(1, 2) reserved at time 1.0: {rt.is_reserved((1, 2), 1.0)}")
    print(f"(1, 5) reserved at time 1.0: {rt.is_reserved((1, 5), 1.0)}")
    print()

    # Test pathfinding
    print("=== Testing Pathfinding ===")
    pf = SimplePathfinder(grid)
    print(f"Created: {repr(pf)}")
    print()

    # Simple path without obstacles
    path1 = pf.find_path((0, 0), (3, 3), agent_id="agent-1", reservation_table=rt)
    print(f"Path from (0,0) to (3,3): {path1}")
    print(f"Path length: {len(path1) if path1 else 'None'}")
    print()

    # Path around obstacles
    path2 = pf.find_path((1, 1), (3, 5), agent_id="agent-2")
    print(f"Path from (1,1) to (3,5) (around obstacles): {path2}")
    print()

    # No path (surrounded)
    grid.set_cell((5, 0), CellType.OBSTACLE)
    grid.set_cell((5, 1), CellType.OBSTACLE)
    grid.set_cell((5, 2), CellType.OBSTACLE)
    path3 = pf.find_path((5, 1), (9, 9), agent_id="agent-3")
    print(f"Path from (5,1) to (9,9) (blocked): {path3}")
    print()

    # Multi-agent conflict avoidance
    print("=== Testing Multi-Agent Conflict Avoidance ===")
    rt2 = ReservationTable()

    # Agent 1 reserves a path
    rt2.reserve("agent-1", (0, 0), 0.0)
    rt2.reserve("agent-1", (0, 1), 1.0)
    rt2.reserve("agent-1", (0, 2), 2.0)
    rt2.reserve("agent-1", (0, 3), 3.0)
    print(f"Agent-1 path: {rt2.get_agent_path('agent-1')}")

    # Agent 2 tries to find a path that doesn't conflict
    path4 = pf.find_path((1, 0), (1, 3), agent_id="agent-2", reservation_table=rt2)
    print(f"Agent-2 path (avoids agent-1): {path4}")
    print()

    # Clear and test
    print("=== Testing Clear ===")
    rt2.clear_agent_reservations("agent-1")
    print(f"After clearing agent-1 reservations: {rt2.get_agent_path('agent-1')}")
    print(f"Total reservations: {len(rt2._reservations)}")