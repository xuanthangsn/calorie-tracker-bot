"""Concrete read action with strict filesystem permission checks."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from agent.path_permission_policy import PathPermissionError, PathPermissionPolicy


class ReadParamsModel(BaseModel):
    """Validation schema for `read` action params."""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)


class ReadAction(BaseAction):
    """Read text file content from the permitted memory directory."""

    name = "read"

    def __init__(
        self,
        params: ActionParam,
        permission_policy: PathPermissionPolicy | None = None,
    ) -> None:
        super().__init__(params)
        self._permission_policy = permission_policy or PathPermissionPolicy.from_cwd()
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
        try:
            safe_path = self._permission_policy.authorize("read", requested_path)
            return safe_path.read_text(encoding="utf-8")
        except PathPermissionError as exc:
            raise ActionError(str(exc)) from exc
        except FileNotFoundError as exc:
            raise ActionError(f"read failed: file not found: '{requested_path}'") from exc
        except IsADirectoryError as exc:
            raise ActionError(f"read failed: path is a directory: '{requested_path}'") from exc
        except OSError as exc:
            raise ActionError(f"read failed for '{requested_path}': {exc}") from exc
