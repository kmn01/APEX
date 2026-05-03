"""Human-oriented digests for persisted run manifests and metrics (runs dashboard)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from apex.evaluation.metrics import EpisodeMetrics
from apex.scenarios.models import ScenarioSpec

_RAW_SCENARIO_JSON_MAX = 64 * 1024

METRIC_LABELS: dict[str, str] = {
    "orders_per_minute": "Orders completed per minute",
    "mean_time_to_completion": "Mean order latency",
    "task_completion_rate": "Instruction completion rate",
    "scheduled_instruction_count": "Task instructions scheduled",
    "completed_instruction_count": "Task instructions completed",
    "executed_conflict_count": "Executed space-time conflicts",
    "planned_spacetime_conflict_count": "Planned CBS space-time overlaps",
    "collision_count": "Collisions (simulation)",
    "replan_count": "Strategic replans",
    "escalation_count": "Escalations to strategic layer",
    "disruption_count": "Disruption events",
    "agent_idle_fraction": "Mean agent idle time (share)",
    "sim_duration": "Simulated time span",
    "horizon": "Scenario horizon cap",
}

METRIC_HELP: dict[str, str] = {
    "orders_per_minute": "Completed orders divided by simulated wall time in minutes.",
    "mean_time_to_completion": "Average (activate → complete) time over orders that finished.",
    "task_completion_rate": "Completed instructions divided by scheduled instructions.",
    "scheduled_instruction_count": "How many concrete task instructions were queued for agents.",
    "completed_instruction_count": "How many of those instructions finished.",
    "executed_conflict_count": "Agents overlapped in the same cell at the same time during execution.",
    "planned_spacetime_conflict_count": "Pairwise space-time overlaps in planned routes (CBS-related telemetry).",
    "collision_count": "Collision events recorded in the episode log.",
    "replan_count": "Times the strategic layer replanned (e.g. after escalation).",
    "escalation_count": "Times local recovery escalated to strategic replanning.",
    "disruption_count": "Injected or stochastic disruption events in the trace.",
    "agent_idle_fraction": "Average across agents of idle time / (idle + busy) from tick aggregates.",
    "sim_duration": "Latest timestamp seen in episode telemetry (not necessarily full horizon).",
    "horizon": "Maximum simulated time configured for the scenario.",
}

METRIC_GROUPS: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "throughput",
        "Throughput and orders",
        ("orders_per_minute", "mean_time_to_completion"),
    ),
    (
        "tasks",
        "Task execution",
        (
            "task_completion_rate",
            "scheduled_instruction_count",
            "completed_instruction_count",
        ),
    ),
    (
        "conflicts",
        "Conflicts and coordination",
        (
            "executed_conflict_count",
            "planned_spacetime_conflict_count",
            "collision_count",
        ),
    ),
    (
        "planning",
        "Planning and disruptions",
        ("replan_count", "escalation_count", "disruption_count"),
    ),
    (
        "utilization",
        "Time and utilization",
        ("agent_idle_fraction", "sim_duration", "horizon"),
    ),
]


def build_repro_block(manifest: dict[str, Any]) -> dict[str, Any | None]:
    """Top-level manifest fields written by ``write_run_directory``."""
    return {
        "apex_version": manifest.get("apex_version"),
        "python": manifest.get("python"),
        "git_revision": manifest.get("git_revision"),
        "scenario_fingerprint": manifest.get("scenario_fingerprint"),
    }


def _pos_tuple(p: Any) -> tuple[int, int] | None:
    if isinstance(p, (list, tuple)) and len(p) == 2:
        try:
            return (int(p[0]), int(p[1]))
        except (TypeError, ValueError):
            return None
    return None


def _truncate_payload(payload: dict[str, Any], max_len: int = 120) -> str:
    try:
        s = json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError):
        return "{}"
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _digest_from_spec(spec: ScenarioSpec) -> dict[str, Any]:
    grid = f"{spec.grid_rows}×{spec.grid_cols}"
    bay = f"{spec.bay_id} @ {spec.bay_position[0]},{spec.bay_position[1]}"
    conv: str | None = None
    if spec.conveyor is not None:
        c = spec.conveyor
        conv = f"{c.id}: {len(c.positions)} cells, dir {c.direction}, speed {c.speed}"

    agents = [{"id": a.id, "pos": f"({a.row},{a.col})"} for a in spec.agents]

    shelves = [
        {"id": z.id, "n_cells": len(z.positions), "capacity": z.capacity} for z in spec.shelves
    ]

    orders: list[dict[str, Any]] = []
    for o in spec.orders:
        first_sku = o.items[0].sku if o.items else "—"
        orders.append(
            {
                "id": o.id,
                "arrival_time": o.arrival_time,
                "deadline": o.deadline,
                "priority": o.priority,
                "n_lines": len(o.items),
                "first_sku": first_sku,
            }
        )

    disruptions = [
        {"time": d.time, "kind": d.kind, "payload": _truncate_payload(dict(d.payload))}
        for d in spec.disruptions
    ]

    stochastic: dict[str, Any] | None = None
    if spec.stochastic_disruption:
        stochastic = {
            "enabled": True,
            "summary": _truncate_payload(dict(spec.stochastic_disruption), max_len=200),
        }
    else:
        stochastic = {"enabled": False, "summary": None}

    return {
        "parsed": True,
        "layout": {
            "grid": grid,
            "bay": bay,
            "conveyor": conv,
        },
        "agents": agents,
        "shelves": shelves,
        "orders": orders,
        "disruptions": disruptions,
        "stochastic": stochastic,
    }


def _digest_fallback(scenario: dict[str, Any]) -> dict[str, Any]:
    gr = scenario.get("grid_rows", "?")
    gc = scenario.get("grid_cols", "?")
    grid = f"{gr}×{gc}"
    bay_id = scenario.get("bay_id", "—")
    bp = _pos_tuple(scenario.get("bay_position"))
    bay = f"{bay_id} @ {bp[0]},{bp[1]}" if bp else str(bay_id)

    conv_raw = scenario.get("conveyor")
    conv: str | None = None
    if isinstance(conv_raw, dict):
        pos = conv_raw.get("positions")
        n = len(pos) if isinstance(pos, list) else "?"
        conv = f"{conv_raw.get('id', 'conveyor')}: {n} cells"

    agents: list[dict[str, Any]] = []
    for a in scenario.get("agents") or []:
        if not isinstance(a, dict):
            continue
        rid = a.get("id", "?")
        agents.append({"id": rid, "pos": f"({a.get('row','?')},{a.get('col','?')})"})

    shelves: list[dict[str, Any]] = []
    for z in scenario.get("shelves") or []:
        if not isinstance(z, dict):
            continue
        pos = z.get("positions")
        n = len(pos) if isinstance(pos, list) else 0
        shelves.append({"id": z.get("id", "?"), "n_cells": n, "capacity": z.get("capacity", "—")})

    orders: list[dict[str, Any]] = []
    for o in scenario.get("orders") or []:
        if not isinstance(o, dict):
            continue
        items = o.get("items") or []
        first = items[0] if items and isinstance(items[0], dict) else None
        first_sku = first.get("sku", "—") if first else "—"
        orders.append(
            {
                "id": o.get("id", "?"),
                "arrival_time": o.get("arrival_time", "—"),
                "deadline": o.get("deadline", "—"),
                "priority": o.get("priority", "—"),
                "n_lines": len(items) if isinstance(items, list) else 0,
                "first_sku": first_sku,
            }
        )

    disruptions: list[dict[str, Any]] = []
    for d in scenario.get("disruptions") or []:
        if not isinstance(d, dict):
            continue
        pl = d.get("payload") if isinstance(d.get("payload"), dict) else {}
        disruptions.append(
            {
                "time": d.get("time"),
                "kind": d.get("kind"),
                "payload": _truncate_payload(pl),
            }
        )

    st = scenario.get("stochastic_disruption")
    if isinstance(st, dict) and st:
        stochastic = {"enabled": True, "summary": _truncate_payload(st, max_len=200)}
    else:
        stochastic = {"enabled": False, "summary": None}

    return {
        "parsed": False,
        "layout": {"grid": grid, "bay": bay, "conveyor": conv},
        "agents": agents,
        "shelves": shelves,
        "orders": orders,
        "disruptions": disruptions,
        "stochastic": stochastic,
    }


def build_scenario_digest(scenario: dict[str, Any] | None) -> dict[str, Any] | None:
    """Structured summary for dashboard templates; returns None if scenario missing."""
    if scenario is None or not isinstance(scenario, dict):
        return None
    try:
        spec = ScenarioSpec.model_validate(scenario)
    except ValidationError:
        return _digest_fallback(scenario)
    return _digest_from_spec(spec)


def format_metric_value(key: str, value: Any) -> str:
    if value is None:
        return "—"
    if key in ("task_completion_rate", "agent_idle_fraction"):
        try:
            x = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{100.0 * x:.1f}%"
    if key in ("mean_time_to_completion", "sim_duration", "horizon"):
        try:
            x = float(value)
        except (TypeError, ValueError):
            return str(value)
        if key == "mean_time_to_completion":
            return f"{x:.1f}s"
        return f"{x:.1f}s"
    if key == "orders_per_minute":
        try:
            x = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{x:.3f}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def metric_display_rows(metrics: EpisodeMetrics) -> list[dict[str, Any]]:
    """Flat rows in METRIC_GROUPS order for templates that want a simple list."""
    rows: list[dict[str, Any]] = []
    data = metrics.model_dump()
    for group_id, _group_title, keys in METRIC_GROUPS:
        for key in keys:
            rows.append(
                {
                    "key": key,
                    "group": group_id,
                    "label": METRIC_LABELS.get(key, key),
                    "value": format_metric_value(key, data.get(key)),
                    "help": METRIC_HELP.get(key, ""),
                }
            )
    return rows


def metric_rows_by_group(metrics: EpisodeMetrics) -> list[dict[str, Any]]:
    """[{group_id, title, rows: [...]}, ...] for sectioned templates."""
    data = metrics.model_dump()
    out: list[dict[str, Any]] = []
    for group_id, group_title, keys in METRIC_GROUPS:
        rows = []
        for key in keys:
            rows.append(
                {
                    "key": key,
                    "label": METRIC_LABELS.get(key, key),
                    "value": format_metric_value(key, data.get(key)),
                    "help": METRIC_HELP.get(key, ""),
                }
            )
        out.append({"group_id": group_id, "title": group_title, "rows": rows})
    return out


def _time_or_none(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build_timeline(event_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Merge narrative slices from ``summarize_events_jsonl`` and sort by time."""
    if not event_summary:
        return []
    items: list[dict[str, Any]] = []

    for o in event_summary.get("orders_completed") or []:
        t = _time_or_none(o.get("time"))
        if t is None:
            continue
        oid = o.get("order_id", "?")
        items.append({"time": t, "kind": "order_completed", "summary": f"Order {oid} completed"})

    for d in event_summary.get("disruptions") or []:
        t = _time_or_none(d.get("time"))
        if t is None:
            continue
        kind = d.get("kind", "?")
        items.append({"time": t, "kind": "disruption", "summary": f"Disruption: {kind}"})

    for r in event_summary.get("strategic_replans") or []:
        t = _time_or_none(r.get("time"))
        if t is None:
            continue
        reason = r.get("reason") or "—"
        items.append({"time": t, "kind": "strategic_replan", "summary": f"Strategic replan ({reason})"})

    for e in event_summary.get("escalations") or []:
        t = _time_or_none(e.get("time"))
        if t is None:
            continue
        reason = e.get("reason") or "—"
        items.append({"time": t, "kind": "escalation", "summary": f"Escalation: {reason}"})

    for x in event_summary.get("executed_conflicts") or []:
        t = _time_or_none(x.get("time"))
        if t is None:
            continue
        cell = x.get("cell")
        a1 = x.get("agent_a", "?")
        a2 = x.get("agent_b", "?")
        items.append(
            {
                "time": t,
                "kind": "executed_conflict",
                "summary": f"Conflict at {cell}: {a1} vs {a2}",
            }
        )

    items.sort(key=lambda it: (it["time"], it["kind"]))
    return items


def consistency_hints(metrics: EpisodeMetrics, event_summary: dict[str, Any] | None) -> list[str]:
    """Compare folded metrics to event counts where possible."""
    hints: list[str] = []
    if not event_summary:
        hints.append("No event summary available; run events.jsonl through summarizer for checks.")
        return hints

    counts = event_summary.get("counts") or {}
    if not isinstance(counts, dict):
        return hints

    def n(name: str) -> int:
        v = counts.get(name, 0)
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    # Prefer full counts from JSONL; narrative lists are capped.
    sr = n("strategic_replan")
    if metrics.replan_count == sr:
        hints.append(f"Strategic replans: metrics ({metrics.replan_count}) matches event count ({sr}).")
    else:
        hints.append(
            f"Strategic replans: metrics reports {metrics.replan_count} but "
            f"events list {sr} strategic_replan rows (investigate if traces diverge)."
        )

    esc = n("escalation")
    if metrics.escalation_count == esc:
        hints.append(f"Escalations: metrics ({metrics.escalation_count}) matches event count ({esc}).")
    else:
        hints.append(
            f"Escalations: metrics reports {metrics.escalation_count} vs {esc} escalation events."
        )

    dis = n("disruption")
    if metrics.disruption_count == dis:
        hints.append(f"Disruptions: metrics ({metrics.disruption_count}) matches event count ({dis}).")
    else:
        hints.append(
            f"Disruptions: metrics reports {metrics.disruption_count} vs {dis} disruption events."
        )

    oc = n("order_completed")
    hints.append(
        f"Orders completed in trace: {oc} order_completed events "
        f"(mean latency in metrics uses activated→completed pairs only)."
    )

    hints.append(
        "Narrative lists (orders, disruptions, replans, conflicts) in the event panel are capped; "
        "use counts and tail for full traces."
    )
    return hints


def cap_raw_scenario_json(scenario: dict[str, Any] | None, max_bytes: int = _RAW_SCENARIO_JSON_MAX) -> tuple[str, bool]:
    """Return pretty-printed JSON and whether output was truncated."""
    if scenario is None:
        return "", False
    try:
        raw = json.dumps(scenario, indent=2, default=str)
    except (TypeError, ValueError):
        return "{}", False
    b = raw.encode("utf-8")
    if len(b) <= max_bytes:
        return raw, False
    cut = raw.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    return cut + "\n… truncated …", True
