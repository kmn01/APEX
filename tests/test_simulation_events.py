"""Tests for stochastic simulation events."""

import simpy

from apex.simulation.events import StochasticEventGenerator
from apex.simulation.grid import Grid
from apex.simulation.warehouse import LoadingBay, ShelfZone, WarehouseState


def _build_warehouse(env: simpy.Environment) -> WarehouseState:
    grid = Grid(10, 10, env)
    shelf = ShelfZone(id="shelf_a", positions=[(1, 1)], capacity=20)
    bay = LoadingBay(id="bay_out", position=(9, 9))
    return WarehouseState(
        grid=grid,
        shelf_zones=[shelf],
        conveyors=[],
        bays=[bay],
        pending_orders=[],
        active_orders=[],
    )


def test_shelf_block_event_restores_capacity_after_duration():
    env = simpy.Environment()
    warehouse = _build_warehouse(env)
    generator = StochasticEventGenerator(env, warehouse, {"block_duration": 3.0})
    shelf = warehouse.get_shelf("shelf_a")
    original_capacity = shelf.capacity

    env.process(generator._shelf_block_event())
    env.run(until=0.1)
    assert shelf.capacity < original_capacity

    env.run(until=3.2)
    assert shelf.capacity == original_capacity


def test_run_schedules_shelf_block_process():
    env = simpy.Environment()
    warehouse = _build_warehouse(env)
    generator = StochasticEventGenerator(
        env,
        warehouse,
        {
            "disruption_rate": 10.0,
            "agent_failure_rate": 0.0,
            "shelf_block_rate": 1.0,
            "new_order_rate": 0.0,
            "block_duration": 1.0,
        },
    )
    shelf = warehouse.get_shelf("shelf_a")
    original_capacity = shelf.capacity

    class _FakeRng:
        def __init__(self) -> None:
            self._calls = 0

        def exponential(self, _scale: float) -> float:
            self._calls += 1
            return 0.1 if self._calls == 1 else 100.0

        def choice(self, values, *_, **_kwargs):
            if isinstance(values, list) and values and hasattr(values[0], "capacity"):
                return values[0]
            return "shelf_block"

    generator.rng = _FakeRng()

    env.process(generator.run())
    env.run(until=0.2)
    assert generator.events_generated >= 1
    assert shelf.capacity < original_capacity

    env.run(until=1.3)
    assert shelf.capacity == original_capacity
