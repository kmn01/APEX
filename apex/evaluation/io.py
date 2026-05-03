"""Persist metrics, manifests, and raw event traces from evaluation runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from apex.evaluation.metrics import EpisodeMetrics, MetricsCollector


def _git_revision() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).resolve().parents[2],
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except OSError:
        pass
    return None


def scenario_fingerprint(obj: BaseModel) -> str:
    blob = json.dumps(obj.model_dump(mode="json"), sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def write_run_directory(
    output_dir: str | Path,
    *,
    scenario: BaseModel,
    metrics: EpisodeMetrics,
    collector: MetricsCollector,
    extra_manifest: dict[str, Any] | None = None,
) -> Path:
    """Write ``metrics.json``, ``events.jsonl``, and ``run_manifest.json`` under ``output_dir``."""
    od = Path(output_dir)
    od.mkdir(parents=True, exist_ok=True)

    metrics_path = od / "metrics.json"
    metrics_path.write_text(metrics.model_dump_json(indent=2), encoding="utf-8")

    events_path = od / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as f:
        for et, data in collector.iter_events():
            f.write(json.dumps({"type": et, "data": data}, sort_keys=True) + "\n")

    manifest = {
        "apex_version": getattr(sys.modules.get("apex"), "__version__", "0.0.0"),
        "python": sys.version.split()[0],
        "git_revision": _git_revision(),
        "scenario_fingerprint": scenario_fingerprint(scenario),
        "scenario": scenario.model_dump(mode="json"),
    }
    if extra_manifest:
        manifest["extra"] = extra_manifest
    (od / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return od
