"""Core Action abstraction for agent tool-calling.

This module defines an OOP base class that concrete actions can extend.
It follows the high-level contract from `agent_system_design.md`:

- Action has a `name` and `params`
- Action exposes `execute()` and returns a string result

It also adds a practical execution lifecycle:
- input validation
- optional pre/post hooks
- consistent error handling
- helpers for parsing structured LLM action payloads
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Mapping


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class ActionError(RuntimeError):
    """Raised when action execution fails."""


class ActionValidationError(ActionError):
    """Raised when action parameters are invalid."""


class BaseAction(ABC):
    """Base class for all tool-calling actions.

    Subclasses should:
    - define a unique `name`
    - implement _execute_impl, validate
    - optionally override  `before_execute()`, `after_execute()`
    """

    name: str = "base_action"

    def __init__(
        self,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        self.params: dict[str, Any] = dict(params or {})
        self.created_at: str = _utc_now_iso()
        self._result: str | None = None
        self._last_error: str | None = None

    @property
    def result(self) -> str | None:
        """Last successful execution result."""
        return self._result

    @property
    def last_error(self) -> str | None:
        """Last execution error, if any."""
        return self._last_error

    @abstractmethod
    def validate(self) -> None:
        """
        Validate action parameters.
        """
     

    def before_execute(self) -> None:
        """Optional hook called before execution."""

    def after_execute(self, result: str) -> None:
        """Optional hook called after successful execution."""

    @abstractmethod
    def _execute_impl(self) -> str:
        """Concrete action logic. Must return a string."""

    def execute(self) -> str:
        """Execute action with lifecycle management.

        Returns:
            str: execution output for the current ReAct cycle.
        """
        self._last_error = None
        self.validate()
        self.before_execute()
        try:
            result = self._execute_impl()
            if not isinstance(result, str):
                raise ActionError(
                    f"{self.__class__.__name__}._execute_impl() must return str"
                )
            self.after_execute(result)
            self._result = result
            return result
        except ActionError as exc:
            self._last_error = str(exc)
            raise
        except Exception as exc:  # pragma: no cover - defensive conversion
            self._last_error = str(exc)
            raise ActionError(
                f"Unhandled error in action '{self.name}': {exc}"
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        """Serialize action state for logs/traces."""
        return {
            "name": self.name,
            "params": self.params,
            "created_at": self.created_at,
            "result": self._result,
            "last_error": self._last_error,
        }

    @classmethod
    def from_llm_action_json(
        cls,
        payload: Mapping[str, Any],
    ) -> BaseAction:
        """Create a base action object from the LLM `action` payload.

        Expected minimal shape:
            {
                "name": "<action_name>",
                "params": { ... }
            }

        This method intentionally returns an anonymous BaseAction subclass,
        which is useful as a neutral fallback before introducing an Action factory.
        """
        name = str(payload.get("name", "")).strip()
        params = payload.get("params", {})
        if not name:
            raise ActionValidationError("LLM action payload is missing 'name'")
        if params is None:
            params = {}
        if not isinstance(params, Mapping):
            raise ActionValidationError("'params' must be an object/dictionary")

        class _AnonymousAction(BaseAction):
            def _execute_impl(self) -> str:
                return (
                    f"Action '{self.name}' is parsed but has no concrete implementation yet."
                )

        obj = _AnonymousAction(params=dict(params))
        obj.name = name
        return obj

