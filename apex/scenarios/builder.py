"""Construct :class:`~apex.simulation.warehouse.WarehouseState` from :class:`ScenarioSpec`."""

from __future__ import annotations

import simpy

from apex.agents.base import AgentCapabilities
from apex.agents.picker import PickerBot
from apex.agents.registry import AgentRegistry
from apex.scenarios.models import ScenarioSpec, ShelfLayoutSpec
from apex.simulation.grid import CellType, Grid
from apex.simulation.warehouse import ConveyorSegment, LoadingBay, ShelfZone, WarehouseState


def _default_shelves(spec: ScenarioSpec) -> list[ShelfLayoutSpec]:
    mid_r, mid_c = spec.grid_rows // 2, spec.grid_cols // 2
    return [
        ShelfLayoutSpec(id="shelf_a", positions=[(mid_r - 2, mid_c - 2)]),
        ShelfLayoutSpec(id="shelf_b", positions=[(mid_r - 2, mid_c + 2)]),
    ]


def _default_conveyor(spec: ScenarioSpec) -> ConveyorSegment:
    mid_r, mid_c = spec.grid_rows // 2, spec.grid_cols // 2
    cells = [(mid_r, mid_c + i) for i in range(-2, 3)]
    return ConveyorSegment(
        id="conv_main",
        positions=cells,
        direction="E",
        speed=2.0,
    )


def build_warehouse_and_registry(spec: ScenarioSpec) -> tuple[simpy.Environment, WarehouseState, AgentRegistry]:
    env = simpy.Environment()
    grid = Grid(spec.grid_rows, spec.grid_cols, env)

    shelves_spec = spec.shelves if spec.shelves else _default_shelves(spec)
    shelf_zones: list[ShelfZone] = []
    for s in shelves_spec:
        sz = ShelfZone(id=s.id, positions=list(s.positions), capacity=s.capacity, current_items=50)
        shelf_zones.append(sz)
        for pos in s.positions:
            grid.set_cell(pos, CellType.SHELF)

    if spec.conveyor is not None:
        conv = ConveyorSegment(
            id=spec.conveyor.id,
            positions=list(spec.conveyor.positions),
            direction=spec.conveyor.direction,
            speed=spec.conveyor.speed,
        )
    else:
        conv = _default_conveyor(spec)
    for pos in conv.positions:
        grid.set_cell(pos, CellType.CONVEYOR)

    bay = LoadingBay(id=spec.bay_id, position=spec.bay_position)
    grid.set_cell(bay.position, CellType.BAY)

    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=shelf_zones,
        conveyors=[conv],
        bays=[bay],
        pending_orders=[],
        active_orders=[],
    )

    registry = AgentRegistry()
    caps = AgentCapabilities(
        max_speed=1.0,
        max_payload=10,
        battery_capacity=1_000_000.0,
        battery_consumption_rate=0.01,
    )
    for a in spec.agents:
        picker = PickerBot(id=a.id, position=(a.row, a.col), capabilities=caps)
        registry.register(picker)

    return env, warehouse, registry
