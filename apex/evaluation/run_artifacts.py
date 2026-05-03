"""Discover and load persisted evaluation run directories (metrics, manifest, events)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apex.evaluation.metrics import EpisodeMetrics

_RUN_MANIFEST = "run_manifest.json"
_METRICS = "metrics.json"
_EVENTS = "events.jsonl"
_EVENT_TAIL_MAX = 500
_NARRATIVE_CAP = 100


@dataclass(frozen=True)
class RunSummary:
    """One subdirectory under a runs root that may contain evaluation artifacts."""

    run_id: str
    path: Path
    mtime: float
    has_manifest: bool
    has_metrics: bool
    has_events: bool
    has_video: bool
    scenario_id: str | None
    seed: int | None


def resolve_runs_root(path: str | Path) -> Path:
    """Return an absolute, existing directory path for the runs root."""
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"Runs root is not a directory: {p}")
    return p


def _is_safe_run_segment(run_id: str) -> bool:
    if not run_id or run_id in (".", ".."):
        return False
    if "/" in run_id or "\\" in run_id:
        return False
    return True


def safe_run_dir(runs_root: Path, run_id: str) -> Path:
    """Resolve ``runs_root / run_id`` and ensure it stays under ``runs_root``."""
    if not _is_safe_run_segment(run_id):
        raise ValueError(f"Invalid run id: {run_id!r}")
    root = runs_root.resolve()
    candidate = (root / run_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError(f"Run path escapes runs root: {run_id!r}") from e
    return candidate


def _video_present(run_dir: Path) -> bool:
    vdir = run_dir / "videos"
    if not vdir.is_dir():
        return False
    return any(vdir.glob("*.mp4"))


def _manifest_brief(manifest_path: Path) -> tuple[str | None, int | None]:
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    scen = raw.get("scenario") if isinstance(raw, dict) else None
    if not isinstance(scen, dict):
        return None, None
    sid = scen.get("id")
    seed = scen.get("seed")
    sid_s = str(sid) if sid is not None else None
    seed_i: int | None
    try:
        seed_i = int(seed) if seed is not None else None
    except (TypeError, ValueError):
        seed_i = None
    return sid_s, seed_i


def iter_run_dirs(runs_root: Path) -> list[RunSummary]:
    """List immediate subdirectories of ``runs_root``, newest by mtime first."""
    root = runs_root.resolve()
    summaries: list[RunSummary] = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return []
    for child in entries:
        if not child.is_dir():
            continue
        run_id = child.name
        try:
            stat = child.stat()
        except OSError:
            continue
        mtime = float(stat.st_mtime)
        has_m = (child / _RUN_MANIFEST).is_file()
        has_met = (child / _METRICS).is_file()
        has_e = (child / _EVENTS).is_file()
        sid, seed = _manifest_brief(child / _RUN_MANIFEST) if has_m else (None, None)
        summaries.append(
            RunSummary(
                run_id=run_id,
                path=child,
                mtime=mtime,
                has_manifest=has_m,
                has_metrics=has_met,
                has_events=has_e,
                has_video=_video_present(child),
                scenario_id=sid,
                seed=seed,
            )
        )
    summaries.sort(key=lambda s: s.mtime, reverse=True)
    return summaries


def load_run_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / _RUN_MANIFEST
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_metrics(run_dir: Path) -> EpisodeMetrics:
    path = run_dir / _METRICS
    if not path.is_file():
        raise FileNotFoundError(path)
    return EpisodeMetrics.model_validate_json(path.read_text(encoding="utf-8"))


def summarize_events_jsonl(
    path: Path,
    *,
    tail_max: int = _EVENT_TAIL_MAX,
    narrative_cap: int = _NARRATIVE_CAP,
) -> dict[str, Any]:
    """Single streaming pass: per-type counts, time range, narrative slices, tail preview."""
    counts: dict[str, int] = {}
    t_min: float | None = None
    t_max: float | None = None
    orders_completed: list[dict[str, Any]] = []
    disruptions: list[dict[str, Any]] = []
    replans: list[dict[str, Any]] = []
    escalations: list[dict[str, Any]] = []
    executed_conflicts: list[dict[str, Any]] = []
    lines_for_tail: list[str] = []
    line_no = 0

    def bump_time(payload: dict[str, Any]) -> None:
        nonlocal t_min, t_max
        if "time" not in payload or payload["time"] is None:
            return
        try:
            t = float(payload["time"])
        except (TypeError, ValueError):
            return
        t_min = t if t_min is None else min(t_min, t)
        t_max = t if t_max is None else max(t_max, t)

    with path.open(encoding="utf-8") as f:
        for line in f:
            line_no += 1
            line = line.strip()
            if not line:
                continue
            if len(lines_for_tail) >= tail_max:
                lines_for_tail.pop(0)
            lines_for_tail.append(line)

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                counts["_unparseable"] = counts.get("_unparseable", 0) + 1
                continue
            et = obj.get("type")
            data = obj.get("data")
            if not isinstance(et, str):
                counts["_missing_type"] = counts.get("_missing_type", 0) + 1
                continue
            if not isinstance(data, dict):
                data = {}
            counts[et] = counts.get(et, 0) + 1
            bump_time(data)

            if et == "order_completed" and len(orders_completed) < narrative_cap:
                orders_completed.append(
                    {
                        "order_id": data.get("order_id"),
                        "time": data.get("time"),
                    }
                )
            elif et == "disruption" and len(disruptions) < narrative_cap:
                disruptions.append(
                    {
                        "time": data.get("time"),
                        "kind": data.get("kind"),
                    }
                )
            elif et == "strategic_replan" and len(replans) < narrative_cap:
                replans.append({"time": data.get("time"), "reason": data.get("reason")})
            elif et == "escalation" and len(escalations) < narrative_cap:
                escalations.append({"time": data.get("time"), "reason": data.get("reason")})
            elif et == "executed_conflict" and len(executed_conflicts) < narrative_cap:
                executed_conflicts.append(
                    {
                        "time": data.get("time"),
                        "cell": data.get("cell"),
                        "agent_a": data.get("agent_a"),
                        "agent_b": data.get("agent_b"),
                    }
                )

    tail_parsed: list[dict[str, Any]] = []
    for ln in lines_for_tail:
        try:
            tail_parsed.append(json.loads(ln))
        except json.JSONDecodeError:
            tail_parsed.append({"type": "_unparseable", "data": {}})

    return {
        "line_count": line_no,
        "counts": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "time_min": t_min,
        "time_max": t_max,
        "orders_completed": orders_completed,
        "disruptions": disruptions,
        "strategic_replans": replans,
        "escalations": escalations,
        "executed_conflicts": executed_conflicts,
        "tail_events": tail_parsed,
    }


def list_mp4_videos(run_dir: Path) -> list[Path]:
    vdir = run_dir / "videos"
    if not vdir.is_dir():
        return []
    return sorted(vdir.glob("*.mp4"))
