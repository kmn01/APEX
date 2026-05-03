"""Tests for telemetry aggregation helpers."""

from apex.evaluation.metrics import (
    MetricsCollector,
    count_pairwise_spacetime_conflicts,
    manhattan_path_cells,
)


def test_manhattan_path_endpoints():
    p = manhattan_path_cells((0, 0), (2, 1))
    assert p[0] == (0, 0)
    assert p[-1] == (2, 1)


def test_spacetime_conflict_counts_cross():
    paths = {"a": [(0, 0), (1, 0)], "b": [(1, 0), (1, 0)]}
    assert count_pairwise_spacetime_conflicts(paths) >= 1


def test_metrics_collector_folds_rates():
    mc = MetricsCollector()
    mc.record_event("episode_started", {"horizon": 120.0})
    for _ in range(4):
        mc.record_event("task_instruction_scheduled", {"time": 0.0})
    for _ in range(4):
        mc.record_event("task_instruction_completed", {"time": 10.0})
    mc.record_event("order_activated", {"order_id": "o1", "time": 2.0})
    mc.record_event("order_completed", {"order_id": "o1", "time": 62.0})
    mc.record_event("agent_busy_tick", {"agent_id": "x", "duration": 40.0, "kind": "MOVE"})
    mc.record_event("agent_idle_tick", {"agent_id": "x", "duration": 20.0})
    mc.record_event("planned_spacetime_conflict_total", {"count": 2})
    m = mc.compute_episode_metrics()
    assert m.scheduled_instruction_count == 4
    assert m.completed_instruction_count == 4
    assert m.task_completion_rate == 1.0
    assert m.planned_spacetime_conflict_count == 2
    assert m.mean_time_to_completion == 60.0
