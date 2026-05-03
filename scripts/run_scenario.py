#!/usr/bin/env python3
"""Run catalog or YAML scenarios with JSON/JSONL artifacts.

Example:

  python scripts/run_scenario.py --scenario two_agents_crossing --output runs/demo1

  python scripts/run_scenario.py --scenario two_agents_crossing --output runs/demo \
    --record-video

  python scripts/run_scenario.py --yaml apex/scenarios/data/single_order.yaml --output runs/demo2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apex.evaluation.episode_driver import EpisodeDriver
from apex.evaluation.io import write_run_directory
from apex.evaluation.metrics import MetricsCollector
from apex.evaluation.run_config import TacticalCoordination
from apex.planner.coordinator import PlanningMode
from apex.scenarios.catalog import SCENARIO_BUILDERS, build_scenario, load_scenario_from_yaml
from apex.scenarios.models import ScenarioSpec


def _merge_run_flags(
    spec: ScenarioSpec,
    *,
    coordination: str | None,
    planning_mode: str | None,
    no_replan: bool,
    quiet: bool,
) -> ScenarioSpec:
    from apex.evaluation.run_config import StrategicReplanMode

    run = spec.run.model_copy()
    if coordination is not None:
        run.coordination = TacticalCoordination(coordination)
    if planning_mode is not None:
        run.planning_mode = PlanningMode(planning_mode)
    if no_replan:
        run.strategic_replan = StrategicReplanMode.DISABLED
    run.quiet = quiet
    return spec.model_copy(update={"run": run})


def main() -> None:
    parser = argparse.ArgumentParser(description="APEX evaluation scenario runner")
    parser.add_argument("--scenario", choices=sorted(SCENARIO_BUILDERS), help="catalog scenario id")
    parser.add_argument("--yaml", type=Path, help="YAML scenario file")
    parser.add_argument("--output", type=Path, required=True, help="output directory")
    parser.add_argument("--coordination", choices=[e.value for e in TacticalCoordination], default=None)
    parser.add_argument(
        "--planning-mode",
        choices=[e.value for e in PlanningMode],
        default=None,
    )
    parser.add_argument("--no-replan", action="store_true", help="disable HTN strategic replan on escalation")
    parser.add_argument("--verbose", action="store_true", help="print agent trajectory logs")
    parser.add_argument(
        "--record-video",
        action="store_true",
        help="save pygame visualization to MP4 (requires pip install -e '.[viz]')",
    )
    parser.add_argument(
        "--video-output-dir",
        type=Path,
        default=None,
        help="MP4 directory; default: <output>/videos",
    )
    parser.add_argument("--video-fps", type=int, default=None, help="encoder FPS (default: run config)")
    parser.add_argument(
        "--video-frame-dt",
        type=float,
        default=None,
        help="sim time slice per visualization frame (default: run config)",
    )
    args = parser.parse_args()

    if bool(args.scenario) == bool(args.yaml):
        parser.error("Specify exactly one of --scenario or --yaml")

    if args.scenario:
        spec = build_scenario(args.scenario)
    else:
        spec = load_scenario_from_yaml(args.yaml)

    spec = _merge_run_flags(
        spec,
        coordination=args.coordination,
        planning_mode=args.planning_mode,
        no_replan=args.no_replan,
        quiet=not args.verbose,
    )
    if args.record_video:
        video_dir = args.video_output_dir if args.video_output_dir is not None else args.output / "videos"
        v_upd = {"enabled": True, "output_dir": str(video_dir.resolve())}
        if args.video_fps is not None:
            v_upd["fps"] = args.video_fps
        if args.video_frame_dt is not None:
            v_upd["frame_dt"] = args.video_frame_dt
        spec = spec.model_copy(
            update={
                "run": spec.run.model_copy(
                    update={"video": spec.run.video.model_copy(update=v_upd)},
                ),
            },
        )

    collector = MetricsCollector()
    metrics = EpisodeDriver(spec, collector=collector).run()

    cli_snap = {}
    for k, v in vars(args).items():
        if isinstance(v, Path):
            cli_snap[k] = str(v)
        else:
            cli_snap[k] = v
    write_run_directory(
        args.output,
        scenario=spec,
        metrics=metrics,
        collector=collector,
        extra_manifest={
            "cli": cli_snap,
            "metrics_summary": json.loads(metrics.model_dump_json()),
        },
    )
    print(metrics.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
