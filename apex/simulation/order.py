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
    # Smoke test: create sample orders and batch
    
    # Create individual order items
    item1 = OrderItem(sku="SKU-001", shelf_zone_id="zone_a", quantity=2)
    item2 = OrderItem(sku="SKU-002", shelf_zone_id="zone_b", quantity=1)
    
    # Create orders
    order1 = Order(
        id="ord-1",
        items=[item1, item2],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )
    
    order2 = Order(
        id="ord-2",
        items=[OrderItem(sku="SKU-003", shelf_zone_id="zone_c", quantity=3)],
        priority=2,
        deadline=150.0,
        status=OrderStatus.PENDING,
    )
    
    # Create a batch
    batch = OrderBatch(
        orders=[order1, order2],
        arrival_time=0.0,
    )
    
    print("Order 1:", repr(order1))
    print("Order 2:", repr(order2))
    print("\nBatch:", repr(batch))
    print(f"\nBatch contains {len(batch.orders)} orders")
    print(f"Total items in batch: {sum(len(o.items) for o in batch.orders)}")