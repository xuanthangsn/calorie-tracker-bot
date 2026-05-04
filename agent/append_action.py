"""Append-only action: add content to the end of a permitted workspace file."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from utils.path_resolution import InvalidLLMRequestedPath, resolve_workspace_path


class AppendParamsModel(BaseModel):
    """Validation schema for `append` action params."""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    content: str = Field(min_length=1)


class AppendAction(BaseAction):
    """Append text to a file under memory root (filename only); add a new line to the file if the file does not end with a newline."""

    name = "append"

    def __init__(self, params: ActionParam) -> None:
        super().__init__(params)
        self._validated_params: AppendParamsModel | None = None

    def _validate_param(self) -> None:
        payload = self.params.to_dict()
        try:
            self._validated_params = AppendParamsModel.model_validate(payload)
        except ValidationError as exc:
            raise ActionValidationError(f"invalid append params: {exc}") from exc

    def _execute_impl(self) -> str:
        if self._validated_params is None:
            raise ActionError("append params must be validated before execution")
        requested_path = self._validated_params.path
        content = self._validated_params.content
        try:
            safe_path = resolve_workspace_path(requested_path)
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            if safe_path.exists():
                existing = safe_path.read_text(encoding="utf-8")
                trailing_newline = existing.endswith("\n")
                if trailing_newline:
                    new_text = existing + content
                else:
                    new_text = existing + "\n" + content
                # new_text = existing + content
            else:
                new_text = content
            safe_path.write_text(new_text, encoding="utf-8")
            return content
        except InvalidLLMRequestedPath as exc:
            raise ActionError(f"the requested append file path is invalid: '{requested_path}'") from exc
        except IsADirectoryError as exc:
            raise ActionError(f"append failed: path is a directory: '{requested_path}'") from exc
        except OSError as exc:
            raise ActionError(f"append failed for '{requested_path}': {exc}") from exc
