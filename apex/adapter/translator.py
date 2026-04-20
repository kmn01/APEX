"""Translate abstract HTN tasks into concrete tactical instructions.

Maps planner :class:`AbstractTask` nodes to :class:`ConcreteInstruction`
sequences understood by the tactical executor and CBS layer, using live
:class:`~apex.simulation.warehouse.WarehouseState` for grounding.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AbstractTask(BaseModel):
    """Planner-side task with hints for domain binding."""

    task_type: str
    item_sku: str | None = None
    zone_hint: str | None = None
    priority: int = 0


class ConcreteInstruction(BaseModel):
    """Grounded instruction with explicit resource ids."""

    agent_id: str
    action_sequence: list[str] = Field(default_factory=list)
    shelf_id: str | None = None
    conveyor_id: str | None = None
    bay_id: str | None = None


class DomainTranslator:
    """Applies resolver logic to build concrete instruction payloads."""

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return "DomainTranslator()"

    def translate(self, task: AbstractTask, warehouse_state: Any) -> ConcreteInstruction:
        """Ground ``task`` using current warehouse layout and inventory."""
        raise NotImplementedError("TODO: combine TaskResolver + action templates")


if __name__ == "__main__":
    t = AbstractTask(task_type="PICK", item_sku="sku-1")
    print(repr(t))
