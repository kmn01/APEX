"""HTN operator definitions with symbolic preconditions and effects.

Operators are building blocks for decomposition: each :class:`HTNOperator`
records estimates used by search and metrics. :data:`BUILT_IN_OPERATORS` seeds
standard warehouse primitives (pick, transport, stage, etc.).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Canonical abstract task families in the HTN domain."""

    PICK = "PICK"
    TRANSPORT = "TRANSPORT"
    STAGE = "STAGE"
    STORE = "STORE"
    DISPATCH = "DISPATCH"


class HTNOperator(BaseModel):
    """A primitive operator usable at the leaves of an HTN plan."""

    name: str
    preconditions: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    cost_estimate: float = 1.0


def _op(
    name: str,
    pre: list[str],
    eff: list[str],
    cost: float,
) -> HTNOperator:
    return HTNOperator(name=name, preconditions=pre, effects=eff, cost_estimate=cost)


BUILT_IN_OPERATORS: dict[str, HTNOperator] = {
    "pick_item": _op("pick_item", ["at_shelf", "sku_available"], ["sku_held"], 2.0),
    "transport_to_conveyor": _op(
        "transport_to_conveyor",
        ["sku_held", "path_clear"],
        ["sku_on_conveyor"],
        4.0,
    ),
    "stage_at_sort": _op("stage_at_sort", ["sku_on_conveyor"], ["sku_staged"], 3.0),
    "store_in_buffer": _op("store_in_buffer", ["sku_staged"], ["sku_buffered"], 2.5),
    "dispatch_to_bay": _op(
        "dispatch_to_bay",
        ["sku_buffered", "bay_open"],
        ["order_complete"],
        3.5,
    ),
}


if __name__ == "__main__":
    print(repr(BUILT_IN_OPERATORS["pick_item"]))
