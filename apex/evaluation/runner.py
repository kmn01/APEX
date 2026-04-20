"""Experiment driver for repeatable scenario sweeps.

Runs configured episodes against the full APEX stack and returns
:class:`~apex.evaluation.metrics.EpisodeMetrics` for analysis or dashboards.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from apex.evaluation.metrics import EpisodeMetrics, MetricsCollector


class ScenarioConfig(BaseModel):
    """Parameters controlling layout, load, randomness, and horizon."""

    grid_rows: int = 20
    grid_cols: int = 20
    n_agents: int = 4
    n_orders: int = 10
    disruption_rate: float = 0.05
    random_seed: int = 0
    sim_duration: float = 3600.0


class ExperimentRunner:
    """High-level harness wiring config to the simulator and planners."""

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self.collector = collector or MetricsCollector()

    def __repr__(self) -> str:
        return f"ExperimentRunner(collector={self.collector!r})"

    def run_episode(self, config: ScenarioConfig) -> EpisodeMetrics:
        """Execute a single parameterized episode."""
        raise NotImplementedError("TODO: build state, run SimPy until horizon")

    def run_sweep(self, configs: list[ScenarioConfig]) -> list[EpisodeMetrics]:
        """Run many configs sequentially or batched for comparison."""
        raise NotImplementedError("TODO: loop run_episode with optional parallelism")


if __name__ == "__main__":
    er = ExperimentRunner()
    print(repr(er))
