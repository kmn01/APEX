"""Tests for apex.evaluation.run_artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apex.evaluation.metrics import EpisodeMetrics
from apex.evaluation.run_artifacts import (
    iter_run_dirs,
    load_metrics,
    load_run_manifest,
    resolve_runs_root,
    safe_run_dir,
    summarize_events_jsonl,
)


def test_resolve_runs_root(tmp_path: Path) -> None:
    assert resolve_runs_root(tmp_path) == tmp_path.resolve()


def test_resolve_runs_root_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        resolve_runs_root(missing)


def test_safe_run_dir_ok(tmp_path: Path) -> None:
    (tmp_path / "my_run").mkdir()
    p = safe_run_dir(tmp_path, "my_run")
    assert p.name == "my_run"
    assert p.is_dir()


def test_safe_run_dir_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        safe_run_dir(tmp_path, "..")
    with pytest.raises(ValueError):
        safe_run_dir(tmp_path, "a/b")


def test_safe_run_dir_escape(tmp_path: Path) -> None:
    (tmp_path / "legit").mkdir()
    # Symlink trick: if "evil" points outside, resolved path may escape
    # On typical setups, ".." as name is invalid before resolve
    with pytest.raises(ValueError):
        safe_run_dir(tmp_path, "")


def test_iter_run_dirs_and_manifest_brief(tmp_path: Path) -> None:
    old = tmp_path / "old_run"
    new = tmp_path / "new_run"
    old.mkdir()
    new.mkdir()
    (old / "run_manifest.json").write_text(
        json.dumps({"scenario": {"id": "sc_a", "seed": 42}}),
        encoding="utf-8",
    )
    (new / "run_manifest.json").write_text(
        json.dumps({"scenario": {"id": "sc_b", "seed": 99}}),
        encoding="utf-8",
    )
    (new / "metrics.json").write_text(
        EpisodeMetrics(sim_duration=10.0, horizon=100.0).model_dump_json(),
        encoding="utf-8",
    )
    (new / "events.jsonl").write_text("", encoding="utf-8")

    summaries = iter_run_dirs(tmp_path)
    assert len(summaries) == 2
    # new_run should be first (newer mtime)
    assert summaries[0].run_id == "new_run"
    assert summaries[0].scenario_id == "sc_b"
    assert summaries[0].seed == 99
    assert summaries[0].has_metrics is True
    assert summaries[1].run_id == "old_run"
    assert summaries[1].scenario_id == "sc_a"


def test_load_manifest_and_metrics(tmp_path: Path) -> None:
    run = tmp_path / "r1"
    run.mkdir()
    (run / "run_manifest.json").write_text(
        json.dumps({"scenario": {"id": "x"}, "extra": {"cli": {"verbose": True}}}),
        encoding="utf-8",
    )
    m = EpisodeMetrics(replan_count=3, sim_duration=5.0)
    (run / "metrics.json").write_text(m.model_dump_json(), encoding="utf-8")
    man = load_run_manifest(run)
    assert man["scenario"]["id"] == "x"
    met = load_metrics(run)
    assert met.replan_count == 3


def test_summarize_events_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "ev.jsonl"
    lines = [
        json.dumps({"type": "episode_started", "data": {"horizon": 200.0}}),
        json.dumps({"type": "order_completed", "data": {"order_id": "o1", "time": 12.0}}),
        json.dumps({"type": "disruption", "data": {"time": 5.0, "kind": "block"}}),
        json.dumps({"type": "strategic_replan", "data": {"time": 6.0, "reason": "esc"}}),
        json.dumps({"type": "escalation", "data": {"time": 7.0, "reason": "x"}}),
        json.dumps({"type": "order_completed", "data": {"order_id": "o2", "time": 20.0}}),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = summarize_events_jsonl(p, tail_max=3, narrative_cap=10)
    assert s["line_count"] == 6
    assert s["counts"]["order_completed"] == 2
    assert s["time_min"] == 5.0
    assert s["time_max"] == 20.0
    assert len(s["orders_completed"]) == 2
    assert len(s["tail_events"]) == 3
    assert s["tail_events"][-1]["type"] == "order_completed"
