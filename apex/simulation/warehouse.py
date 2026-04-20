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

    def is_full(self) -> bool:
        """Check if shelf is at capacity."""
        return self.current_items >= self.capacity

    def available_capacity(self) -> int:
        """Return remaining slots."""
        return self.capacity - self.current_items


class ConveyorSegment(BaseModel):
    """A directed conveyor span with traversal speed."""

    id: str
    positions: list[tuple[int, int]]
    direction: str  # "N", "S", "E", "W"
    speed: float  # cells per time unit


class LoadingBay(BaseModel):
    """Outbound or inbound dock with an order queue."""

    id: str
    position: tuple[int, int]
    queue: list[str] = Field(default_factory=list)  # order IDs waiting at bay

    def enqueue(self, order_id: str) -> None:
        """Add order to bay queue."""
        self.queue.append(order_id)

    def dequeue(self) -> str | None:
        """Remove and return first order, or None if empty."""
        return self.queue.pop(0) if self.queue else None


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
        """Return the shelf zone with ``shelf_id``, or raise KeyError."""
        for z in self.shelf_zones:
            if z.id == shelf_id:
                return z
        raise KeyError(f"Shelf {shelf_id} not found")

    def get_bay(self, bay_id: str) -> LoadingBay:
        """Return the loading bay with ``bay_id``, or raise KeyError."""
        for b in self.bays:
            if b.id == bay_id:
                return b
        raise KeyError(f"Bay {bay_id} not found")

    def get_conveyor(self, conveyor_id: str) -> ConveyorSegment:
        """Return the conveyor segment with ``conveyor_id``, or raise KeyError."""
        for c in self.conveyors:
            if c.id == conveyor_id:
                return c
        raise KeyError(f"Conveyor {conveyor_id} not found")

    def is_shelf_available(self, shelf_id: str) -> bool:
        """True if the shelf can accept more inventory."""
        z = self.get_shelf(shelf_id)
        return not z.is_full()

    def get_order(self, order_id: str) -> Order | None:
        """Find order by ID in pending or active lists."""
        for o in self.pending_orders:
            if o.id == order_id:
                return o
        for o in self.active_orders:
            if o.id == order_id:
                return o
        return None

    def total_pending_items(self) -> int:
        """Count all items across pending orders."""
        return sum(len(o.items) for o in self.pending_orders)

    def total_active_items(self) -> int:
        """Count all items across active orders."""
        return sum(len(o.items) for o in self.active_orders)


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import CellType, Grid
    from apex.simulation.order import Order, OrderItem, OrderStatus

    # Create a small grid
    env = simpy.Environment()
    g = Grid(10, 10, env)
    
    # Mark some cells as shelves, conveyors, and bays
    g.set_cell((1, 1), CellType.SHELF)
    g.set_cell((1, 2), CellType.SHELF)
    g.set_cell((5, 0), CellType.CONVEYOR)
    g.set_cell((5, 1), CellType.CONVEYOR)
    g.set_cell((9, 9), CellType.BAY)
    
    # Create shelf zones
    shelf_a = ShelfZone(
        id="shelf_a",
        positions=[(1, 1)],
        capacity=50,
        current_items=0,
    )
    shelf_b = ShelfZone(
        id="shelf_b",
        positions=[(1, 2)],
        capacity=40,
        current_items=0,
    )
    
    # Create conveyor segments
    conveyor_main = ConveyorSegment(
        id="conv_main",
        positions=[(5, 0), (5, 1)],
        direction="E",
        speed=2.0,
    )
    
    # Create loading bays
    bay_out = LoadingBay(id="bay_out", position=(9, 9), queue=[])
    
    # Create sample orders
    order1 = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    order2 = Order(
        id="ord-2",
        items=[
            OrderItem(sku="SKU-B", shelf_zone_id="shelf_b", quantity=1),
            OrderItem(sku="SKU-C", shelf_zone_id="shelf_a", quantity=3),
        ],
        priority=2,
        deadline=150.0,
        status=OrderStatus.PENDING,
    )
    
    # Create warehouse state
    warehouse = WarehouseState(
        grid=g,
        shelf_zones=[shelf_a, shelf_b],
        conveyors=[conveyor_main],
        bays=[bay_out],
        pending_orders=[order1, order2],
        active_orders=[],
    )
    
    print("=== Warehouse State ===")
    print(f"Grid: {warehouse.grid.rows}x{warehouse.grid.cols}")
    print(f"Shelves: {len(warehouse.shelf_zones)}")
    print(f"Conveyors: {len(warehouse.conveyors)}")
    print(f"Bays: {len(warehouse.bays)}")
    print(f"Pending orders: {len(warehouse.pending_orders)}")
    print(f"Active orders: {len(warehouse.active_orders)}")
    print()
    
    print("=== Shelf Details ===")
    for shelf in warehouse.shelf_zones:
        print(f"{shelf.id}: {shelf.current_items}/{shelf.capacity} (available: {shelf.available_capacity()})")
    print()
    
    print("=== Orders ===")
    for order in warehouse.pending_orders:
        print(f"{order.id} (priority {order.priority}, deadline {order.deadline}s):")
        for item in order.items:
            print(f"  - {item.sku} x{item.quantity} from {item.shelf_zone_id}")
    print()
    
    print("=== Test Methods ===")
    print(f"Shelf 'shelf_a' available: {warehouse.is_shelf_available('shelf_a')}")
    print(f"Total pending items: {warehouse.total_pending_items()}")
    print(f"Total active items: {warehouse.total_active_items()}")
    print()
    
    print("=== Bay Queue Test ===")
    bay_out.enqueue("ord-1")
    bay_out.enqueue("ord-2")
    print(f"Bay queue: {bay_out.queue}")
    dequeued = bay_out.dequeue()
    print(f"Dequeued: {dequeued}, Remaining: {bay_out.queue}")