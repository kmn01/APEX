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
        self._cells: np.ndarray = np.full((rows, cols), default, dtype=object)

    def __repr__(self) -> str:
        return f"Grid(rows={self.rows}, cols={self.cols}, env={self.env!r})"

    def is_walkable(self, pos: Pos) -> bool:
        """Return True if an agent may occupy ``pos``."""
        raise NotImplementedError("TODO: bounds check and CellType walkability rules")

    def get_cell_type(self, pos: Pos) -> CellType:
        """Return the :class:`CellType` at ``pos``."""
        raise NotImplementedError("TODO: index grid and map stored value to CellType")

    def set_cell(self, pos: Pos, cell_type: CellType) -> None:
        """Assign ``cell_type`` at ``pos``."""
        raise NotImplementedError("TODO: bounds check and write into backing array")

    def neighbors(self, pos: Pos) -> list[Pos]:
        """Return orthogonal neighbors inside the grid."""
        raise NotImplementedError("TODO: 4-connected neighbors with bounds checks")


if __name__ == "__main__":
    import simpy

    g = Grid(4, 5, simpy.Environment())
    print(repr(g))
