"""Named scenario presets for reproducible benchmarks."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from apex.evaluation.run_config import RunConfig, StrategicReplanMode, TacticalCoordination
from apex.planner.coordinator import PlanningMode
from apex.scenarios.models import (
    AgentSpec,
    ConveyorLayoutSpec,
    DisruptionSpec,
    OrderLineSpec,
    OrderSpec,
    ScenarioSpec,
    ShelfLayoutSpec,
)


def scenario_single_order(
    *,
    coordination: TacticalCoordination = TacticalCoordination.CBS,
    planning_mode: PlanningMode = PlanningMode.HTN_ONLY,
    strategic_replan: StrategicReplanMode = StrategicReplanMode.HTN_FALLBACK,
) -> ScenarioSpec:
    return ScenarioSpec(
        id="single_order_single_agent",
        seed=42,
        horizon=3_000.0,
        grid_rows=16,
        grid_cols=16,
        shelves=[
            ShelfLayoutSpec(id="shelf_a", positions=[(4, 4)]),
            ShelfLayoutSpec(id="shelf_b", positions=[(4, 10)]),
        ],
        conveyor=ConveyorLayoutSpec(
            id="conv_main",
            positions=[(8, col) for col in range(4, 12)],
            direction="E",
            speed=2.0,
        ),
        bay_position=(14, 8),
        agents=[AgentSpec(id="picker-0", row=0, col=0)],
        orders=[
            OrderSpec(
                id="ord-0",
                arrival_time=0.0,
                items=[
                    OrderLineSpec(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1),
                    OrderLineSpec(sku="SKU-B", shelf_zone_id="shelf_b", quantity=1),
                ],
            ),
        ],
        disruptions=[],
        run=RunConfig(
            coordination=coordination,
            planning_mode=planning_mode,
            strategic_replan=strategic_replan,
            quiet=True,
        ),
    )


def scenario_two_agents_crossing(
    *,
    coordination: TacticalCoordination = TacticalCoordination.CBS,
) -> ScenarioSpec:
    """Two pickers serving two orders so the first hops are concurrent MOVE_TO."""
    return ScenarioSpec(
        id="two_agents_crossing",
        seed=1,
        horizon=5_000.0,
        grid_rows=14,
        grid_cols=14,
        shelves=[
            ShelfLayoutSpec(id="shelf_a", positions=[(2, 10)]),
            ShelfLayoutSpec(id="shelf_b", positions=[(10, 2)]),
        ],
        conveyor=ConveyorLayoutSpec(
            id="conv_main",
            positions=[(6, col) for col in range(4, 10)],
            direction="E",
            speed=2.0,
        ),
        bay_position=(12, 12),
        agents=[
            AgentSpec(id="picker-0", row=0, col=0),
            AgentSpec(id="picker-1", row=0, col=13),
        ],
        orders=[
            OrderSpec(
                id="ord-0",
                arrival_time=0.0,
                items=[OrderLineSpec(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
            ),
            OrderSpec(
                id="ord-1",
                arrival_time=0.0,
                items=[OrderLineSpec(sku="SKU-B", shelf_zone_id="shelf_b", quantity=1)],
            ),
        ],
        disruptions=[],
        run=RunConfig(
            coordination=coordination,
            planning_mode=PlanningMode.HTN_ONLY,
            strategic_replan=StrategicReplanMode.HTN_FALLBACK,
            quiet=True,
        ),
    )


# alias for YAML / docs naming
scenario_crossing_agents = scenario_two_agents_crossing


def scenario_order_queue(
    *,
    coordination: TacticalCoordination = TacticalCoordination.CBS,
) -> ScenarioSpec:
    return ScenarioSpec(
        id="order_batch_queue",
        seed=2,
        horizon=8_000.0,
        grid_rows=18,
        grid_cols=18,
        shelves=[
            ShelfLayoutSpec(id="shelf_a", positions=[(5, 5)]),
            ShelfLayoutSpec(id="shelf_b", positions=[(5, 12)]),
        ],
        conveyor=ConveyorLayoutSpec(
            id="conv_main",
            positions=[(10, c) for c in range(4, 14)],
            direction="E",
            speed=2.0,
        ),
        bay_position=(15, 9),
        agents=[
            AgentSpec(id="picker-0", row=0, col=8),
            AgentSpec(id="picker-1", row=2, col=8),
        ],
        orders=[
            OrderSpec(
                id="ord-wave-1",
                arrival_time=0.0,
                items=[OrderLineSpec(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1)],
            ),
            OrderSpec(
                id="ord-wave-2",
                arrival_time=400.0,
                items=[OrderLineSpec(sku="SKU-B", shelf_zone_id="shelf_b", quantity=1)],
            ),
            OrderSpec(
                id="ord-wave-3",
                arrival_time=900.0,
                items=[
                    OrderLineSpec(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1),
                ],
            ),
        ],
        disruptions=[],
        run=RunConfig(
            coordination=coordination,
            planning_mode=PlanningMode.HTN_ONLY,
            strategic_replan=StrategicReplanMode.HTN_FALLBACK,
            quiet=True,
        ),
    )


def scenario_shelf_recovery(
    *,
    coordination: TacticalCoordination = TacticalCoordination.CBS,
) -> ScenarioSpec:
    return ScenarioSpec(
        id="shelf_block_recovery",
        seed=3,
        horizon=6_000.0,
        grid_rows=16,
        grid_cols=16,
        shelves=[
            ShelfLayoutSpec(id="shelf_a", positions=[(4, 6)]),
            ShelfLayoutSpec(id="shelf_b", positions=[(4, 10)]),
        ],
        conveyor=ConveyorLayoutSpec(
            id="conv_main",
            positions=[(9, c) for c in range(4, 12)],
            direction="E",
            speed=2.0,
        ),
        bay_position=(14, 8),
        agents=[AgentSpec(id="picker-0", row=0, col=0)],
        orders=[
            OrderSpec(
                id="ord-0",
                arrival_time=0.0,
                items=[
                    OrderLineSpec(sku="SKU-A", shelf_zone_id="shelf_a", quantity=1),
                    OrderLineSpec(sku="SKU-B", shelf_zone_id="shelf_b", quantity=1),
                ],
            ),
        ],
        disruptions=[
            DisruptionSpec(
                time=50.0,
                kind="shelf_block",
                payload={"shelf_id": "shelf_a", "duration": 30.0},
            ),
        ],
        run=RunConfig(
            coordination=coordination,
            planning_mode=PlanningMode.HTN_ONLY,
            strategic_replan=StrategicReplanMode.HTN_FALLBACK,
            quiet=True,
        ),
    )


def scenario_injected_order(
    *,
    coordination: TacticalCoordination = TacticalCoordination.CBS,
) -> ScenarioSpec:
    return ScenarioSpec(
        id="injected_priority_order",
        seed=4,
        horizon=7_000.0,
        grid_rows=16,
        grid_cols=16,
        shelves=[
            ShelfLayoutSpec(id="shelf_a", positions=[(4, 4)]),
        ],
        conveyor=ConveyorLayoutSpec(
            id="conv_main",
            positions=[(8, col) for col in range(4, 12)],
            direction="E",
            speed=2.0,
        ),
        bay_position=(14, 8),
        agents=[AgentSpec(id="picker-0", row=0, col=0)],
        orders=[
            OrderSpec(
                id="ord-main",
                arrival_time=0.0,
                items=[OrderLineSpec(sku="SKU-A", shelf_zone_id="shelf_a", quantity=2)],
            ),
        ],
        disruptions=[
            DisruptionSpec(
                time=300.0,
                kind="inject_order",
                payload={
                    "id": "rush-1",
                    "priority": 9,
                    "items": [{"sku": "SKU-A", "shelf_zone_id": "shelf_a", "quantity": 1}],
                },
            ),
        ],
        run=RunConfig(
            coordination=coordination,
            planning_mode=PlanningMode.HTN_ONLY,
            strategic_replan=StrategicReplanMode.HTN_FALLBACK,
            quiet=True,
        ),
    )


def scenario_scale_floor(
    rows: int,
    cols: int,
    n_agents: int,
    n_orders: int,
    *,
    coordination: TacticalCoordination = TacticalCoordination.CBS,
    seed: int = 0,
) -> ScenarioSpec:
    """Scaling grid with a single shelf band and deterministic SKUs."""
    shelf_positions = [(rows // 2, max(2, cols // 6) + i * 2) for i in range(max(1, n_orders))]
    conveyor_row = rows // 2 + max(3, rows // 8)
    conv_cells = [(conveyor_row, c) for c in range(cols // 6, cols - cols // 6)]
    picks: list[ShelfLayoutSpec] = [
        ShelfLayoutSpec(id=f"shelf_{k}", positions=[shelf_positions[k % len(shelf_positions)]])
        for k in range(max(1, n_orders))
    ]
    agents = [
        AgentSpec(id=f"picker-{i}", row=i % rows, col=i % cols) for i in range(n_agents)
    ]
    orders = [
        OrderSpec(
            id=f"ord-{j}",
            arrival_time=0.0,
            items=[
                OrderLineSpec(
                    sku=f"SKU-{j}",
                    shelf_zone_id=picks[j % len(picks)].id,
                    quantity=1,
                ),
            ],
        )
        for j in range(n_orders)
    ]
    return ScenarioSpec(
        id=f"scale_{rows}x{cols}_a{n_agents}_o{n_orders}",
        seed=seed,
        horizon=20_000.0,
        grid_rows=rows,
        grid_cols=cols,
        shelves=picks,
        conveyor=ConveyorLayoutSpec(id="conv_main", positions=conv_cells, direction="E", speed=2.0),
        bay_position=(rows - 2, cols - 2),
        agents=agents,
        orders=orders,
        disruptions=[],
        run=RunConfig(
            coordination=coordination,
            planning_mode=PlanningMode.HTN_ONLY,
            strategic_replan=StrategicReplanMode.HTN_FALLBACK,
            quiet=True,
        ),
    )


SCENARIO_BUILDERS: dict[str, Callable[..., ScenarioSpec]] = {
    "single_order_single_agent": scenario_single_order,
    "two_agents_crossing": scenario_two_agents_crossing,
    "crossing_agents": scenario_crossing_agents,
    "order_batch_queue": scenario_order_queue,
    "shelf_block_recovery": scenario_shelf_recovery,
    "injected_priority_order": scenario_injected_order,
}


def build_scenario(name: str, **kwargs: object) -> ScenarioSpec:
    """Instantiate a named catalog scenario (``kwargs`` forwarded to builder)."""
    if name not in SCENARIO_BUILDERS:
        raise KeyError(f"Unknown scenario {name!r}; known: {sorted(SCENARIO_BUILDERS)}")
    fn = SCENARIO_BUILDERS[name]
    return fn(**kwargs)  # type: ignore[arg-type]


def load_scenario_from_yaml(path: str | Path) -> ScenarioSpec:
    """Load :class:`ScenarioSpec` from a YAML file (requires ``pyyaml``)."""
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("load_scenario_from_yaml requires PyYAML (pip install pyyaml)") from exc

    p = Path(path)
    raw = yaml.safe_load(p.read_text())
    return ScenarioSpec.model_validate(raw)
