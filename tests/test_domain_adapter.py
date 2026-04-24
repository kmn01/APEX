"""Tests for M4 Domain Adapter."""

import pytest
import simpy

from apex.adapter.resolver import TaskResolver
from apex.adapter.translator import AbstractTask, DomainTranslator
from apex.simulation.grid import Grid
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])