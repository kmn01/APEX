"""Sorter robot agent for divert and staging near conveyors.

Aligns with abstract STAGE/DISPATCH-style tasks after HTN decomposition and
feeds metrics on throughput at sortation points.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy

from apex.agents.base import Agent, AgentCapabilities, AgentStatus, AgentType


class SorterBot(Agent):
    """Agent stationed on or near conveyor logic for sortation."""

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
            type=AgentType.SORTER,
            position=position,
            status=status,
            capabilities=capabilities,
            assigned_task=assigned_task,
        )
        self.should_stop = False  # Signal to stop the run loop
        self.items_sorted = 0  # Count of items sorted
        self.conveyor_id = None  # Which conveyor this sorter monitors
        self.divert_accuracy = 0.95  # Probability of correct sort (95%)

    def run(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """SimPy loop: monitor conveyor, execute diverts, stage to bays."""
        while not self.should_stop:
            # Check battery
            if self.battery_level <= 0:
                self.status = AgentStatus.FAILED
                print(f"[{env.now:.1f}] {self.id} FAILED: out of battery")
                break
            
            # If idle and no task, monitor conveyor
            if self.status == AgentStatus.IDLE and not self.assigned_task:
                yield env.timeout(0.5)
                continue
            
            # If we have an assigned task, process it
            if self.assigned_task:
                print(f"[{env.now:.1f}] {self.id} starting sort task: {self.assigned_task}")
                
                # Simulate sorting process (scanning, diverting, staging)
                self.status = AgentStatus.WORKING
                
                # Scan phase (0.5 time units) - read item info
                print(f"[{env.now:.1f}] {self.id} scanning items on conveyor...")
                yield env.timeout(0.5)
                self.consume_battery(0.5 * self.capabilities.battery_consumption_rate)
                
                # Divert/sort phase (1.5 time units) - physically divert items
                print(f"[{env.now:.1f}] {self.id} diverting items...")
                yield env.timeout(1.5)
                self.consume_battery(1.5 * self.capabilities.battery_consumption_rate)
                
                # Stage phase (1.0 time units) - position for pickup
                print(f"[{env.now:.1f}] {self.id} staging items for pickup...")
                yield env.timeout(1.0)
                self.consume_battery(1.0 * self.capabilities.battery_consumption_rate)
                
                # Process items
                items_processed = 3  # Typical batch size
                # Simulate occasional missorting
                import random
                if random.random() < self.divert_accuracy:
                    self.items_sorted += items_processed
                    accuracy_status = "OK"
                else:
                    # Missorting - count as partial work
                    self.items_sorted += max(1, items_processed - 1)
                    accuracy_status = "MISORT DETECTED"
                
                self.total_work_done += items_processed
                print(
                    f"[{env.now:.1f}] {self.id} completed sort cycle. "
                    f"Sorted: {items_processed} items ({accuracy_status}). "
                    f"Total work: {self.total_work_done}"
                )
                
                # Task complete
                self.assigned_task = None
                self.status = AgentStatus.IDLE
            else:
                # Idle for a bit
                yield env.timeout(0.5)

    def can_perform(self, task_type: str) -> bool:
        """Sorters specialize in sort/stage task families."""
        sort_tasks = ["SORT", "STAGE", "DIVERT", "SCAN_CONVEYOR"]
        return task_type.upper() in sort_tasks

    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Short-range repositioning along conveyor adjacency."""
        if not warehouse_state:
            return
        
        # Sorters typically move shorter distances (they're stationary)
        distance = self.manhattan_distance(pos)
        
        # Sorters move slower but more deliberately
        travel_time = distance / self.capabilities.max_speed
        
        # Update status
        self.status = AgentStatus.MOVING
        print(
            f"[{env.now:.1f}] {self.id} repositioning to {pos} "
            f"(distance: {distance}, time: {travel_time:.1f})"
        )
        
        # Simulate movement with time delay
        yield env.timeout(travel_time)
        
        # Update position and consume battery
        self.position = pos
        self.total_distance_traveled += distance
        battery_consumed = travel_time * self.capabilities.battery_consumption_rate
        self.consume_battery(battery_consumed)
        
        print(f"[{env.now:.1f}] {self.id} positioned at {pos}, battery: {self.battery_level:.1f}")
        self.status = AgentStatus.IDLE

    def set_monitored_conveyor(self, conveyor_id: str) -> None:
        """Assign this sorter to monitor a specific conveyor segment."""
        self.conveyor_id = conveyor_id
        print(f"{self.id} now monitoring conveyor: {conveyor_id}")

    def get_sort_metrics(self) -> dict[str, float]:
        """Return sorting performance metrics."""
        accuracy = (
            self.items_sorted / self.total_work_done
            if self.total_work_done > 0
            else 0.0
        )
        return {
            "items_sorted": self.items_sorted,
            "total_processed": self.total_work_done,
            "sort_accuracy": accuracy,
            "battery_remaining": self.battery_level,
        }


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import CellType, Grid
    from apex.simulation.order import Order, OrderItem, OrderStatus
    from apex.simulation.warehouse import (
        ConveyorSegment,
        LoadingBay,
        ShelfZone,
        WarehouseState,
    )

    # Create a warehouse with conveyor
    env = simpy.Environment()
    g = Grid(20, 20, env)
    g.set_cell((5, 5), CellType.CONVEYOR)
    g.set_cell((5, 6), CellType.CONVEYOR)
    g.set_cell((5, 7), CellType.CONVEYOR)
    g.set_cell((10, 10), CellType.BAY)

    shelf_a = ShelfZone(
        id="shelf_a",
        positions=[(2, 2)],
        capacity=100,
        current_items=50,
    )

    conveyor_main = ConveyorSegment(
        id="conv_main",
        positions=[(5, 5), (5, 6), (5, 7)],
        direction="E",
        speed=0.5,
    )

    order1 = Order(
        id="ord-1",
        items=[OrderItem(sku="SKU-A", shelf_zone_id="shelf_a", quantity=10)],
        priority=1,
        deadline=200.0,
        status=OrderStatus.PENDING,
    )

    warehouse = WarehouseState(
        grid=g,
        shelf_zones=[shelf_a],
        conveyors=[conveyor_main],
        bays=[LoadingBay(id="bay_out", position=(10, 10))],
        pending_orders=[order1],
        active_orders=[],
    )

    # Create a sorter bot with stationary characteristics
    sorter_caps = AgentCapabilities(
        max_speed=0.8,  # Slowest (mostly stationary)
        max_payload=1,  # Handles one item at a time
        sensor_range=3.0,
        battery_capacity=120.0,
        battery_consumption_rate=0.3,  # Efficient (least mobile)
    )

    sorter = SorterBot(
        id="sorter-1",
        position=(5, 6),  # Positioned on conveyor
        capabilities=sorter_caps,
        status=AgentStatus.IDLE,
    )

    print("=== Initial State ===")
    print(f"Sorter: {repr(sorter)}")
    print(f"Position: {sorter.position}")
    print(f"Battery: {sorter.battery_level}")
    print(f"Max Speed: {sorter.capabilities.max_speed}")
    print(f"Max Payload: {sorter.capabilities.max_payload}")
    print()

    print("=== Testing Sorter Operations ===")

    def test_sorter():
        """Test sorter repositioning and sorting operations."""
        
        # Assign to conveyor
        sorter.set_monitored_conveyor("conv_main")
        print()

        # Do several sort cycles
        for i in range(3):
            sorter.assigned_task = f"SORT_BATCH_{i+1}"
            yield env.timeout(5.0)  # Let main loop process
            print()

        # Test repositioning
        print("[TEST] Repositioning along conveyor...")
        yield env.process(sorter._move_to((5, 5), env, warehouse))
        print(f"Battery after reposition: {sorter.battery_level:.1f}")
        print()

        # More sort cycles
        for i in range(2):
            sorter.assigned_task = f"SORT_BATCH_{i+4}"
            yield env.timeout(5.0)
            print()

        # Print metrics
        print("=== Sort Metrics ===")
        metrics = sorter.get_sort_metrics()
        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
        print()

        # Test can_perform
        print("=== Task Capability Test ===")
        print(f"Can perform SORT: {sorter.can_perform('SORT')}")
        print(f"Can perform STAGE: {sorter.can_perform('stage')}")
        print(f"Can perform DIVERT: {sorter.can_perform('DIVERT')}")
        print(f"Can perform PICK: {sorter.can_perform('PICK')}")
        print()

        # Signal stop
        sorter.should_stop = True
        print("=== Final State ===")
        print(f"Position: {sorter.position}")
        print(f"Battery: {sorter.battery_level:.1f}")
        print(f"Total distance: {sorter.total_distance_traveled:.1f}")
        print(f"Total work done: {sorter.total_work_done}")
        print(f"Items sorted: {sorter.items_sorted}")
        print(f"Status: {sorter.status}")

    # Run the test
    env.process(sorter.run(env, warehouse))
    env.process(test_sorter())
    env.run()