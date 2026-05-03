"""Smoke tests for scenario catalog + episodic harness."""

from apex.evaluation.episode_driver import EpisodeDriver
from apex.evaluation.runner import ExperimentRunner
from apex.evaluation.run_config import TacticalCoordination
from apex.scenarios.catalog import (
    SCENARIO_BUILDERS,
    build_scenario,
    load_scenario_from_yaml,
)


def test_all_catalog_builders_registered():
    assert "single_order_single_agent" in SCENARIO_BUILDERS
    assert len(SCENARIO_BUILDERS) >= 5


def test_episode_single_order_finishes_instructions():
    spec = build_scenario("single_order_single_agent")
    m = EpisodeDriver(spec).run()
    assert m.completed_instruction_count >= 8


def test_greedy_baseline_matches_cbs_completed_count():
    s_cbs = build_scenario("two_agents_crossing", coordination=TacticalCoordination.CBS)
    s_gr = build_scenario(
        "two_agents_crossing",
        coordination=TacticalCoordination.GREEDY_UNCOORDINATED,
    )
    cbs_i = EpisodeDriver(s_cbs).run().completed_instruction_count
    gr_i = EpisodeDriver(s_gr).run().completed_instruction_count
    assert cbs_i == gr_i


def test_experiment_runner_sweep_lengths():
    specs = [
        build_scenario("single_order_single_agent"),
        build_scenario("two_agents_crossing"),
    ]
    out = ExperimentRunner().run_sweep(specs)
    assert len(out) == 2


def test_yaml_scenario_roundtrip_tmp_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("sc") / "scenario.yaml"
    p.write_text(
        """
id: tiny
seed: 0
horizon: 2000
grid_rows: 12
grid_cols: 12
bay_position: [10, 10]
shelves:
  - id: shelf_a
    positions: [[3, 3]]
    capacity: 50
agents:
  - id: picker-0
    row: 0
    col: 0
orders:
  - id: o1
    arrival_time: 0
    items:
      - sku: S1
        shelf_zone_id: shelf_a
        quantity: 1
disruptions: []
run:
  coordination: cbs
  planning_mode: HTN_ONLY
  strategic_replan: disabled
  quiet: true
""".strip(),
        encoding="utf-8",
    )
    spec = load_scenario_from_yaml(p)
    m = EpisodeDriver(spec).run()
    assert m.scheduled_instruction_count >= 8
