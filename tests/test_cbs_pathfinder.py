"""Tests for full CBS tactical pathfinding."""

import simpy

from apex.simulation.grid import CellType, Grid
from apex.tactical.cbs import CBSPlanner


def _position_at(path: list[tuple[int, int]], t: int) -> tuple[int, int]:
    if t < len(path):
        return path[t]
    return path[-1]


def _assert_conflict_free(paths: dict[str, list[tuple[int, int]]]) -> None:
    agents = sorted(paths)
    max_t = max(len(path) for path in paths.values()) - 1
    for t in range(max_t + 1):
        occupied: set[tuple[int, int]] = set()
        for agent in agents:
            pos = _position_at(paths[agent], t)
            assert pos not in occupied
            occupied.add(pos)

        if t == 0:
            continue
        for i, a in enumerate(agents):
            for b in agents[i + 1 :]:
                prev_a = _position_at(paths[a], t - 1)
                cur_a = _position_at(paths[a], t)
                prev_b = _position_at(paths[b], t - 1)
                cur_b = _position_at(paths[b], t)
                assert not (prev_a == cur_b and prev_b == cur_a)


def test_cbs_resolves_vertex_conflict():
    env = simpy.Environment()
    grid = Grid(3, 3, env)
    planner = CBSPlanner(grid)

    starts = {"a": (0, 1), "b": (2, 1)}
    goals = {"a": (2, 1), "b": (0, 1)}
    paths = planner.plan_paths(starts, goals)

    assert paths is not None
    _assert_conflict_free(paths)
    assert paths["a"][-1] == goals["a"]
    assert paths["b"][-1] == goals["b"]


def test_cbs_resolves_edge_swap_conflict():
    env = simpy.Environment()
    grid = Grid(3, 3, env)
    planner = CBSPlanner(grid)

    starts = {"a": (1, 0), "b": (1, 2)}
    goals = {"a": (1, 2), "b": (1, 0)}
    paths = planner.plan_paths(starts, goals)

    assert paths is not None
    _assert_conflict_free(paths)


def test_cbs_returns_none_when_unsat():
    env = simpy.Environment()
    grid = Grid(2, 2, env)
    grid.set_cell((1, 1), CellType.OBSTACLE)
    planner = CBSPlanner(grid)

    starts = {"a": (0, 0)}
    goals = {"a": (1, 1)}
    assert planner.plan_paths(starts, goals) is None


def test_cbs_matches_shortest_cost_when_independent():
    env = simpy.Environment()
    grid = Grid(5, 5, env)
    planner = CBSPlanner(grid)

    starts = {"a": (0, 0), "b": (4, 4)}
    goals = {"a": (0, 2), "b": (4, 2)}
    paths = planner.plan_paths(starts, goals)

    assert paths is not None
    # Independent lanes should keep shortest Manhattan costs.
    assert len(paths["a"]) - 1 == 2
    assert len(paths["b"]) - 1 == 2
