#!/usr/bin/env python3
"""Emit a catalog :class:`~apex.scenarios.models.ScenarioSpec` as YAML.

Example:

  python scripts/export_catalog_scenario_to_yaml.py \\
    --scenario single_order_single_agent \\
    --output apex/scenarios/data/suite/baseline_single_agent.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from apex.scenarios.catalog import SCENARIO_BUILDERS, build_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Export catalog scenario to YAML")
    parser.add_argument("--scenario", required=True, choices=sorted(SCENARIO_BUILDERS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec = build_scenario(args.scenario)
    data = spec.model_dump(mode="json")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
