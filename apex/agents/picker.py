"""Picker robot agent specialized for shelf-facing retrieval.

Implements the :class:`~apex.agents.base.Agent` contract for pick tasks in the
tactical executor and registers with the fleet
:class:`~apex.agents.registry.AgentRegistry`.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import simpy

from apex.agents.base import Agent, AgentCapabilities, AgentStatus, AgentType


class PickerBot(Agent):
    """Agent that travels to shelves and performs picks."""

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
            type=AgentType.PICKER,
            position=position,
            status=status,
            capabilities=capabilities,
            assigned_task=assigned_task,
        )
        self.should_stop = False  # Signal to stop the run loop

    def run(
        self,
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """SimPy loop: accept tasks, move, pick, signal completion."""
        while not self.should_stop:
            # Check battery
            if self.battery_level <= 0:
                self.status = AgentStatus.FAILED
                print(f"[{env.now:.1f}] {self.id} FAILED: out of battery")
                break
            
            # If idle and no task, just wait
            if self.status == AgentStatus.IDLE and not self.assigned_task:
                yield env.timeout(1.0)
                continue
            
            # If we have an assigned task, process it
            if self.assigned_task:
                print(f"[{env.now:.1f}] {self.id} starting task: {self.assigned_task}")
                
                # Simulate picking process
                # In a real scenario, this would parse the task and navigate
                self.status = AgentStatus.WORKING
                
                # Simulate pick duration (2 time units)
                yield env.timeout(2.0)
                self.consume_battery(2.0 * self.capabilities.battery_consumption_rate)
                
                self.total_work_done += 1
                print(f"[{env.now:.1f}] {self.id} completed pick. Work done: {self.total_work_done}")
                
                # Task complete
                self.assigned_task = None
                self.status = AgentStatus.IDLE
            else:
                # Idle for a bit
                yield env.timeout(0.5)

    def can_perform(self, task_type: str) -> bool:
        """Pickers handle shelf-facing work types."""
        pick_tasks = ["PICK", "RETRIEVE", "SHELF_SCAN"]
        return task_type.upper() in pick_tasks

    def _move_to(
        self,
        pos: tuple[int, int],
        env: simpy.Environment,
        warehouse_state: Any,
    ) -> Generator[simpy.Event, None, None]:
        """Navigate using grid walkability and reservations."""
        if not warehouse_state:
            return
        
        # Calculate travel time based on distance and speed
        distance = self.manhattan_distance(pos)
        travel_time = distance / self.capabilities.max_speed
        
        # Update status
        self.status = AgentStatus.MOVING
        print(f"[{env.now:.1f}] {self.id} moving to {pos} (distance: {distance}, time: {travel_time:.1f})")
        
        # Simulate movement with time delay
        yield env.timeout(travel_time)
        
        # Update position and consume battery
        self.position = pos
        self.total_distance_traveled += distance
        battery_consumed = travel_time * self.capabilities.battery_consumption_rate
        self.consume_battery(battery_consumed)
        
        print(f"[{env.now:.1f}] {self.id} arrived at {pos}, battery: {self.battery_level:.1f}")
        self.status = AgentStatus.IDLE


if __name__ == "__main__":
    import simpy

    from apex.simulation.grid import CellType, Grid
    from apex.simulation.order import Order, OrderItem, OrderStatus
    from apex.simulation.warehouse import LoadingBay, ShelfZone, WarehouseState

    # Create a small warehouse
    env = simpy.Environment()
    g = Grid(10, 10, env)
    g.set_cell((1, 1), CellType.SHELF)
    g.set_cell((1, 2), CellType.SHELF)
    g.set_cell((9, 9), CellType.BAY)

    shelf_a = ShelfZone(
        id="shelf_a",
        positions=[(1, 1)],
        capacity=50,
        current_items=10,
    )
    shelf_b = ShelfZone(
        id="shelf_b",
        positions=[(1, 2)],
        capacity=40,
        current_items=5,
    )

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

    # Create a picker bot with custom capabilities
    picker_caps = AgentCapabilities(
        max_speed=2.0,  # 2 cells per time unit
        max_payload=10,
        sensor_range=5.0,
        battery_capacity=100.0,
        battery_consumption_rate=0.5,  # 0.5 energy per time unit
    )

    picker = PickerBot(
        id="picker-1",
        position=(0, 0),
        capabilities=picker_caps,
        status=AgentStatus.IDLE,
    )

    print("=== Initial State ===")
    print(f"Picker: {repr(picker)}")
    print(f"Position: {picker.position}")
    print(f"Battery: {picker.battery_level}")
    print(f"Capabilities: max_speed={picker.capabilities.max_speed}, max_payload={picker.capabilities.max_payload}")
    print()

    print("=== Testing Movement ===")

    def test_movement():
        """Test picker movement and task execution."""
        # Move to shelf A
        yield env.process(picker._move_to((1, 1), env, warehouse))
        print(f"Total distance: {picker.total_distance_traveled}, Battery: {picker.battery_level:.1f}")
        print()

        # Assign a task and run the main loop for a bit
        picker.assigned_task = "PICK_SKU-A"
        yield env.timeout(3.0)  # Let the main loop run
        print(f"Work done: {picker.total_work_done}, Battery: {picker.battery_level:.1f}")
        print()

        # Move to shelf B
        yield env.process(picker._move_to((1, 2), env, warehouse))
        print(f"Total distance: {picker.total_distance_traveled}, Battery: {picker.battery_level:.1f}")
        print()

        # Assign another task
        picker.assigned_task = "PICK_SKU-B"
        yield env.timeout(3.0)
        print(f"Work done: {picker.total_work_done}, Battery: {picker.battery_level:.1f}")
        print()

        # Signal the picker to stop its main loop
        picker.should_stop = True
        print(f"=== Final State ===")
        print(f"Position: {picker.position}")
        print(f"Battery: {picker.battery_level:.1f}")
        print(f"Total distance traveled: {picker.total_distance_traveled}")
        print(f"Total work done: {picker.total_work_done}")
        print(f"Status: {picker.status}")

    # Run the test
    env.process(picker.run(env, warehouse))
    env.process(test_movement())
    env.run()