"""Tests for apex.evaluation.run_digest."""

from __future__ import annotations

import json

from apex.evaluation.metrics import EpisodeMetrics
from apex.evaluation.run_digest import (
    build_repro_block,
    build_scenario_digest,
    build_timeline,
    cap_raw_scenario_json,
    consistency_hints,
    format_metric_value,
    metric_display_rows,
    metric_rows_by_group,
)


def test_build_repro_block() -> None:
    m = {
        "apex_version": "0.0.0",
        "python": "3.12",
        "git_revision": "abc",
        "scenario_fingerprint": "deadbeef",
        "scenario": {},
    }
    r = build_repro_block(m)
    assert r["git_revision"] == "abc"
    assert r["scenario_fingerprint"] == "deadbeef"


def test_build_scenario_digest_typed() -> None:
    scen = {
        "id": "demo",
        "seed": 1,
        "horizon": 100.0,
        "grid_rows": 5,
        "grid_cols": 6,
        "agents": [{"id": "p1", "row": 0, "col": 1}],
        "orders": [
            {
                "id": "o1",
                "arrival_time": 0.0,
                "deadline": 50.0,
                "priority": 1,
                "items": [{"sku": "A", "shelf_zone_id": "shelf_a", "quantity": 2}],
            }
        ],
        "disruptions": [{"time": 3.0, "kind": "shelf_block", "payload": {"shelf_id": "s1"}}],
        "shelves": [{"id": "shelf_a", "positions": [[1, 1]], "capacity": 10}],
        "bay_id": "bay_out",
        "bay_position": [4, 4],
        "run": {"coordination": "greedy_uncoordinated"},
    }
    d = build_scenario_digest(scen)
    assert d is not None
    assert d["parsed"] is True
    assert d["layout"]["grid"] == "5×6"
    assert len(d["agents"]) == 1
    assert d["agents"][0]["id"] == "p1"
    assert len(d["orders"]) == 1
    assert d["orders"][0]["first_sku"] == "A"
    assert d["disruptions"][0]["kind"] == "shelf_block"
    assert d["stochastic"]["enabled"] is False


def test_build_scenario_digest_fallback() -> None:
    scen = {"id": "bad", "grid_rows": "nope", "agents": "broken"}
    d = build_scenario_digest(scen)
    assert d is not None
    assert d["parsed"] is False
    assert "×" in d["layout"]["grid"]


def test_format_metric_value() -> None:
    assert format_metric_value("task_completion_rate", 0.5) == "50.0%"
    assert format_metric_value("horizon", 5000.0) == "5000.0s"
    assert format_metric_value("orders_per_minute", 0.25) == "0.250"


def test_metric_display_rows_order() -> None:
    m = EpisodeMetrics(
        orders_per_minute=1.0,
        mean_time_to_completion=10.0,
        task_completion_rate=0.9,
        scheduled_instruction_count=5,
        completed_instruction_count=4,
        executed_conflict_count=0,
        planned_spacetime_conflict_count=1,
        collision_count=0,
        replan_count=2,
        escalation_count=1,
        disruption_count=3,
        agent_idle_fraction=0.2,
        sim_duration=100.0,
        horizon=200.0,
    )
    rows = metric_display_rows(m)
    assert rows[0]["key"] == "orders_per_minute"
    assert rows[0]["group"] == "throughput"
    groups = metric_rows_by_group(m)
    assert len(groups) == 5
    assert groups[0]["title"] == "Throughput and orders"
    assert len(groups[0]["rows"]) == 2


def test_build_timeline_sorted() -> None:
    summary = {
        "orders_completed": [{"order_id": "a", "time": 20.0}],
        "disruptions": [{"time": 5.0, "kind": "x"}],
        "strategic_replans": [{"time": 10.0, "reason": "r"}],
        "escalations": [{"time": 15.0, "reason": "e"}],
        "executed_conflicts": [
            {"time": 7.0, "cell": [1, 1], "agent_a": "a1", "agent_b": "a2"},
        ],
    }
    tl = build_timeline(summary)
    times = [x["time"] for x in tl]
    assert times == sorted(times)
    kinds = [x["kind"] for x in tl]
    assert "executed_conflict" in kinds


def test_consistency_hints() -> None:
    m = EpisodeMetrics(replan_count=2, escalation_count=1, disruption_count=0)
    summary = {
        "counts": {
            "strategic_replan": 2,
            "escalation": 1,
            "disruption": 0,
            "order_completed": 3,
        }
    }
    hints = consistency_hints(m, summary)
    assert any("Strategic replans" in h for h in hints)
    m2 = EpisodeMetrics(replan_count=9, escalation_count=1, disruption_count=0)
    hints2 = consistency_hints(m2, summary)
    assert any("9" in h and "2" in h for h in hints2)


def test_cap_raw_scenario_json_truncation() -> None:
    big = {"id": "x", "blob": "y" * 100_000}
    text, trunc = cap_raw_scenario_json(big, max_bytes=200)
    assert trunc is True
    assert len(text.encode("utf-8")) <= 250
    small, trunc2 = cap_raw_scenario_json({"a": 1}, max_bytes=10_000)
    assert trunc2 is False
    assert json.loads(small)["a"] == 1
