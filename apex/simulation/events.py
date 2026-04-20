"""Stochastic disruption processes for the SimPy simulation.

This module hosts generators that inject agent failures, blocked shelves, and
ad-hoc orders into the running model. It reads and updates
:class:`~apex.simulation.warehouse.WarehouseState` but does not own it.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import numpy as np
import simpy


class StochasticEventGenerator:
    """SimPy-aware source of random operational disruptions."""

    def __init__(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.env = env
        self.warehouse_state = warehouse_state
        self.config = config if config is not None else {}
        
        # Default config values
        self.disruption_rate = self.config.get("disruption_rate", 0.1)  # events per time unit
        self.agent_failure_rate = self.config.get("agent_failure_rate", 0.05)
        self.shelf_block_rate = self.config.get("shelf_block_rate", 0.03)
        self.new_order_rate = self.config.get("new_order_rate", 0.02)
        self.block_duration = self.config.get("block_duration", 10.0)
        self.rng_seed = self.config.get("rng_seed", 42)
        
        # Initialize random number generator
        self.rng = np.random.RandomState(self.rng_seed)
        self.events_generated = 0

    def __repr__(self) -> str:
        return (
            f"StochasticEventGenerator(env={self.env!r}, "
            f"disruption_rate={self.disruption_rate}, "
            f"config={self.config!r})"
        )

    def run(self) -> Generator[simpy.Event, None, None]:
        """SimPy process that schedules random disruptions over time."""
        while True:
            # Sample time to next disruption event
            time_to_next = self.rng.exponential(1.0 / self.disruption_rate)
            yield self.env.timeout(time_to_next)
            
            # Decide which type of disruption
            event_type = self.rng.choice(
                ["agent_failure", "shelf_block", "new_order"],
                p=[
                    self.agent_failure_rate,
                    self.shelf_block_rate,
                    self.new_order_rate,
                ]
                / np.array(
                    [
                        self.agent_failure_rate,
                        self.shelf_block_rate,
                        self.new_order_rate,
                    ]
                ).sum(),
            )
            
            if event_type == "agent_failure":
                self._agent_failure_event()
            elif event_type == "shelf_block":
                self._shelf_block_event()
            elif event_type == "new_order":
                self._new_order_injection_event()
            
            self.events_generated += 1

    def _agent_failure_event(self) -> None:
        """Schedule or handle a random agent failure."""
        # This is a stub - in M2 we'll have agents to fail
        # For now, just log it
        if self.warehouse_state:
            print(
                f"[{self.env.now:.1f}] DISRUPTION: Agent failure event "
                f"(no agents yet in M1)"
            )

    def _shelf_block_event(self) -> None:
        """Block shelf access or capacity for a period."""
        if not self.warehouse_state or not self.warehouse_state.shelf_zones:
            return
        
        # Pick a random shelf
        shelf = self.rng.choice(self.warehouse_state.shelf_zones)
        original_capacity = shelf.capacity
        
        # Reduce its capacity (simulating blocked access)
        reduced_capacity = max(1, int(shelf.capacity * 0.5))
        shelf.capacity = reduced_capacity
        
        print(
            f"[{self.env.now:.1f}] DISRUPTION: Shelf '{shelf.id}' blocked. "
            f"Capacity {original_capacity} -> {reduced_capacity}"
        )
        
        # Schedule unblock event
        yield self.env.timeout(self.block_duration)
        shelf.capacity = original_capacity
        print(f"[{self.env.now:.1f}] RECOVERY: Shelf '{shelf.id}' unblocked.")

    def _new_order_injection_event(self) -> None:
        """Inject a new high-priority or standard order."""
        if not self.warehouse_state:
            return
        
        from apex.simulation.order import Order, OrderItem, OrderStatus
        
        # Generate a random order
        order_num = len(self.warehouse_state.pending_orders) + len(
            self.warehouse_state.active_orders
        )
        new_order_id = f"injected-{order_num}"
        
        # Pick random shelf zones for items
        if not self.warehouse_state.shelf_zones:
            return
        
        num_items = self.rng.randint(1, 4)
        items = []
        for i in range(num_items):
            shelf = self.rng.choice(self.warehouse_state.shelf_zones)
            item = OrderItem(
                sku=f"injected-sku-{order_num}-{i}",
                shelf_zone_id=shelf.id,
                quantity=self.rng.randint(1, 3),
            )
            items.append(item)
        
        new_order = Order(
            id=new_order_id,
            items=items,
            priority=self.rng.randint(1, 5),
            deadline=self.env.now + self.rng.uniform(50, 200),
            status=OrderStatus.PENDING,
        )
        
        self.warehouse_state.pending_orders.append(new_order)
        print(
            f"[{self.env.now:.1f}] DISRUPTION: New order '{new_order_id}' injected "
            f"({num_items} items, priority {new_order.priority})"
        )


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import CellType, Grid
    from apex.simulation.order import OrderItem, OrderStatus
    from apex.simulation.order import Order
    from apex.simulation.warehouse import LoadingBay, ShelfZone, WarehouseState

    # Create a small warehouse
    env = simpy.Environment()
    g = Grid(10, 10, env)
    g.set_cell((1, 1), CellType.SHELF)
    g.set_cell((5, 5), CellType.CONVEYOR)
    g.set_cell((9, 9), CellType.BAY)

    shelf_a = ShelfZone(id="shelf_a", positions=[(1, 1)], capacity=50, current_items=0)
    shelf_b = ShelfZone(id="shelf_b", positions=[(1, 2)], capacity=40, current_items=0)

    order1 = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )

    warehouse = WarehouseState(
        grid=g,
        shelf_zones=[shelf_a, shelf_b],
        conveyors=[],
        bays=[LoadingBay(id="bay_out", position=(9, 9))],
        pending_orders=[order1],
        active_orders=[],
    )

    # Create event generator
    config = {
        "disruption_rate": 0.5,  # 1 event every 2 time units
        "agent_failure_rate": 0.0,  # Disable for now (no agents in M1)
        "shelf_block_rate": 0.5,
        "new_order_rate": 0.5,
        "block_duration": 5.0,
        "rng_seed": 123,
    }

    gen = StochasticEventGenerator(env, warehouse, config)
    print(f"Generator: {repr(gen)}")
    print()

    # Run simulation with events for 100 time units
    print("=== Running Simulation ===")
    print(f"Initial pending orders: {len(warehouse.pending_orders)}")
    print(f"Initial shelf_a capacity: {warehouse.get_shelf('shelf_a').capacity}")
    print()

    env.process(gen.run())
    env.run(until=100)

    print()
    print("=== Simulation Complete ===")
    print(f"Total disruption events generated: {gen.events_generated}")
    print(f"Final pending orders: {len(warehouse.pending_orders)}")
    print(f"Final shelf_a capacity: {warehouse.get_shelf('shelf_a').capacity}")