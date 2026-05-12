"""Typed environment settings (pydantic-settings).

Gemini and MAP are on by default; missing ``GEMINI_API_KEY`` or a failed client init
falls back to baseline planning (see :class:`~apex.planner.specialists.orchestrator.MapOrchestrator`).
Tests may inject a mock client.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _dotenv_paths() -> tuple[str, ...] | None:
    """Resolve ``.env`` relative to repo root then cwd.

    Pydantic loads files in order; later files override earlier ones, so a cwd
    ``.env`` wins over the checkout copy when both exist.
    """
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    cwd_env = Path(".env")
    merged: list[Path] = []
    seen_resolved: set[Path] = set()
    for p in (repo_env, cwd_env):
        if not p.is_file():
            continue
        r = p.resolve()
        if r in seen_resolved:
            continue
        seen_resolved.add(r)
        merged.append(p)
    return tuple(str(x) for x in merged) if merged else None


class ApexSettings(BaseSettings):
    """Central settings loaded from environment (and optional ``.env``)."""

    model_config = SettingsConfigDict(
        env_file=_dotenv_paths(),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key"),
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "gemini_model"),
    )

    # MAP / Gemini planner flags (explicit APEX_* env names; override to disable or shadow-only)
    map_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("APEX_MAP_ENABLED", "map_enabled"),
    )
    map_apply_plan: bool = Field(
        default=True,
        validation_alias=AliasChoices("APEX_MAP_APPLY_PLAN", "map_apply_plan"),
    )
    map_apply_replan: bool = Field(
        default=True,
        validation_alias=AliasChoices("APEX_MAP_APPLY_REPLAN", "map_apply_replan"),
    )
    map_replan_shadow: bool = Field(
        default=True,
        validation_alias=AliasChoices("APEX_MAP_REPLAN_SHADOW", "map_replan_shadow"),
    )
    map_plan_shadow: bool = Field(
        default=True,
        validation_alias=AliasChoices("APEX_MAP_PLAN_SHADOW", "map_plan_shadow"),
    )

    map_request_timeout_s: float = Field(
        default=60.0,
        validation_alias=AliasChoices("APEX_MAP_TIMEOUT_S", "map_request_timeout_s"),
    )
    map_max_retries: int = Field(
        default=2,
        validation_alias=AliasChoices("APEX_MAP_MAX_RETRIES", "map_max_retries"),
    )

    observability_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("APEX_OBSERVABILITY_ENABLED", "observability_enabled"),
    )
    observability_emit_move_steps: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APEX_OBSERVABILITY_EMIT_MOVE_STEPS", "observability_emit_move_steps"
        ),
    )
    viewer_provenance_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APEX_VIEWER_PROVENANCE_ENABLED", "viewer_provenance_enabled"
        ),
    )


MapRolloutStage = Literal["disabled", "shadow_replan", "apply_replan", "full"]


def require_gemini_api_key(settings: ApexSettings | None = None) -> str:
    """Return API key or raise a clear error when Gemini is required."""
    s = settings or get_settings()
    if not s.gemini_api_key:
        msg = (
            "GEMINI_API_KEY is not set. Add it to your environment or `.env`, "
            "or install optional deps with `pip install -e \".[llm]\"` and configure the key."
        )
        raise RuntimeError(msg)
    return s.gemini_api_key


@lru_cache
def get_settings() -> ApexSettings:
    """Cached settings singleton (clear cache in tests via ``get_settings.cache_clear()``)."""
    return ApexSettings()


def map_rollout_stage(settings: ApexSettings | None = None) -> MapRolloutStage:
    """Derive a coarse rollout stage from flags for logging/metrics."""
    s = settings or get_settings()
    if not s.map_enabled:
        return "disabled"
    if s.map_replan_shadow and not s.map_apply_replan:
        return "shadow_replan"
    if s.map_apply_replan and not s.map_apply_plan:
        return "apply_replan"
    if s.map_apply_plan or s.map_apply_replan:
        return "full"
    return "disabled"
