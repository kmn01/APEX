"""HTN methods describing how compound tasks decompose into subtasks.

Each :class:`HTNMethod` names an applicability check (by function name string)
that the planner will resolve at runtime. :data:`BUILT_IN_METHODS` captures a
baseline ``fulfill_order`` style decomposition.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from apex.planner.htn.operators import TaskType


class HTNMethod(BaseModel):
    """Compound-task decomposition pattern."""

    name: str
    task: str
    subtask_types: list[TaskType] = Field(default_factory=list)
    applicability_check_fn: str = "always_true"
    priority: int = 0


BUILT_IN_METHODS: list[HTNMethod] = [
    HTNMethod(
        name="fulfill_order_standard",
        task="fulfill_order",
        subtask_types=[
            TaskType.PICK,
            TaskType.TRANSPORT,
            TaskType.STAGE,
            TaskType.DISPATCH,
        ],
        applicability_check_fn="order_items_available",
        priority=0,
    ),
    HTNMethod(
        name="fulfill_order_direct_bay",
        task="fulfill_order",
        subtask_types=[TaskType.PICK, TaskType.TRANSPORT, TaskType.DISPATCH],
        applicability_check_fn="bay_adjacent_to_pick",
        priority=10,
    ),
]


if __name__ == "__main__":
    print(repr(BUILT_IN_METHODS[0]))
