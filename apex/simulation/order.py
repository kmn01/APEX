"""Order and batch models for inbound work to the warehouse.

These Pydantic models feed the HTN planner and tactical layer. Status
transitions are tracked on each :class:`Order` while :class:`OrderBatch`
represents arrival-time groupings for batch planning.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Lifecycle state of a customer or internal order."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class OrderItem(BaseModel):
    """One line item referencing a SKU and source shelf zone."""

    sku: str
    shelf_zone_id: str
    quantity: int


class Order(BaseModel):
    """A single order with priority, deadline, and fulfillment status."""

    id: str
    items: list[OrderItem] = Field(default_factory=list)
    priority: int = 0
    deadline: float = 0.0
    status: OrderStatus = OrderStatus.PENDING


class OrderBatch(BaseModel):
    """Orders that arrived together for joint decomposition."""

    orders: list[Order] = Field(default_factory=list)
    arrival_time: float = 0.0


if __name__ == "__main__":
    o = Order(
        id="demo",
        items=[OrderItem(sku="x", shelf_zone_id="z1", quantity=2)],
        priority=1,
        deadline=50.0,
        status=OrderStatus.PENDING,
    )
    print(repr(o))
