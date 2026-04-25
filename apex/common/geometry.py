"""Grid and spatial helpers shared by simulation, pathfinding, and agents."""

from __future__ import annotations


def manhattan_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Return Manhattan distance |r1 - r2| + |c1 - c2| for grid coordinates."""
    r1, c1 = a
    r2, c2 = b
    return abs(r1 - r2) + abs(c1 - c2)
