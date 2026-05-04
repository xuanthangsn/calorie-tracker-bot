"""Concrete read action for workspace files (optional tail = last n lines)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from utils.path_resolution import InvalidLLMRequestedPath, resolve_workspace_path


class ReadParamsModel(BaseModel):
    """Validation schema for `read` action params (implemented_actions.md)."""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    tail: str | None = Field(default=None)

    @field_validator("tail")
    @classmethod
    def validate_tail(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if not stripped.isdigit():
            raise ValueError("tail must be a string of digits (positive integer)")
        n = int(stripped)
        if n <= 0:
            raise ValueError("tail must be a positive integer")
        return stripped


class ReadAction(BaseAction):
    """Read text from a file under the LLM workspace."""

    name = "read"

    def __init__(self, params: ActionParam) -> None:
        super().__init__(params)
        self._validated_params: ReadParamsModel | None = None

    def _validate_param(self) -> None:
        payload = self.params.to_dict()
        try:
            self._validated_params = ReadParamsModel.model_validate(payload)
        except ValidationError as exc:
            raise ActionValidationError(f"invalid read params: {exc}") from exc

    def _execute_impl(self) -> str:
        if self._validated_params is None:
            raise ActionError("read params must be validated before execution")
        requested_path = self._validated_params.path
        tail_raw = self._validated_params.tail

        try:
            safe_path = resolve_workspace_path(requested_path)
            content = safe_path.read_text(encoding="utf-8")
        except InvalidLLMRequestedPath as exc:
            raise ActionError(f"the requested read file path is invalid: '{requested_path}'") from exc
        except FileNotFoundError as exc:
            raise ActionError(f"read failed: file not found: '{requested_path}'") from exc
        except IsADirectoryError as exc:
            raise ActionError(f"read failed: path is a directory: '{requested_path}'") from exc
        except OSError as exc:
            raise ActionError(f"read failed for '{requested_path}': {exc}") from exc

        if tail_raw is None:
            return content

        n = int(tail_raw.strip())
        lines = content.splitlines()
        if n >= len(lines):
            return content
        selected = "\n".join(lines[-n:])
        if content.endswith("\n"):
            selected += "\n"
        return selected
