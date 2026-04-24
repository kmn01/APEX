"""Translate abstract HTN tasks into concrete tactical instructions.

Maps planner :class:`AbstractTask` nodes to :class:`ConcreteInstruction`
sequences understood by the tactical executor and CBS layer, using live
:class:`~apex.simulation.warehouse.WarehouseState` for grounding.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apex.adapter.resolver import TaskResolver
from apex.tactical.executor import TaskInstruction


class AbstractTask(BaseModel):
    """Planner-side task with hints for domain binding."""

    task_type: str
    item_sku: str | None = None
    zone_hint: str | None = None
    priority: int = 0
    deadline: float = 0.0


class ConcreteInstruction(BaseModel):
    """Grounded instruction with explicit resource ids."""

    agent_id: str
    action_sequence: list[str] = Field(default_factory=list)
    shelf_id: str | None = None
    conveyor_id: str | None = None
    bay_id: str | None = None


class DomainTranslator:
    """Applies resolver logic to build concrete instruction payloads."""

    def __init__(self, resolver: TaskResolver | None = None) -> None:
        self.resolver = resolver or TaskResolver()

    def __repr__(self) -> str:
        return f"DomainTranslator(resolver={self.resolver!r})"

    def translate(
        self,
        task: AbstractTask,
        warehouse_state: Any,
        agent_id: str = "agent-1",
    ) -> list[TaskInstruction]:
        """Ground ``task`` using current warehouse layout and inventory.
        
        Returns a sequence of tactical instructions to execute the task.
        """
        instructions: list[TaskInstruction] = []
        
        if task.task_type == "PICK":
            # Resolve SKU to shelf
            shelf = self.resolver.resolve_shelf(task.item_sku or "", warehouse_state)
            
            # Generate movement + pick sequence
            if shelf and shelf.positions:
                target_pos = shelf.positions[0]
                instructions.append(
                    TaskInstruction(
                        agent_id=agent_id,
                        action_type="MOVE_TO",
                        target_pos=target_pos,
                        shelf_id=shelf.id,
                    )
                )
                instructions.append(
                    TaskInstruction(
                        agent_id=agent_id,
                        action_type="PICK",
                        shelf_id=shelf.id,
                        deadline=task.deadline,
                    )
                )
        
        elif task.task_type == "TRANSPORT":
            # Move to conveyor, place item
            conveyor = self.resolver.resolve_conveyor_segment(
                warehouse_state.grid.rows // 2,
                warehouse_state.grid.cols // 2,
                warehouse_state,
            )
            
            if conveyor and conveyor.positions:
                target_pos = conveyor.positions[0]
                instructions.append(
                    TaskInstruction(
                        agent_id=agent_id,
                        action_type="MOVE_TO",
                        target_pos=target_pos,
                        conveyor_id=conveyor.id,
                    )
                )
                instructions.append(
                    TaskInstruction(
                        agent_id=agent_id,
                        action_type="PLACE_ON_CONVEYOR",
                        conveyor_id=conveyor.id,
                    )
                )
        
        elif task.task_type == "DISPATCH":
            # Move to bay, hand off
            bay = self.resolver.resolve_bay("order-1", warehouse_state)
            
            if bay:
                instructions.append(
                    TaskInstruction(
                        agent_id=agent_id,
                        action_type="MOVE_TO",
                        target_pos=bay.position,
                        bay_id=bay.id,
                    )
                )
                instructions.append(
                    TaskInstruction(
                        agent_id=agent_id,
                        action_type="DISPATCH",
                        bay_id=bay.id,
                        deadline=task.deadline,
                    )
                )
        
        else:
            # Generic action
            instructions.append(
                TaskInstruction(
                    agent_id=agent_id,
                    action_type=task.task_type,
                    deadline=task.deadline,
                )
            )
        
        return instructions


if __name__ == "__main__":
    import simpy

    from apex.adapter.resolver import TaskResolver
    from apex.simulation.grid import CellType, Grid
    from apex.simulation.warehouse import (
        ConveyorSegment,
        LoadingBay,
        ShelfZone,
        WarehouseState,
    )
    from apex.simulation.order import Order, OrderItem, OrderStatus

    env = simpy.Environment()
    grid = Grid(20, 20, env)
    
    # Setup zones
    shelf_a = ShelfZone(id="shelf_a", positions=[(5, 5)], capacity=100)
    bay_out = LoadingBay(id="bay_out", position=(15, 15))
    conveyor = ConveyorSegment(
        id="conv_main",
        positions=[(10, 10), (10, 11)],
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
    
    translator = DomainTranslator()
    
    print("=== Testing DomainTranslator ===")
    print(repr(translator))
    print()
    
    print("=== PICK Task ===")
    pick_task = AbstractTask(
        task_type="PICK",
        item_sku="SKU-A",
        priority=1,
        deadline=100.0,
    )
    pick_instrs = translator.translate(pick_task, warehouse, "picker-1")
    for instr in pick_instrs:
        print(f"  {instr}")
    print()
    
    print("=== TRANSPORT Task ===")
    transport_task = AbstractTask(
        task_type="TRANSPORT",
        priority=1,
        deadline=150.0,
    )
    transport_instrs = translator.translate(transport_task, warehouse, "carrier-1")
    for instr in transport_instrs:
        print(f"  {instr}")
    print()
    
    print("=== DISPATCH Task ===")
    dispatch_task = AbstractTask(
        task_type="DISPATCH",
        priority=1,
        deadline=200.0,
    )
    dispatch_instrs = translator.translate(dispatch_task, warehouse, "picker-1")
    for instr in dispatch_instrs:
        print(f"  {instr}")