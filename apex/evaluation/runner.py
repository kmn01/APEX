"""Experiment driver for repeatable scenario sweeps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from apex.evaluation.episode_driver import EpisodeDriver
from apex.evaluation.metrics import EpisodeMetrics, MetricsCollector

if TYPE_CHECKING:
    from apex.scenarios.models import ScenarioSpec


class ScenarioConfig(BaseModel):
    """Legacy horizon/layout knobs; prefer composing :class:`~apex.scenarios.models.ScenarioSpec`."""

    grid_rows: int = 20
    grid_cols: int = 20
    n_agents: int = 4
    n_orders: int = 10
    disruption_rate: float = 0.05
    random_seed: int = 0
    sim_duration: float = 3600.0

    def to_scale_scenario_spec(self, scenario_id: str = "scale_from_config") -> "ScenarioSpec":
        """Materialize :class:`~apex.scenarios.models.ScenarioSpec` via :func:`~apex.scenarios.catalog.scenario_scale_floor`."""
        from apex.scenarios.catalog import scenario_scale_floor

        return scenario_scale_floor(
            self.grid_rows,
            self.grid_cols,
            self.n_agents,
            self.n_orders,
            seed=self.random_seed,
        ).model_copy(
            update={
                "id": scenario_id,
                "horizon": self.sim_duration,
                "stochastic_disruption": {
                    "disruption_rate": max(self.disruption_rate, 1e-6),
                    "rng_seed": self.random_seed,
                },
            }
        )


class ExperimentRunner:
    """High-level harness wiring config to the simulator and planners."""

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self.collector = collector

    def __repr__(self) -> str:
        return f"ExperimentRunner(collector={self.collector!r})"

    def run_episode(self, scenario: "ScenarioSpec") -> EpisodeMetrics:
        """Execute a single parameterized episode."""
        col = MetricsCollector() if self.collector is None else self.collector
        driver = EpisodeDriver(scenario.model_copy(deep=True), collector=col)
        return driver.run()

    def run_sweep(self, configs: list["ScenarioSpec"]) -> list[EpisodeMetrics]:
        """Run many configs sequentially (deterministic notebook-style sweeps)."""
        return [self.run_episode(spec) for spec in configs]


if __name__ == "__main__":
    er = ExperimentRunner()
    print(repr(er))
