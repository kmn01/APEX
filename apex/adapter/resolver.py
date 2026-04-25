"""Resolve abstract SKU and routing references to warehouse objects.

The domain translator calls these helpers to bind HTN tasks to concrete shelf
zones, bays, and conveyor segments inside :class:`~apex.simulation.warehouse.WarehouseState`.
"""

from __future__ import annotations

from typing import Any

from apex.common.geometry import manhattan_distance
from apex.simulation.warehouse import ConveyorSegment, LoadingBay, ShelfZone


class TaskResolver:
    """Lookup service from SKUs and order ids to physical infrastructure."""

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return "TaskResolver()"

    def resolve_shelf(self, sku: str, warehouse_state: Any) -> ShelfZone | None:
        """Find the :class:`ShelfZone` for ``sku``.

        If a pending or active order line references ``sku`` with a
        :attr:`~apex.simulation.order.OrderItem.shelf_zone_id`, that zone is
        resolved via :meth:`~apex.simulation.warehouse.WarehouseState.get_shelf`.
        Otherwise falls back to the first listed shelf (MVP policy).
        """
        if not warehouse_state.shelf_zones:
            return None
        for order in (
            *warehouse_state.pending_orders,
            *warehouse_state.active_orders,
        ):
            for item in order.items:
                if item.sku == sku:
                    try:
                        return warehouse_state.get_shelf(item.shelf_zone_id)
                    except KeyError:
                        continue
        return warehouse_state.shelf_zones[0]

    def resolve_bay(self, order_id: str, warehouse_state: Any) -> LoadingBay | None:
        """Select a :class:`LoadingBay` for ``order_id`` (MVP: first bay).

        Uses :meth:`~apex.simulation.warehouse.WarehouseState.get_order` when
        extending this to per-order bay assignment.
        """
        if not warehouse_state.bays:
            return None
        return warehouse_state.bays[0]

    def resolve_conveyor_segment(
        self,
        origin_row: int,
        origin_col: int,
        warehouse_state: Any,
    ) -> ConveyorSegment | None:
        """Return the conveyor segment whose cells are closest to the origin."""
        if not warehouse_state.conveyors:
            return None
        origin = (origin_row, origin_col)

        def min_dist(seg: ConveyorSegment) -> int:
            if not seg.positions:
                return 10**9
            return min(manhattan_distance(origin, p) for p in seg.positions)

        return min(warehouse_state.conveyors, key=min_dist)

    def resolve_conveyor_path(
        self,
        origin: tuple[int, int],
        dest: tuple[int, int],
        warehouse_state: Any,
    ) -> list[ConveyorSegment]:
        """Return ordered conveyor segments connecting ``origin`` to ``dest``.

        For MVP: return all conveyors in order. In production: graph search.
        """
        return warehouse_state.conveyors


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import Grid
    from apex.simulation.warehouse import (
        ConveyorSegment,
        LoadingBay,
        ShelfZone,
        WarehouseState,
    )

    env = simpy.Environment()
    grid = Grid(20, 20, env)

    shelf_a = ShelfZone(id="shelf_a", positions=[(5, 5)], capacity=100)
    bay_out = LoadingBay(id="bay_out", position=(15, 15))
    conveyor = ConveyorSegment(
        id="conv_main",
        positions=[(10, 10)],
        direction="E",
        speed=2.0,
    )

    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf_a],
        conveyors=[conveyor],
        bays=[bay_out],
        pending_orders=[],
        active_orders=[],
    )

    resolver = TaskResolver()
    print("=== Testing TaskResolver ===")
    print(repr(resolver))
    print()

    print("=== Resolve Shelf ===")
    shelf = resolver.resolve_shelf("SKU-A", warehouse)
    print(f"Shelf for SKU-A: {shelf.id if shelf else None}")
    print()

    print("=== Resolve Bay ===")
    bay = resolver.resolve_bay("ord-1", warehouse)
    print(f"Bay for ord-1: {bay.id if bay else None}")
    print()

    print("=== Resolve Conveyor Path ===")
    path = resolver.resolve_conveyor_path((0, 0), (20, 20), warehouse)
    print(f"Conveyor path: {[c.id for c in path]}")
