"""Typed scenario specifications for evaluation episodes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from apex.evaluation.run_config import RunConfig


class AgentSpec(BaseModel):
    id: str
    row: int
    col: int


class OrderLineSpec(BaseModel):
    sku: str
    shelf_zone_id: str
    quantity: int = 1


class OrderSpec(BaseModel):
    id: str
    arrival_time: float = 0.0
    priority: int = 1
    deadline: float = 10_000.0
    items: list[OrderLineSpec] = Field(default_factory=list)


DisruptionKind = Literal[
    "shelf_block",
    "shelf_unblock",
    "inject_order",
    "agent_fail",
    "new_priority",
]


class DisruptionSpec(BaseModel):
    time: float
    kind: DisruptionKind
    payload: dict[str, Any] = Field(default_factory=dict)


class ShelfLayoutSpec(BaseModel):
    id: str
    positions: list[tuple[int, int]]
    capacity: int = 100


class ConveyorLayoutSpec(BaseModel):
    id: str = "conv_main"
    positions: list[tuple[int, int]]
    direction: str = "E"
    speed: float = 2.0


class ScenarioSpec(BaseModel):
    """Static layout, orders, scripted disruptions, and driver parameters."""

    id: str
    seed: int = 0
    horizon: float = 5_000.0
    grid_rows: int = 20
    grid_cols: int = 20

    agents: list[AgentSpec] = Field(default_factory=list)
    shelves: list[ShelfLayoutSpec] = Field(default_factory=list)
    conveyor: ConveyorLayoutSpec | None = None
    bay_id: str = "bay_out"
    bay_position: tuple[int, int] = (15, 15)

    shelf_zone_ids: list[str] = Field(
        default_factory=lambda: ["shelf_a", "shelf_b"],
        description="Legacy default shelf ids when shelves list is empty.",
    )

    orders: list[OrderSpec] = Field(default_factory=list)
    disruptions: list[DisruptionSpec] = Field(default_factory=list)

    stochastic_disruption: dict[str, Any] | None = Field(
        default=None,
        description="If set, enables StochasticEventGenerator with this config dict.",
    )

    run: RunConfig = Field(default_factory=RunConfig)
