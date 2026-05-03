"""Experiment run configuration: coordination ablations and replan modes."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from apex.planner.coordinator import PlanningMode


class TacticalCoordination(str, Enum):
    """How multi-agent MOVE_TO instructions are expanded before execution."""

    CBS = "cbs"  # Conflict-based search batch expansion in executor
    GREEDY_UNCOORDINATED = "greedy_uncoordinated"  # No CBS; straight-line moves


class StrategicReplanMode(str, Enum):
    """How escalations are handled at the strategic layer."""

    DISABLED = "disabled"  # Record escalations only
    HTN_FALLBACK = "htn_fallback"  # Full coordinator.plan on active orders after escalation
    LOCAL_ONLY = "local_only"  # Never strategic replan (not used in coordinator; driver skips)


class VideoRecordingConfig(BaseModel):
    """Optional per-episode video capture settings for pygame visualization."""

    enabled: bool = False
    output_dir: str = "artifacts/videos"
    fps: int = 20
    frame_dt: float = 0.1
    width: int = 1200
    height: int = 900
    cell_size: int = 30
    include_paths: bool = False


class RunConfig(BaseModel):
    """Per-episode algorithm switches for benchmark sweeps."""

    planning_mode: PlanningMode = PlanningMode.HTN_ONLY
    coordination: TacticalCoordination = TacticalCoordination.CBS
    strategic_replan: StrategicReplanMode = StrategicReplanMode.HTN_FALLBACK
    disruption_stochastic_enabled: bool = False
    quiet: bool = True
    video: VideoRecordingConfig = Field(default_factory=VideoRecordingConfig)
