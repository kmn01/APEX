"""Pydantic models for MAP specialist I/O and planning context snapshots."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from apex.planner.graph_delta import TaskGraphDelta
from apex.planner.htn.planner import TaskGraph
from apex.tactical.replanner import EscalationSignal


class OrderSummary(BaseModel):
    """Compact order view for LLM prompts."""

    order_id: str
    priority: int
    deadline: float
    item_count: int
    skus: list[str] = Field(default_factory=list)


class WarehouseSummary(BaseModel):
    """Compact warehouse view for LLM prompts."""

    shelf_zone_ids: list[str] = Field(default_factory=list)
    bay_ids: list[str] = Field(default_factory=list)
    conveyor_count: int = 0


class FleetSummary(BaseModel):
    """Agent capability summary."""

    agent_id: str
    roles: list[str] = Field(default_factory=list)


class PlanningContext(BaseModel):
    """Context for initial ``plan`` MAP pass."""

    orders: list[OrderSummary] = Field(default_factory=list)
    warehouse: WarehouseSummary = Field(default_factory=WarehouseSummary)
    fleet: list[FleetSummary] = Field(default_factory=list)
    baseline_graph: TaskGraph
    notes: str = ""


class ReplanContext(BaseModel):
    """Context for ``replan`` MAP pass."""

    escalation: EscalationSignal
    current_graph: TaskGraph
    warehouse: WarehouseSummary = Field(default_factory=WarehouseSummary)
    fleet: list[FleetSummary] = Field(default_factory=list)
    notes: str = ""


class DecompositionOutput(BaseModel):
    """Structured output from the decomposition specialist."""

    subgoals: list[str] = Field(default_factory=list)
    method_ranking: list[str] = Field(default_factory=list)
    rationale: str = ""


class StatePredictionOutput(BaseModel):
    """Risk / state prediction specialist."""

    task_risk: dict[str, float] = Field(default_factory=dict)
    predicted_bottlenecks: list[str] = Field(default_factory=list)
    rationale: str = ""


class MonitoringOutput(BaseModel):
    """Critique / monitoring specialist."""

    issues: list[str] = Field(default_factory=list)
    severity: str = "low"  # low | medium | high
    suggested_remove_task_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class CoordinationOutput(BaseModel):
    """Final merge proposal as a graph delta (validated separately)."""

    delta: TaskGraphDelta = Field(default_factory=TaskGraphDelta)
    rationale: str = ""


class SpecialistTrace(BaseModel):
    """One MAP pipeline run for logging and reliability metrics."""

    decomposition: DecompositionOutput | None = None
    prediction: StatePredictionOutput | None = None
    monitoring: MonitoringOutput | None = None
    coordination: CoordinationOutput | None = None
    raw_errors: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    debug: dict[str, Any] = Field(default_factory=dict)
