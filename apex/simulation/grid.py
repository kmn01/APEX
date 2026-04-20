"""Discrete grid representation for the warehouse floor.

Used by :class:`~apex.simulation.warehouse.WarehouseState` and pathfinding to
answer walkability, cell occupancy, and local neighborhood queries. The grid
holds a reference to a SimPy :class:`~simpy.Environment` for time-aware
reservations elsewhere, but this module does not schedule events itself.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import simpy


Pos = tuple[int, int]


class CellType(str, Enum):
    """Semantic labels for each grid cell."""

    EMPTY = "EMPTY"
    SHELF = "SHELF"
    CONVEYOR = "CONVEYOR"
    BAY = "BAY"
    OBSTACLE = "OBSTACLE"


class Grid:
    """Row-major warehouse grid with cell types backed by a NumPy array."""

    def __init__(
        self,
        rows: int,
        cols: int,
        env: simpy.Environment,
        default: CellType = CellType.EMPTY,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.env = env
        # Use dtype=object to store CellType enums properly (not strings)
        self._cells: np.ndarray = np.empty((rows, cols), dtype=object)
        # Initialize all cells with the default type
        for i in range(rows):
            for j in range(cols):
                self._cells[i, j] = default

    def __repr__(self) -> str:
        return f"Grid(rows={self.rows}, cols={self.cols}, env={self.env!r})"

    def is_walkable(self, pos: Pos) -> bool:
        """Return True if an agent may occupy ``pos``."""
        # Check bounds
        r, c = pos
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return False
        
        # Get cell type
        cell_type = self.get_cell_type(pos)
        
        # Walkable: EMPTY, SHELF, CONVEYOR, BAY (can pass through)
        # Not walkable: OBSTACLE
        return cell_type != CellType.OBSTACLE

    def get_cell_type(self, pos: Pos) -> CellType:
        """Return the :class:`CellType` at ``pos``."""
        r, c = pos
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise IndexError(f"Position {pos} out of bounds for grid {self.rows}x{self.cols}")
        
        cell_value = self._cells[r, c]
        # Already stored as CellType, just return it
        if isinstance(cell_value, CellType):
            return cell_value
        # Fallback (shouldn't happen with proper initialization)
        raise ValueError(f"Invalid cell value at {pos}: {cell_value}")

    def set_cell(self, pos: Pos, cell_type: CellType) -> None:
        """Assign ``cell_type`` at ``pos``."""
        r, c = pos
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise IndexError(f"Position {pos} out of bounds for grid {self.rows}x{self.cols}")
        
        if not isinstance(cell_type, CellType):
            raise ValueError(f"Expected CellType, got {type(cell_type)}")
        
        self._cells[r, c] = cell_type

    def neighbors(self, pos: Pos) -> list[Pos]:
        """Return orthogonal neighbors inside the grid."""
        r, c = pos
        # 4-connected neighbors: up, down, left, right
        candidate_neighbors = [
            (r - 1, c),  # up
            (r + 1, c),  # down
            (r, c - 1),  # left
            (r, c + 1),  # right
        ]
        
        # Filter to keep only in-bounds neighbors
        valid_neighbors = [
            (nr, nc) 
            for nr, nc in candidate_neighbors 
            if 0 <= nr < self.rows and 0 <= nc < self.cols
        ]
        
        return valid_neighbors


if __name__ == "__main__":
    import simpy

    # Smoke test: create a simple grid and verify operations
    env = simpy.Environment()
    g = Grid(4, 5, env)
    print(repr(g))
    
    # Test setting cells
    g.set_cell((0, 0), CellType.SHELF)
    g.set_cell((3, 4), CellType.BAY)
    g.set_cell((1, 1), CellType.OBSTACLE)
    
    # Test walkability
    print(f"(0, 0) walkable: {g.is_walkable((0, 0))}")  # Shelf: True
    print(f"(1, 1) walkable: {g.is_walkable((1, 1))}")  # Obstacle: False
    print(f"(2, 2) walkable: {g.is_walkable((2, 2))}")  # Empty: True
    print(f"(10, 10) walkable: {g.is_walkable((10, 10))}")  # Out of bounds: False
    
    # Test neighbors
    print(f"Neighbors of (2, 2): {g.neighbors((2, 2))}")
    print(f"Neighbors of (0, 0): {g.neighbors((0, 0))}")  # Corner