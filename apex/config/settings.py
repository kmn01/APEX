"""Typed environment settings (pydantic-settings).

Gemini and MAP flags are optional; missing ``GEMINI_API_KEY`` disables live LLM calls
unless tests inject a mock client.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApexSettings(BaseSettings):
    """Central settings loaded from environment (and optional ``.env``)."""

    model_config = SettingsConfigDict(
        env_file=".env",
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

    # MAP / Gemini planner flags (explicit APEX_* env names)
    map_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("APEX_MAP_ENABLED", "map_enabled"),
    )
    map_apply_plan: bool = Field(
        default=False,
        validation_alias=AliasChoices("APEX_MAP_APPLY_PLAN", "map_apply_plan"),
    )
    map_apply_replan: bool = Field(
        default=False,
        validation_alias=AliasChoices("APEX_MAP_APPLY_REPLAN", "map_apply_replan"),
    )
    map_replan_shadow: bool = Field(
        default=False,
        validation_alias=AliasChoices("APEX_MAP_REPLAN_SHADOW", "map_replan_shadow"),
    )
    map_plan_shadow: bool = Field(
        default=False,
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
