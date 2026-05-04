"""Replace-in-file action: substitute occurrences of old_text with new_text."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from utils.path_resolution import InvalidLLMRequestedPath, resolve_workspace_path


class ReplaceParamsModel(BaseModel):
    """Validation schema for `replace` action params (schema uses old_text / new_text, not content)."""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    old_text: str = Field(min_length=1)
    new_text: str = Field(min_length=1)


class ReplaceAction(BaseAction):
    """Replace all non-overlapping occurrences of old_text with new_text in a workspace file."""

    name = "replace"

    def __init__(self, params: ActionParam) -> None:
        super().__init__(params)
        self._validated_params: ReplaceParamsModel | None = None

    def _validate_param(self) -> None:
        payload = self.params.to_dict()
        try:
            self._validated_params = ReplaceParamsModel.model_validate(payload)
        except ValidationError as exc:
            raise ActionValidationError(f"invalid replace params: {exc}") from exc

    def _execute_impl(self) -> str:
        if self._validated_params is None:
            raise ActionError("replace params must be validated before execution")
        requested_path = self._validated_params.path
        old_text = self._validated_params.old_text
        new_text = self._validated_params.new_text
        try:
            safe_path = resolve_workspace_path(requested_path)
            if not safe_path.exists():
                raise ActionError(f"replace failed: file not found: '{requested_path}'")
            if safe_path.is_dir():
                raise ActionError(f"replace failed: path is a directory: '{requested_path}'")
            raw = safe_path.read_text(encoding="utf-8")
            if old_text not in raw:
                raise ActionError(f"replace failed: old_text not found in '{requested_path}'")
            updated = raw.replace(old_text, new_text)
            safe_path.write_text(updated, encoding="utf-8")
            return new_text
        except InvalidLLMRequestedPath as exc:
            raise ActionError(f"the requested replace file path is invalid: '{requested_path}'") from exc
        except OSError as exc:
            raise ActionError(f"replace failed for '{requested_path}': {exc}") from exc
