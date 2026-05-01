"""Concrete write action with strict filesystem permission checks."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from utils.path_resolution import InvalidLLMRequestedPath, resolve_workspace_path


class WriteParamsModel(BaseModel):
    """Validation schema for `write` action params."""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    mode: Literal["append", "replace_lines"]
    content: str
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_line_bounds(self) -> WriteParamsModel:
        if self.start_line is not None and self.end_line is not None and self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        return self


def _lines_from_text(text: str) -> list[str]:
    return text.splitlines()


def _apply_replace_lines(
    existing_lines: list[str],
    content: str,
    start_line: int | None,
    end_line: int | None,
) -> str:
    """Replace lines in [start_line, end_line) (1-based, half-open). Omit both bounds → whole file."""
    if start_line is None and end_line is None:
        return content
    new_segment = _lines_from_text(content)
    start_idx = 0 if start_line is None else start_line - 1
    end_idx = len(existing_lines) if end_line is None else end_line - 1
    if start_idx < 0 or start_idx > len(existing_lines):
        raise ActionError(
            f"replace_lines: start_line {start_line} is out of range for file with {len(existing_lines)} lines"
        )
    if end_idx < start_idx:
        raise ActionError("replace_lines: end_line must be >= start_line")
    if end_idx > len(existing_lines):
        raise ActionError(
            f"replace_lines: end_line {end_line} is past end of file ({len(existing_lines)} lines)"
        )
    merged = existing_lines[:start_idx] + new_segment + existing_lines[end_idx:]
    return "\n".join(merged)


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
        mode = self._validated_params.mode
        start_line = self._validated_params.start_line
        end_line = self._validated_params.end_line
        try:
            safe_path = resolve_workspace_path(requested_path)
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            if mode == "append":
                if safe_path.exists():
                    # append content in a new line
                    existing = safe_path.read_text(encoding="utf-8")
                    trailing_newline = existing.endswith("\n")
                    if trailing_newline:
                        new_text = existing + content
                    else:
                        new_text = existing + "\n" + content
                else:
                    new_text = content
                safe_path.write_text(new_text, encoding="utf-8")
                return content

            # replace_lines
            if safe_path.exists():
                raw_existing = safe_path.read_text(encoding="utf-8")
                existing_lines = _lines_from_text(raw_existing)
                trailing_newline = raw_existing.endswith("\n")
            else:
                existing_lines = []
                trailing_newline = False
            new_text = _apply_replace_lines(existing_lines, content, start_line, end_line)
            if trailing_newline and not new_text.endswith("\n"):
                new_text += "\n"
            safe_path.write_text(new_text, encoding="utf-8")
            return content
        except InvalidLLMRequestedPath as exc:
            raise ActionError(f"the requested write file path is invalid: '{requested_path}'") from exc
        except IsADirectoryError as exc:
            raise ActionError(f"write failed: path is a directory: '{requested_path}'") from exc
        except OSError as exc:
            raise ActionError(f"write failed for '{requested_path}': {exc}") from exc
