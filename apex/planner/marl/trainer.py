"""Self-play MARL trainer stub (Phase 3).

Will orchestrate rollouts against the simulator and update :class:`~apex.planner.marl.policy.MAPPOPolicy`
weights once torch training is enabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch

from apex.planner.marl.policy import MAPPOPolicy


class SelfPlayTrainer:
    """Placeholder trainer coordinating data collection and optimization."""

    def __init__(self, policy: MAPPOPolicy | None = None) -> None:
        self.policy = policy or MAPPOPolicy()

    def __repr__(self) -> str:
        return f"SelfPlayTrainer(policy={self.policy!r})"

    def train_step(self, batch: Any) -> dict[str, float]:
        """Perform one optimizer step on a collected rollout batch."""
        raise NotImplementedError("TODO: PPO/MAPPO loss and backward")

    def run_rollout(self, env: Any) -> Any:
        """Gather trajectories from the simulation environment."""
        raise NotImplementedError("TODO: parallel rollout drivers")


if __name__ == "__main__":
    tr = SelfPlayTrainer()
    print(repr(tr))
