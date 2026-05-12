"""Thin wrapper around the official ``google-genai`` client for JSON outputs."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from apex.config.settings import ApexSettings, get_settings

T = TypeVar("T", bound=BaseModel)


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


class GeminiJsonClient:
    """Call Gemini with low temperature and parse JSON into a Pydantic model."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        try:
            from google import genai  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional extra
            raise ImportError(
                "Optional dependency missing: install with `pip install -e \".[llm]\"` "
                "to use GeminiJsonClient."
            ) from exc

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    @classmethod
    def from_settings(cls, settings: ApexSettings | None = None) -> GeminiJsonClient:
        s = settings or get_settings()
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        return cls(
            s.gemini_api_key,
            s.gemini_model,
            timeout_s=s.map_request_timeout_s,
            max_retries=s.map_max_retries,
        )

    def complete_json(
        self,
        system: str,
        user: str,
        model_cls: type[T],
        telemetry_hook: Callable[[dict[str, Any]], None] | None = None,
    ) -> T:
        from google.genai import types  # type: ignore[import-not-found]

        last_err: Exception | None = None
        for attempt in range(self._max_retries + 1):
            started = time.perf_counter()
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.15,
                        response_mime_type="application/json",
                    ),
                )
                text = getattr(response, "text", None) or ""
                payload = json.loads(_strip_json_fence(text))
                out = model_cls.model_validate(payload)
                if telemetry_hook is not None:
                    telemetry_hook(
                        {
                            "model": self._model,
                            "attempt": attempt,
                            "duration_s": time.perf_counter() - started,
                            "ok": True,
                            "response_chars": len(text),
                        }
                    )
                return out
            except (json.JSONDecodeError, ValidationError, AttributeError, ValueError) as exc:
                last_err = exc
                if telemetry_hook is not None:
                    telemetry_hook(
                        {
                            "model": self._model,
                            "attempt": attempt,
                            "duration_s": time.perf_counter() - started,
                            "ok": False,
                            "error_type": type(exc).__name__,
                        }
                    )
                if attempt < self._max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise RuntimeError(f"Gemini JSON parse/validate failed: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if telemetry_hook is not None:
                    telemetry_hook(
                        {
                            "model": self._model,
                            "attempt": attempt,
                            "duration_s": time.perf_counter() - started,
                            "ok": False,
                            "error_type": type(exc).__name__,
                        }
                    )
                if attempt < self._max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(f"Gemini call failed: {last_err!r}")
