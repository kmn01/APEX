"""Canonical Conflict-Based Search (CBS) for multi-agent grid routing.

This module implements a high-level constraint tree (CT) search and uses
constrained single-agent A* as the low-level planner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from itertools import combinations
from typing import Any

from apex.tactical.pathfinder import SimplePathfinder

Pos = tuple[int, int]
VertexConstraint = tuple[Pos, int]
EdgeConstraint = tuple[Pos, Pos, int]


@dataclass(frozen=True)
class CBSConstraint:
    """Constraint that applies to one agent at one timestep."""

    agent_id: str
    time: int
    position: Pos | None = None
    edge_from: Pos | None = None
    edge_to: Pos | None = None

    def as_vertex(self) -> VertexConstraint | None:
        if self.position is None:
            return None
        return (self.position, self.time)

    def as_edge(self) -> EdgeConstraint | None:
        if self.edge_from is None or self.edge_to is None:
            return None
        return (self.edge_from, self.edge_to, self.time)


@dataclass(frozen=True)
class CBSConflict:
    """First collision found in a candidate multi-agent schedule."""

    kind: str  # "vertex" or "edge"
    agent_a: str
    agent_b: str
    time: int
    position: Pos | None = None
    edge_a: tuple[Pos, Pos] | None = None
    edge_b: tuple[Pos, Pos] | None = None


@dataclass
class CBSNode:
    """Constraint tree node."""

    constraints: dict[str, set[CBSConstraint]] = field(default_factory=dict)
    paths: dict[str, list[Pos]] = field(default_factory=dict)
    cost: int = 0


class CBSPlanner:
    """Conflict-Based Search planner with sum-of-cost objective."""

    def __init__(
        self,
        warehouse_grid: Any,
        *,
        max_horizon: int = 256,
        max_node_expansions: int = 2000,
    ) -> None:
        self.grid = warehouse_grid
        self.max_horizon = max_horizon
        self.max_node_expansions = max_node_expansions
        self._low_level = SimplePathfinder(warehouse_grid)

    def plan_paths(
        self,
        starts: dict[str, Pos],
        goals: dict[str, Pos],
    ) -> dict[str, list[Pos]] | None:
        """Return conflict-free per-agent paths, or None when unsat."""
        if set(starts) != set(goals):
            raise ValueError("starts/goals must contain the same agent ids")

        root_paths: dict[str, list[Pos]] = {}
        root_constraints = {agent_id: set() for agent_id in starts}
        for agent_id in sorted(starts):
            path = self._plan_agent(
                agent_id=agent_id,
                start=starts[agent_id],
                goal=goals[agent_id],
                constraints=root_constraints[agent_id],
            )
            if path is None:
                return None
            root_paths[agent_id] = path

        root = CBSNode(
            constraints=root_constraints,
            paths=root_paths,
            cost=self._sum_of_costs(root_paths),
        )
        open_set: list[tuple[int, int, CBSNode]] = []
        counter = 0
        heapq.heappush(open_set, (root.cost, counter, root))

        expansions = 0
        while open_set and expansions < self.max_node_expansions:
            _, _, node = heapq.heappop(open_set)
            expansions += 1

            conflict = self._first_conflict(node.paths)
            if conflict is None:
                return node.paths

            for agent_id in (conflict.agent_a, conflict.agent_b):
                child_constraints = {
                    aid: set(constraints) for aid, constraints in node.constraints.items()
                }
                child_paths = {aid: list(path) for aid, path in node.paths.items()}
                child_constraints.setdefault(agent_id, set()).add(
                    self._constraint_from_conflict(conflict, agent_id)
                )

                replanned = self._plan_agent(
                    agent_id=agent_id,
                    start=starts[agent_id],
                    goal=goals[agent_id],
                    constraints=child_constraints[agent_id],
                )
                if replanned is None:
                    continue

                child_paths[agent_id] = replanned
                child = CBSNode(
                    constraints=child_constraints,
                    paths=child_paths,
                    cost=self._sum_of_costs(child_paths),
                )
                counter += 1
                heapq.heappush(open_set, (child.cost, counter, child))

        return None

    def _plan_agent(
        self,
        *,
        agent_id: str,
        start: Pos,
        goal: Pos,
        constraints: set[CBSConstraint],
    ) -> list[Pos] | None:
        vertex_constraints: set[VertexConstraint] = set()
        edge_constraints: set[EdgeConstraint] = set()
        for c in constraints:
            if c.agent_id != agent_id:
                continue
            v = c.as_vertex()
            if v is not None:
                vertex_constraints.add(v)
            e = c.as_edge()
            if e is not None:
                edge_constraints.add(e)

        return self._low_level.find_path_with_constraints(
            start=start,
            goal=goal,
            vertex_constraints=vertex_constraints,
            edge_constraints=edge_constraints,
            max_time=self.max_horizon,
        )

    def _sum_of_costs(self, paths: dict[str, list[Pos]]) -> int:
        return sum(max(0, len(path) - 1) for path in paths.values())

    def _first_conflict(self, paths: dict[str, list[Pos]]) -> CBSConflict | None:
        if not paths:
            return None

        agents = sorted(paths)
        max_t = max(len(path) for path in paths.values()) - 1

        for t in range(max_t + 1):
            for agent_a, agent_b in combinations(agents, 2):
                pos_a = self._position_at(paths[agent_a], t)
                pos_b = self._position_at(paths[agent_b], t)
                if pos_a == pos_b:
                    return CBSConflict(
                        kind="vertex",
                        agent_a=agent_a,
                        agent_b=agent_b,
                        time=t,
                        position=pos_a,
                    )

                if t == 0:
                    continue
                prev_a = self._position_at(paths[agent_a], t - 1)
                prev_b = self._position_at(paths[agent_b], t - 1)
                if prev_a == pos_b and prev_b == pos_a:
                    return CBSConflict(
                        kind="edge",
                        agent_a=agent_a,
                        agent_b=agent_b,
                        time=t,
                        edge_a=(prev_a, pos_a),
                        edge_b=(prev_b, pos_b),
                    )
        return None

    def _position_at(self, path: list[Pos], t: int) -> Pos:
        if t < len(path):
            return path[t]
        return path[-1]

    def _constraint_from_conflict(self, conflict: CBSConflict, agent_id: str) -> CBSConstraint:
        if conflict.kind == "vertex":
            if conflict.position is None:
                raise ValueError("vertex conflict missing position")
            return CBSConstraint(agent_id=agent_id, position=conflict.position, time=conflict.time)

        if conflict.kind == "edge":
            if agent_id == conflict.agent_a:
                if conflict.edge_a is None:
                    raise ValueError("edge conflict missing edge_a")
                edge_from, edge_to = conflict.edge_a
            else:
                if conflict.edge_b is None:
                    raise ValueError("edge conflict missing edge_b")
                edge_from, edge_to = conflict.edge_b
            return CBSConstraint(
                agent_id=agent_id,
                edge_from=edge_from,
                edge_to=edge_to,
                time=conflict.time,
            )

        raise ValueError(f"Unknown conflict kind: {conflict.kind}")
