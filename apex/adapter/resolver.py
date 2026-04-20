"""Resolve abstract SKU and routing references to warehouse objects.

The domain translator calls these helpers to bind HTN tasks to concrete shelf
zones, bays, and conveyor segments inside :class:`~apex.simulation.warehouse.WarehouseState`.
"""

from __future__ import annotations

from typing import Any

from apex.simulation.warehouse import ConveyorSegment, LoadingBay, ShelfZone


class TaskResolver:
    """Lookup service from SKUs and order ids to physical infrastructure."""

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return "TaskResolver()"

    def resolve_shelf(self, sku: str, warehouse_state: Any) -> ShelfZone:
        """Find the :class:`ShelfZone` holding ``sku``."""
        raise NotImplementedError("TODO: index SKUs to shelf zones from state")

    def resolve_bay(self, order_id: str, warehouse_state: Any) -> LoadingBay:
        """Select a :class:`LoadingBay` for ``order_id``."""
        raise NotImplementedError("TODO: bay assignment policy from order id")

    def resolve_conveyor_path(
        self,
        origin: tuple[int, int],
        dest: tuple[int, int],
        warehouse_state: Any,
    ) -> list[ConveyorSegment]:
        """Return ordered conveyor segments connecting ``origin`` to ``dest``."""
        raise NotImplementedError("TODO: graph search over conveyor segments")


if __name__ == "__main__":
    tr = TaskResolver()
    print(repr(tr))
