"""Tests for M4 Domain Adapter."""

import pytest
import simpy

from apex.adapter.resolver import TaskResolver
from apex.adapter.translator import AbstractTask, DomainTranslator
from apex.simulation.grid import Grid
from apex.simulation.order import Order, OrderItem, OrderStatus
from apex.simulation.warehouse import (
    ConveyorSegment,
    LoadingBay,
    ShelfZone,
    WarehouseState,
)


@pytest.fixture
def warehouse():
    """Create test warehouse."""
    env = simpy.Environment()
    grid = Grid(20, 20, env)
    
    shelf = ShelfZone(id="shelf_a", positions=[(5, 5)], capacity=100)
    bay = LoadingBay(id="bay_out", position=(15, 15))
    conveyor = ConveyorSegment(
        id="conv_main",
        positions=[(10, 10)],
        direction="E",
        speed=2.0,
    )
    
    return WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[conveyor],
        bays=[bay],
        pending_orders=[],
        active_orders=[],
    )


def test_translator_creation():
    """Test translator initialization."""
    translator = DomainTranslator()
    assert translator is not None
    assert translator.resolver is not None


def test_translate_pick_task(warehouse):
    """Test translating a PICK task."""
    translator = DomainTranslator()
    task = AbstractTask(task_type="PICK", item_sku="SKU-A", priority=1)
    
    instructions = translator.translate(task, warehouse, "picker-1")
    assert len(instructions) >= 2
    assert any(i.action_type == "MOVE_TO" for i in instructions)
    assert any(i.action_type == "PICK" for i in instructions)


def test_translate_transport_task(warehouse):
    """Test translating a TRANSPORT task."""
    translator = DomainTranslator()
    task = AbstractTask(task_type="TRANSPORT", priority=1)
    
    instructions = translator.translate(task, warehouse, "carrier-1")
    assert len(instructions) >= 2
    assert any(i.action_type == "MOVE_TO" for i in instructions)
    assert all(i.conveyor_id == "conv_main" for i in instructions)


def test_translate_dispatch_task(warehouse):
    """Test translating a DISPATCH task."""
    translator = DomainTranslator()
    task = AbstractTask(task_type="DISPATCH", priority=1)
    
    instructions = translator.translate(task, warehouse, "picker-1")
    assert len(instructions) >= 2
    assert any(i.action_type == "DISPATCH" for i in instructions)


def test_resolver_shelf():
    """Test shelf resolution."""
    resolver = TaskResolver()
    env = simpy.Environment()
    grid = Grid(10, 10, env)
    shelf = ShelfZone(id="s1", positions=[(2, 2)], capacity=50)
    
    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[],
        pending_orders=[],
        active_orders=[],
    )
    
    resolved = resolver.resolve_shelf("SKU-X", warehouse)
    assert resolved is not None
    assert resolved.id == "s1"


def test_resolve_bay_prefers_order_queue_assignment():
    resolver = TaskResolver()
    env = simpy.Environment()
    grid = Grid(10, 10, env)
    shelf = ShelfZone(id="s1", positions=[(2, 2)], capacity=50)
    bay_a = LoadingBay(id="bay-a", position=(9, 9), queue=["ord-1"])
    bay_b = LoadingBay(id="bay-b", position=(1, 1), queue=[])

    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[bay_a, bay_b],
        pending_orders=[],
        active_orders=[],
    )

    assert resolver.resolve_bay("ord-1", warehouse).id == "bay-a"


def test_resolve_bay_uses_order_shelf_proximity_and_queue():
    resolver = TaskResolver()
    env = simpy.Environment()
    grid = Grid(10, 10, env)
    shelf = ShelfZone(id="s1", positions=[(2, 2)], capacity=50)
    bay_near = LoadingBay(id="bay-near", position=(2, 3), queue=[])
    bay_far = LoadingBay(id="bay-far", position=(9, 9), queue=[])
    order = Order(
        id="ord-2",
        items=[OrderItem(sku="SKU-2", shelf_zone_id="s1", quantity=1)],
        priority=1,
        deadline=100.0,
        status=OrderStatus.PENDING,
    )

    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[bay_far, bay_near],
        pending_orders=[order],
        active_orders=[],
    )

    assert resolver.resolve_bay("ord-2", warehouse).id == "bay-near"


def test_resolve_conveyor_path_returns_targeted_segments():
    resolver = TaskResolver()
    env = simpy.Environment()
    grid = Grid(20, 20, env)
    shelf = ShelfZone(id="s1", positions=[(1, 1)], capacity=50)
    conveyors = [
        ConveyorSegment(id="c-start", positions=[(1, 0)], direction="E", speed=1.0),
        ConveyorSegment(id="c-mid", positions=[(10, 10)], direction="E", speed=1.0),
        ConveyorSegment(id="c-end", positions=[(18, 19)], direction="E", speed=1.0),
    ]

    warehouse = WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=conveyors,
        bays=[],
        pending_orders=[],
        active_orders=[],
    )

    path = resolver.resolve_conveyor_path((0, 0), (19, 19), warehouse)
    ids = [seg.id for seg in path]
    assert ids == ["c-start", "c-end"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])