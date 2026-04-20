"""Structured warehouse layout and runtime state.

:class:`WarehouseState` is the single source of truth passed through planning,
adaptation, and execution. It composes a :class:`~apex.simulation.grid.Grid`
with logical zones (shelves, conveyors, bays) and order queues consumed by the
strategic and tactical layers.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from apex.simulation.grid import Grid
from apex.simulation.order import Order


class ShelfZone(BaseModel):
    """A logical shelf region with capacity and inventory bookkeeping."""

    id: str
    positions: list[tuple[int, int]]
    capacity: int
    current_items: int = 0


class ConveyorSegment(BaseModel):
    """A directed conveyor span with traversal speed."""

    id: str
    positions: list[tuple[int, int]]
    direction: str
    speed: float


class LoadingBay(BaseModel):
    """Outbound or inbound dock with an order queue."""

    id: str
    position: tuple[int, int]
    queue: list[str] = Field(default_factory=list)


class WarehouseState(BaseModel):
    """Full warehouse snapshot for planners and sim processes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    grid: Grid
    shelf_zones: list[ShelfZone]
    conveyors: list[ConveyorSegment]
    bays: list[LoadingBay]
    pending_orders: list[Order]
    active_orders: list[Order]

    def get_shelf(self, shelf_id: str) -> ShelfZone:
        """Return the shelf zone with ``shelf_id``."""
        for z in self.shelf_zones:
            if z.id == shelf_id:
                return z
        raise KeyError(shelf_id)

    def get_bay(self, bay_id: str) -> LoadingBay:
        """Return the loading bay with ``bay_id``."""
        for b in self.bays:
            if b.id == bay_id:
                return b
        raise KeyError(bay_id)

    def is_shelf_available(self, shelf_id: str) -> bool:
        """True if the shelf can accept more inventory."""
        z = self.get_shelf(shelf_id)
        return z.current_items < z.capacity


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import Grid
    from apex.simulation.order import Order, OrderItem, OrderStatus

    g = Grid(3, 3, simpy.Environment())
    o = Order(
        id="ord-1",
        items=[OrderItem(sku="sku-a", shelf_zone_id="s1", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    ws = WarehouseState(
        grid=g,
        shelf_zones=[
            ShelfZone(id="s1", positions=[(0, 0)], capacity=10, current_items=0),
        ],
        conveyors=[],
        bays=[LoadingBay(id="b1", position=(2, 2), queue=[])],
        pending_orders=[o],
        active_orders=[],
    )
    print(repr(ws))
