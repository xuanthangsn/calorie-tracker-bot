"""Concrete final answer action for terminating a task."""
from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam


class FinalAnswerParamsModel(BaseModel):
    """Validation schema for `final_answer` action params."""

    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1)


class FinalAnswerAction(BaseAction):
    """Return the final user-facing message and completion signal."""

    name = "final_answer"

    def __init__(self, params: ActionParam) -> None:
        super().__init__(params)
        self._validated_params: FinalAnswerParamsModel | None = None

    def _validate_param(self) -> None:
        payload = self.params.to_dict()
        try:
            self._validated_params = FinalAnswerParamsModel.model_validate(payload)
        except ValidationError as exc:
            raise ActionValidationError(f"invalid final_answer params: {exc}") from exc

    def _execute_impl(self) -> str:
        if self._validated_params is None:
            raise ActionError("final_answer params must be validated before execution")

        message = self._validated_params.message
        logging.info("LLM final answer: %s", message)
        return message
