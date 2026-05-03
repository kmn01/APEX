"""Protocols for JSON-capable clients used by MAP specialists."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JsonCompletionClient(Protocol):
    """Minimal surface for structured JSON completions."""

    def complete_json(self, system: str, user: str, model_cls: type[T]) -> T:
        """Parse model output as ``model_cls`` (raise on failure)."""
        ...

