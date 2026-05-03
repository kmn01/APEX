"""Smoke tests for all YAML files in apex/scenarios/data/suite/."""

from __future__ import annotations

from pathlib import Path

import pytest

from apex.config.settings import get_settings
from apex.evaluation.episode_driver import EpisodeDriver
from apex.scenarios.catalog import load_scenario_from_yaml


SUITE_DIR = Path(__file__).resolve().parents[1] / "apex" / "scenarios" / "data" / "suite"
SUITE_YAMLS = sorted(SUITE_DIR.glob("*.yaml"))


@pytest.fixture(autouse=True)
def _disable_map_for_suite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APEX_MAP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "yaml_path",
    SUITE_YAMLS,
    ids=[p.stem for p in SUITE_YAMLS],
)
def test_suite_yaml_episode_smoke(yaml_path: Path) -> None:
    spec = load_scenario_from_yaml(yaml_path)
    metrics = EpisodeDriver(spec).run()
    assert metrics.scheduled_instruction_count > 0
    assert metrics.completed_instruction_count > 0
    assert metrics.horizon == spec.horizon
    assert metrics.sim_duration > 0


def test_suite_directory_nonempty() -> None:
    assert SUITE_YAMLS, f"Expected YAML scenarios under {SUITE_DIR}"
