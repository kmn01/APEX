# MAP + Gemini rollout (APEX)

This document describes how the Modular Agentic Planner (MAP)–style Gemini integration is staged and how to operate it safely.

## Components

| Piece | Path | Role |
| --- | --- | --- |
| Settings | `apex/config/settings.py` | `GEMINI_*`, `APEX_MAP_*` flags, timeouts |
| Graph contract | `apex/planner/graph_delta.py` | `TaskGraphDelta`, validate/apply |
| Orchestrator | `apex/planner/specialists/orchestrator.py` | Four specialist prompts in sequence |
| Gemini client | `apex/planner/specialists/gemini_client.py` | `google-genai`, JSON parsing |
| Coordinator | `apex/planner/coordinator.py` | Baseline plan + optional MAP refine / replan |

## Rollout stages (recommended)

1. **Disabled** — `APEX_MAP_ENABLED=false` (opt-in override). No LLM calls; behavior unchanged from pre-MAP code. By default MAP is enabled in `apex/config/settings.py`; without `GEMINI_API_KEY` or if the client cannot start, runs fall back to baseline and log a warning.
2. **Shadow replan** — `APEX_MAP_ENABLED=true`, `APEX_MAP_REPLAN_SHADOW=true`, `APEX_MAP_APPLY_REPLAN=false`. MAP runs on `replan`; proposals are recorded on `SpecialistTrace.debug` only; returned delta stays empty.
3. **Apply replan** — `APEX_MAP_APPLY_REPLAN=true`, `APEX_MAP_APPLY_PLAN=false`. Only strategic **replan** may return a validated `TaskGraphDelta`; initial `plan` stays baseline-only unless you enable plan apply.
4. **Full** — `APEX_MAP_APPLY_PLAN=true` (and optionally `APEX_MAP_APPLY_REPLAN=true`). MAP may replace the post-HTN/post-MCTS graph when validation passes.

`map_rollout_stage()` in settings returns a coarse label (`disabled` | `shadow_replan` | `apply_replan` | `full`) for logging.

## Guardrails

- Every coordination output is validated with `validate_task_graph_delta` and merged in-process with `apply_task_graph_delta` before the coordinator accepts it.
- **Pass^k / repeatability:** use `MapReliabilityMetrics.record_plan_run_hash()` (see tests) to fingerprint successive plans under fixed seeds.
- **No key / bad client:** if `GEMINI_API_KEY` is unset, optional `google-genai` is missing, or client init fails, MAP returns `None` / empty delta, logs a warning, and metrics record fallbacks.

## Dependencies

Core installs include `pydantic-settings`. Gemini calls require:

```bash
pip install -e ".[llm]"
```
