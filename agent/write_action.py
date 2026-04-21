"""Concrete write action with strict filesystem permission checks."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from utils.path_resolution import InvalidLLMRequestedPath, resolve_workspace_path


class WriteParamsModel(BaseModel):
    """Validation schema for `write` action params."""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    content: str


class WriteAction(BaseAction):
    """Write text content to a file in the permitted memory directory."""

    name = "write"

    def __init__(
        self,
        params: ActionParam,
    ) -> None:
        super().__init__(params)
        self._validated_params: WriteParamsModel | None = None

    def _validate_param(self) -> None:
        payload = self.params.to_dict()
        try:
            self._validated_params = WriteParamsModel.model_validate(payload)
        except ValidationError as exc:
            raise ActionValidationError(f"invalid write params: {exc}") from exc

    def _execute_impl(self) -> str:
        if self._validated_params is None:
            raise ActionError("write params must be validated before execution")
        requested_path = self._validated_params.path
        content = self._validated_params.content
        try:
            safe_path = resolve_workspace_path(requested_path)
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            safe_path.write_text(content, encoding="utf-8")
            return f"write success: {safe_path}"
        except InvalidLLMRequestedPath as exc:
            raise ActionError(f"the requested write file path is invalid: '{requested_path}'") from exc
        except IsADirectoryError as exc:
            raise ActionError(f"write failed: path is a directory: '{requested_path}'") from exc
        except OSError as exc:
            raise ActionError(f"write failed for '{requested_path}': {exc}") from exc
