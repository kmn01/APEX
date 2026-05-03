"""Tests for typed settings and Gemini key helpers."""

import pytest

from apex.config.settings import ApexSettings, get_settings, map_rollout_stage, require_gemini_api_key


def test_require_gemini_api_key_raises_when_missing():
    s = ApexSettings(gemini_api_key=None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        require_gemini_api_key(s)


def test_require_gemini_api_key_ok():
    s = ApexSettings(gemini_api_key="secret")
    assert require_gemini_api_key(s) == "secret"


def test_map_rollout_stage_disabled():
    s = ApexSettings(map_enabled=False)
    assert map_rollout_stage(s) == "disabled"


def test_map_rollout_stage_shadow_replan():
    s = ApexSettings(
        map_enabled=True,
        map_replan_shadow=True,
        map_apply_replan=False,
        map_apply_plan=False,
    )
    assert map_rollout_stage(s) == "shadow_replan"


def test_get_settings_cache_clear(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    s = get_settings()
    assert s.gemini_api_key == "from-env"
    get_settings.cache_clear()


def test_map_rollout_stage_full():
    s = ApexSettings(map_enabled=True, map_apply_plan=True, map_apply_replan=False)
    assert map_rollout_stage(s) == "full"


def test_map_rollout_stage_apply_replan_only():
    s = ApexSettings(
        map_enabled=True,
        map_apply_plan=False,
        map_apply_replan=True,
        map_replan_shadow=False,
    )
    assert map_rollout_stage(s) == "apply_replan"


def test_map_rollout_stage_enabled_but_no_apply_flags():
    s = ApexSettings(map_enabled=True, map_apply_plan=False, map_apply_replan=False)
    assert map_rollout_stage(s) == "disabled"
