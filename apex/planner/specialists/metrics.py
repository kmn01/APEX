"""Counters for MAP / Gemini planner reliability and rollout observability."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MapReliabilityMetrics(BaseModel):
    """Lightweight metrics (increment from :class:`~apex.planner.coordinator.StrategicCoordinator`)."""

    map_plan_invocations: int = 0
    map_plan_successes: int = 0
    map_plan_fallbacks: int = 0
    map_plan_shadow_proposals: int = 0

    map_replan_invocations: int = 0
    map_replan_successes: int = 0
    map_replan_fallbacks: int = 0
    map_replan_shadow_proposals: int = 0

    # pass^k-style hooks: caller can snapshot graph hashes across repeated runs
    plan_run_hashes: list[str] = Field(default_factory=list)

    def record_plan_run_hash(self, graph_hash: str) -> None:
        """Append a stable fingerprint of a returned plan (e.g. SHA256 of canonical JSON)."""
        self.plan_run_hashes.append(graph_hash)
