"""Shared pytest fixtures."""

import pytest
import simpy

from apex.simulation.grid import Grid
from apex.simulation.warehouse import LoadingBay, ShelfZone, WarehouseState


@pytest.fixture
def warehouse():
    """Standard test warehouse (shelf + bay)."""
    env = simpy.Environment()
    grid = Grid(20, 20, env)
    shelf = ShelfZone(id="shelf_a", positions=[(5, 5)], capacity=100)
    bay = LoadingBay(id="bay_out", position=(15, 15))

    return WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[bay],
        pending_orders=[],
        active_orders=[],
    )


@pytest.fixture
def warehouse_adjacent_bay():
    """Warehouse where shelf and bay are adjacent."""
    env = simpy.Environment()
    grid = Grid(20, 20, env)
    shelf = ShelfZone(id="shelf_adj", positions=[(5, 5)], capacity=100)
    bay = LoadingBay(id="bay_adj", position=(5, 6))

    return WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[bay],
        pending_orders=[],
        active_orders=[],
    )
