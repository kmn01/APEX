"""Episode-level KPI models and a collector for simulation telemetry.

Feeds :class:`~apex.evaluation.runner.ExperimentRunner` with structured
:class:`EpisodeMetrics` after discrete-event episodes complete.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EpisodeMetrics(BaseModel):
    """Scalar summary statistics for one simulation episode."""

    task_completion_rate: float = 0.0
    mean_time_to_completion: float = 0.0
    agent_idle_fraction: float = 0.0
    collision_count: int = 0
    replan_count: int = 0
    orders_per_minute: float = 0.0


class MetricsCollector:
    """Append-only event log with a terminal aggregation step."""

    def __init__(self) -> None:
        self._events: list[tuple[str, dict[str, Any]]] = []

    def __repr__(self) -> str:
        return f"MetricsCollector(events={len(self._events)})"

    def __len__(self) -> int:
        return len(self._events)

    def record_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Store a structured event for later metric computation."""
        self._events.append((event_type, data if data is not None else {}))

    def compute_episode_metrics(self) -> EpisodeMetrics:
        """Fold :attr:`_events` into :class:`EpisodeMetrics`."""
        raise NotImplementedError("TODO: aggregate counters and time series from events")


if __name__ == "__main__":
    mc = MetricsCollector()
    mc.record_event("start", {})
    print(repr(mc))
