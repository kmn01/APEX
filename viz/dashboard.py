#!/usr/bin/env python3
"""Local web dashboard for APEX evaluation runs under a directory (e.g. ./runs).

Requires optional dependencies::

    pip install -e ".[dashboard]"
    python viz/dashboard.py --runs runs

Then open the printed URL in a browser.
"""

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

_VIZ_DIR = Path(__file__).resolve().parent


def _configure_templates() -> Any:
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory=str(_VIZ_DIR / "templates"))

    def fmt_ts(ts: float) -> str:
        return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

    def pathquote(s: str) -> str:
        return quote(str(s), safe="")

    templates.env.filters["fmt_ts"] = fmt_ts
    templates.env.filters["pathquote"] = pathquote
    return templates


def _scenario_run_snippet(manifest: dict[str, Any]) -> dict[str, Any]:
    scen = manifest.get("scenario")
    if not isinstance(scen, dict):
        return {}
    run = scen.get("run")
    if not isinstance(run, dict):
        run = {}
    return {
        "scenario_id": scen.get("id"),
        "seed": scen.get("seed"),
        "horizon": scen.get("horizon"),
        "coordination": run.get("coordination"),
        "planning_mode": run.get("planning_mode"),
        "strategic_replan": run.get("strategic_replan"),
    }


def create_app(*, runs_root: Path) -> Any:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse

    from apex.evaluation.metrics import EpisodeMetrics
    from apex.evaluation.run_artifacts import (
        iter_run_dirs,
        list_mp4_videos,
        load_metrics,
        load_run_manifest,
        safe_run_dir,
        summarize_events_jsonl,
    )
    from apex.evaluation.run_digest import (
        build_scenario_digest,
        build_timeline,
        cap_raw_scenario_json,
        consistency_hints,
        metric_rows_by_group,
    )

    templates = _configure_templates()
    root = runs_root.resolve()

    app = FastAPI(title="APEX runs dashboard")
    app.state.runs_root = root

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Any:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"runs_root": str(root)},
        )

    @app.get("/partials/runs", response_class=HTMLResponse)
    async def partial_runs(request: Request) -> Any:
        runs = iter_run_dirs(app.state.runs_root)
        return templates.TemplateResponse(
            request,
            "_runs_partial.html",
            {"runs": runs},
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_detail(request: Request, run_id: str) -> Any:
        try:
            run_dir = safe_run_dir(app.state.runs_root, run_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not run_dir.is_dir():
            raise HTTPException(status_code=404, detail="Run not found")

        manifest: dict[str, Any] | None = None
        if (run_dir / "run_manifest.json").is_file():
            try:
                manifest = load_run_manifest(run_dir)
            except (OSError, json.JSONDecodeError):
                manifest = None

        m = manifest or {}
        snippet = _scenario_run_snippet(m)
        scen_dict = m.get("scenario") if isinstance(m.get("scenario"), dict) else None
        scenario_digest = build_scenario_digest(scen_dict)
        scenario_raw, scenario_raw_truncated = cap_raw_scenario_json(scen_dict)

        cli = None
        cli_json = ""
        if isinstance(m.get("extra"), dict):
            ex = m["extra"]
            if isinstance(ex.get("cli"), dict):
                cli = ex["cli"]
                cli_json = json.dumps(cli, indent=2)

        metrics_obj: EpisodeMetrics | None = None
        metric_groups: list[dict[str, Any]] | None = None
        if (run_dir / "metrics.json").is_file():
            try:
                metrics_obj = load_metrics(run_dir)
                metric_groups = metric_rows_by_group(metrics_obj)
            except Exception:
                metrics_obj = None
                metric_groups = None

        event_summary = None
        tail_json = ""
        has_events = (run_dir / "events.jsonl").is_file()
        if has_events:
            try:
                event_summary = summarize_events_jsonl(run_dir / "events.jsonl")
                tail_json = json.dumps(event_summary.get("tail_events", []), indent=2)
            except OSError:
                event_summary = None

        timeline = build_timeline(event_summary) if event_summary else []
        consistency: list[str] = []
        if metrics_obj is not None and event_summary is not None:
            consistency = consistency_hints(metrics_obj, event_summary)

        videos = list_mp4_videos(run_dir)

        return templates.TemplateResponse(
            request,
            "run_detail.html",
            {
                "runs_root": str(root),
                "run_id": run_id,
                "snippet": snippet,
                "scenario_digest": scenario_digest,
                "scenario_raw": scenario_raw,
                "scenario_raw_truncated": scenario_raw_truncated,
                "cli": cli,
                "cli_json": cli_json,
                "metric_groups": metric_groups,
                "event_summary": event_summary,
                "tail_json": tail_json,
                "has_events": has_events,
                "timeline": timeline,
                "consistency": consistency,
                "videos": videos,
            },
        )

    @app.get("/media/{run_id}/{filename}")
    async def media_file(run_id: str, filename: str) -> Any:
        if "/" in filename or "\\" in filename or not filename.endswith(".mp4"):
            raise HTTPException(status_code=404, detail="Invalid file")
        try:
            run_dir = safe_run_dir(app.state.runs_root, run_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        path = run_dir / "videos" / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type="video/mp4", filename=filename)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="APEX runs dashboard (FastAPI + HTMX)")
    parser.add_argument(
        "--runs",
        type=Path,
        default=Path("runs"),
        help="Directory containing run subfolders (default: ./runs)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8765, help="TCP port")
    args = parser.parse_args()

    try:
        runs_root = Path(args.runs).expanduser().resolve()
        if not runs_root.is_dir():
            runs_root.mkdir(parents=True, exist_ok=True)
        runs_root = runs_root.resolve()
    except OSError as e:
        print(f"Cannot use runs directory: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        print(
            "Missing dependencies. Install with: pip install -e '.[dashboard]'",
            file=sys.stderr,
        )
        sys.exit(1)

    app = create_app(runs_root=runs_root)
    print(f"APEX runs dashboard → http://{args.host}:{args.port}/  (runs root: {runs_root})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
