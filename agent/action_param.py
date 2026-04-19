"""Generic action parameters wrapper."""
from __future__ import annotations
from typing import Any, Mapping
class ActionParam:
    """Holds the raw LLM/action payload (typically a string-keyed mapping)."""
    __slots__ = ("params",)
    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        self.params: dict[str, Any] = dict(params or {})
    def to_dict(self) -> dict[str, Any]:
        return dict(self.params)