"""Episode-level KPI models and a collector for simulation telemetry.

Event schema (``MetricsCollector.record_event``)
------------------------------------------------
All ``data`` dicts are optional unless noted.

- ``episode_started``: ``horizon``, ``scenario_id``, ``seed``
- ``order_released``: ``order_id``, ``time``
- ``order_activated``: ``order_id``, ``time``
- ``order_completed``: ``order_id``, ``time``
- ``task_instruction_scheduled``: ``agent_id``, ``action_type``, ``order_id`` (optional)
- ``task_instruction_completed``: ``agent_id``, ``action_type``, ``order_id`` (optional)
- ``disruption``: ``kind``, ``time``, extra fields per kind
- ``strategic_replan``: ``time``, ``reason`` (optional)
- ``escalation``: ``time``, ``reason`` (optional)
- ``executed_conflict``: ``time``, ``cell``, ``agent_a``, ``agent_b``
- ``agent_idle_tick``: ``agent_id``, ``duration``
- ``agent_busy_tick``: ``agent_id``, ``duration``, ``kind`` ("MOVE"|"WORK")
- ``planned_spacetime_conflict_total``: ``count``
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
    executed_conflict_count: int = 0
    planned_spacetime_conflict_count: int = 0
    replan_count: int = 0
    escalation_count: int = 0
    orders_per_minute: float = 0.0
    disruption_count: int = 0
    sim_duration: float = 0.0
    horizon: float = 0.0
    scheduled_instruction_count: int = 0
    completed_instruction_count: int = 0


class MetricsCollector:
    """Append-only event log with a terminal aggregation step."""

    def __init__(self) -> None:
        self._events: list[tuple[str, dict[str, Any]]] = []

    def __repr__(self) -> str:
        return f"MetricsCollector(events={len(self._events)})"

    def __len__(self) -> int:
        return len(self._events)

    def iter_events(self) -> list[tuple[str, dict[str, Any]]]:
        return list(self._events)

    def record_event(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Store a structured event for later metric computation."""
        self._events.append((event_type, data if data is not None else {}))

    def compute_episode_metrics(self) -> EpisodeMetrics:
        """Fold :attr:`_events` into :class:`EpisodeMetrics`."""
        horizon = 0.0
        scenario_duration = 0.0

        completions: dict[str, float] = {}
        activated: dict[str, float] = {}

        idle_by_agent: dict[str, float] = {}
        busy_by_agent: dict[str, float] = {}

        scheduled_i = 0
        completed_i = 0
        completed_order_ids: set[str] = set()

        disruptions = 0
        replans = 0
        escalations = 0
        collisions = 0
        exec_conflicts = 0
        planned_conflicts = 0

        for etype, payload in self._events:
            if etype == "episode_started":
                horizon = float(payload.get("horizon") or horizon)

            elif etype in ("order_released", "order_activated"):
                oid = payload.get("order_id")
                if oid is not None:
                    activated[str(oid)] = float(payload.get("time") or 0.0)

            elif etype == "order_completed":
                oid = str(payload["order_id"])
                t = float(payload["time"])
                completions[oid] = t
                completed_order_ids.add(oid)

            elif etype == "task_instruction_scheduled":
                scheduled_i += 1

            elif etype == "task_instruction_completed":
                completed_i += 1

            elif etype == "disruption":
                disruptions += 1

            elif etype == "strategic_replan":
                replans += 1

            elif etype == "escalation":
                escalations += 1

            elif etype == "collision":
                collisions += 1

            elif etype == "executed_conflict":
                exec_conflicts += 1

            elif etype == "planned_spacetime_conflict_total":
                planned_conflicts += int(payload.get("count") or 0)

            elif etype == "agent_idle_tick":
                aid = str(payload["agent_id"])
                idle_by_agent[aid] = idle_by_agent.get(aid, 0.0) + float(payload.get("duration") or 0)

            elif etype == "agent_busy_tick":
                aid = str(payload["agent_id"])
                busy_by_agent[aid] = busy_by_agent.get(aid, 0.0) + float(payload.get("duration") or 0)

        times: list[float] = []
        for _, payload in self._events:
            if "time" in payload and payload["time"] is not None:
                times.append(float(payload["time"]))
        if times:
            scenario_duration = max(times)

        latency_values = [
            completions[oid] - activated[oid]
            for oid in completed_order_ids
            if oid in activated and oid in completions
        ]
        mean_latency = sum(latency_values) / len(latency_values) if latency_values else 0.0

        task_rate = completed_i / scheduled_i if scheduled_i else 0.0

        all_agents = set(idle_by_agent.keys()) | set(busy_by_agent.keys())
        idle_frac_mean = 0.0
        if all_agents:
            per_agent_idle: list[float] = []
            for aid in all_agents:
                idle_t = idle_by_agent.get(aid, 0.0)
                busy_t = busy_by_agent.get(aid, 0.0)
                total_tracked = idle_t + busy_t
                if total_tracked <= 0:
                    per_agent_idle.append(1.0)
                else:
                    per_agent_idle.append(idle_t / total_tracked)
            idle_frac_mean = sum(per_agent_idle) / len(per_agent_idle)

        n_orders_finished = len(completed_order_ids)
        o_per_minute = (
            n_orders_finished / (scenario_duration / 60.0)
            if scenario_duration > 0
            else 0.0
        )

        return EpisodeMetrics(
            task_completion_rate=task_rate,
            mean_time_to_completion=mean_latency,
            agent_idle_fraction=idle_frac_mean,
            collision_count=collisions,
            executed_conflict_count=exec_conflicts,
            planned_spacetime_conflict_count=planned_conflicts,
            replan_count=replans,
            escalation_count=escalations,
            orders_per_minute=o_per_minute,
            disruption_count=disruptions,
            sim_duration=scenario_duration,
            horizon=horizon,
            scheduled_instruction_count=scheduled_i,
            completed_instruction_count=completed_i,
        )


def count_pairwise_spacetime_conflicts(
    paths: dict[str, list[tuple[int, int]]],
) -> int:
    """Count unordered pairs of space-time overlaps for unit-time grid motion.

    Each path is a list of cells at integer times t=0,1,...,len-1.
    """
    spacetime: dict[tuple[tuple[int, int], int], list[str]] = {}
    for agent_id, cells in paths.items():
        for t, pos in enumerate(cells):
            key = (pos, t)
            spacetime.setdefault(key, []).append(agent_id)

    conflicts = 0
    for agents in spacetime.values():
        if len(agents) < 2:
            continue
        n = len(agents)
        conflicts += n * (n - 1) // 2
    return conflicts


def manhattan_path_cells(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """Axis-aligned path (first rows, then cols)."""
    r0, c0 = start
    r1, c1 = goal
    cells = [start]
    r, c = r0, c0
    while r != r1:
        r += 1 if r < r1 else -1
        cells.append((r, c))
    while c != c1:
        c += 1 if c < c1 else -1
        cells.append((r, c))
    return cells


if __name__ == "__main__":
    mc = MetricsCollector()
    mc.record_event("episode_started", {"horizon": 100.0})
    mc.record_event("task_instruction_scheduled", {})
    mc.record_event("task_instruction_completed", {})
    mc.record_event("order_activated", {"order_id": "a", "time": 0.0})
    mc.record_event("order_completed", {"order_id": "a", "time": 50.0})
    mc.record_event("agent_busy_tick", {"agent_id": "p1", "duration": 30.0, "kind": "MOVE"})
    mc.record_event("agent_idle_tick", {"agent_id": "p1", "duration": 20.0})
    print(mc.compute_episode_metrics())
