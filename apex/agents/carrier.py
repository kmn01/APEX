"""Carrier robot agent for totes and pallets across the floor.

Bridges shelf zones, conveyors, and bays under tactical instructions issued by
the CBS-backed executor.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy

from apex.agents.base import Agent, AgentCapabilities, AgentStatus, AgentType


class CarrierBot(Agent):
    """Higher-payload agent for transport legs."""

    def __init__(
        self,
        id: str,
        position: tuple[int, int],
        status: AgentStatus = AgentStatus.IDLE,
        capabilities: AgentCapabilities | None = None,
        assigned_task: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
            type=AgentType.CARRIER,
            position=position,
            status=status,
            capabilities=capabilities,
            assigned_task=assigned_task,
        )
        self.load_id = None  # Current load/tote being carried

    def _execute_assigned_task(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Load, travel leg, and unload for the current transport assignment."""
        assert self.assigned_task
        print(f"[{env.now:.1f}] {self.id} starting transport task: {self.assigned_task}")
        self.status = AgentStatus.WORKING

        print(f"[{env.now:.1f}] {self.id} loading cargo...")
        yield env.timeout(1.0)
        self.consume_battery(1.0 * self.capabilities.battery_consumption_rate)
        self.load_id = f"load-{env.now}"
        self.current_payload = min(3, self.capabilities.max_payload)
        print(
            f"[{env.now:.1f}] {self.id} loaded {self.current_payload} items "
            f"(load_id: {self.load_id})"
        )

        print(f"[{env.now:.1f}] {self.id} transporting to destination...")
        yield env.timeout(2.0)
        self.consume_battery(2.0 * self.capabilities.battery_consumption_rate)

        print(f"[{env.now:.1f}] {self.id} unloading cargo...")
        yield env.timeout(1.0)
        self.consume_battery(1.0 * self.capabilities.battery_consumption_rate)
        items_unloaded = self.current_payload
        self.current_payload = 0
        self.load_id = None
        self.total_work_done += items_unloaded
        print(
            f"[{env.now:.1f}] {self.id} completed transport. Unloaded {items_unloaded} items. "
            f"Total work: {self.total_work_done}"
        )
        self.assigned_task = None
        self.status = AgentStatus.IDLE

    def can_perform(self, task_type: str) -> bool:
        """Carriers accept transport-heavy abstract tasks."""
        transport_tasks = ["TRANSPORT", "CARRY", "MOVE_LOAD", "DELIVER"]
        return task_type.upper() in transport_tasks

    def _effective_travel_speed(self) -> float:
        """Heavier load reduces effective speed (up to 50% reduction)."""
        if self.current_payload <= 0:
            return self.capabilities.max_speed
        payload_penalty = min(
            0.5, self.current_payload / self.capabilities.max_payload * 0.5
        )
        return self.capabilities.max_speed * (1.0 - payload_penalty)

    def _movement_log_suffix(self) -> str:
        if self.current_payload > 0:
            return f" (carrying {self.current_payload} items)"
        return ""


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import CellType, Grid
    from apex.simulation.order import Order, OrderItem, OrderStatus
    from apex.simulation.warehouse import LoadingBay, ShelfZone, WarehouseState

    # Create a warehouse
    env = simpy.Environment()
    g = Grid(15, 15, env)
    g.set_cell((2, 2), CellType.SHELF)
    g.set_cell((5, 5), CellType.CONVEYOR)
    g.set_cell((12, 12), CellType.BAY)

    shelf_a = ShelfZone(
        id="shelf_a",
        positions=[(2, 2)],
        capacity=100,
        current_items=20,
    )

    order1 = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=5)],
        priority=1,
        deadline=200.0,
        status=OrderStatus.PENDING,
    )

    warehouse = WarehouseState(
        grid=g,
        shelf_zones=[shelf_a],
        conveyors=[],
        bays=[LoadingBay(id="bay_out", position=(12, 12))],
        pending_orders=[order1],
        active_orders=[],
    )

    # Create a carrier bot with higher payload capacity
    carrier_caps = AgentCapabilities(
        max_speed=1.5,  # 1.5 cells per time unit (slower than picker)
        max_payload=20,  # Can carry 20 items (vs picker's 10)
        sensor_range=8.0,
        battery_capacity=150.0,
        battery_consumption_rate=0.4,
    )

    carrier = CarrierBot(
        id="carrier-1",
        position=(0, 0),
        capabilities=carrier_caps,
        status=AgentStatus.IDLE,
    )

    print("=== Initial State ===")
    print(f"Carrier: {repr(carrier)}")
    print(f"Position: {carrier.position}")
    print(f"Battery: {carrier.battery_level}")
    print(f"Max Payload: {carrier.capabilities.max_payload}")
    print(f"Max Speed: {carrier.capabilities.max_speed}")
    print()

    print("=== Testing Carrier Movement and Transport ===")

    def test_carrier():
        """Test carrier movement and transport operations."""
        # Move to shelf
        print("[TEST] Moving to shelf...")
        yield env.process(carrier._move_to((2, 2), env, warehouse))
        print(f"Battery after move to shelf: {carrier.battery_level:.1f}")
        print()

        # Assign transport task
        carrier.assigned_task = "TRANSPORT_LOAD_1"
        yield env.timeout(5.0)  # Let the main loop process the task
        print(f"Payload: {carrier.current_payload}, Work done: {carrier.total_work_done}")
        print(f"Battery after transport: {carrier.battery_level:.1f}")
        print()

        # Move to bay (while carrying load)
        print("[TEST] Moving to bay with load...")
        yield env.process(carrier._move_to((12, 12), env, warehouse))
        print(f"Battery after move to bay: {carrier.battery_level:.1f}")
        print(f"Total distance: {carrier.total_distance_traveled}")
        print()

        # Do another transport task
        carrier.assigned_task = "TRANSPORT_LOAD_2"
        yield env.timeout(5.0)
        print(f"Total work done: {carrier.total_work_done}")
        print(f"Battery: {carrier.battery_level:.1f}")
        print()

        # Test can_perform
        print("=== Task Capability Test ===")
        print(f"Can perform TRANSPORT: {carrier.can_perform('TRANSPORT')}")
        print(f"Can perform CARRY: {carrier.can_perform('carry')}")
        print(f"Can perform PICK: {carrier.can_perform('PICK')}")
        print()

        # Signal stop
        carrier.should_stop = True
        print("=== Final State ===")
        print(f"Position: {carrier.position}")
        print(f"Battery: {carrier.battery_level:.1f}")
        print(f"Total distance: {carrier.total_distance_traveled:.1f}")
        print(f"Total work done: {carrier.total_work_done}")
        print(f"Status: {carrier.status}")

    # Run the test
    env.process(carrier.run(env, warehouse))
    env.process(test_carrier())
    env.run()
