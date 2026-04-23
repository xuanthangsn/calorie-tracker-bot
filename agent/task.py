"""Task component implementing bounded ReAct execution."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import config
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.action import ActionError, ActionValidationError, BaseAction
from agent.action_param import ActionParam
from agent.final_answer_action import FinalAnswerAction
from agent.read_action import ReadAction
from agent.write_action import WriteAction
from google import genai
from google.genai import types


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_system_prompt() -> str:
    prompt_path = Path("prompts/system_prompt.md")
    try:
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TaskError(f"failed to load system prompt file '{prompt_path}': {exc}") from exc
    if not prompt_text:
        raise TaskError(f"system prompt file is empty: '{prompt_path}'")
    return prompt_text


class TaskError(RuntimeError):
    """Raised for Task-level failures in orchestration or lifecycle."""


class LLMResponse(BaseModel):
    """Strict action-centric response envelope from LLM."""

    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1)
    thought: str = Field(min_length=1)
    params: dict[str, Any]


@dataclass
class _Observation:
    tool_executed: str
    status: str
    output: str

    def to_text(self) -> str:
        payload = {
            "tool_executed": self.tool_executed,
            "status": self.status,
            "output": self.output,
        }
        return f"OBSERVATION:\n{json.dumps(payload, ensure_ascii=True)}"


class Task:
    """One user-originated run with bounded ReAct cycles."""

    ACTION_REGISTRY: dict[str, Callable[[ActionParam], BaseAction]] = {
        "read": ReadAction,
        "write": WriteAction,
        "final_answer": FinalAnswerAction,
    }

    SYSTEM_PROMPT = _get_system_prompt()

    def __init__(
        self,
        user_request: str,
        max_cycle: int = 8,
        model_name: str = "gemini-3-flash-preview",
    ) -> None:
        if not isinstance(user_request, str) or not user_request.strip():
            raise TaskError("user_request must be a non-empty string")
        if max_cycle <= 0:
            raise TaskError("max_cycle must be > 0")

        self.id: str = str(uuid.uuid4())
        self.user_request: str = user_request.strip()
        self.final_response: str | None = None
        self.status: str = "pending"
        self.cycle_index: int = 0
        self.max_cycle: int = max_cycle
        self.task_context: list[dict[str, Any]] = [
            {"role": "user", "parts": [{"text": self.user_request}]}
        ]
        self.actions: list[dict[str, Any]] = []
        self.error: str | None = None
        self.created_at: str = _utc_now_iso()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self._stop_requested: bool = False
        self._model_name = model_name

        try:
            self._client = self._build_llm_client()
        except Exception as exc:
            raise TaskError(f"failed to build LLM client: {exc}") from exc

    def _build_llm_client(self) -> Any:
        return genai.Client(api_key=config.GEMINI_API_KEY)

    def execute(self) -> str:
        """Run bounded ReAct loop until completion, cancel, or failure."""
        if self.status not in {"pending", "running"}:
            raise TaskError(f"cannot execute task from status '{self.status}'")

        if self.status == "pending":
            self.status = "running"
            self.started_at = _utc_now_iso()

        while self.status == "running":
            if self._stop_requested:
                self.status = "cancelled"
                self.finished_at = _utc_now_iso()
                break

            if self.cycle_index >= self.max_cycle:
                self.status = "failed"
                self.error = "max cycles exceeded without completion"
                self.finished_at = _utc_now_iso()
                break

            self.cycle_index += 1
            try:
                llm_raw = self._call_llm()
                parsed = self._parse_llm_response(llm_raw)
            except TaskError as exc:
                self.status = "failed"
                self.error = str(exc)
                self.finished_at = _utc_now_iso()
                break

            self.task_context.append({"role": "model", "parts": [{"text": llm_raw}]})

            action_name = parsed.action
            action_cls = self.ACTION_REGISTRY.get(action_name)
            if action_cls is None:
                self.status = "failed"
                self.error = f"unknown action: '{action_name}'"
                self.finished_at = _utc_now_iso()
                break

            action = action_cls(ActionParam(parsed.params))
            try:
                output = action.execute()
            except ActionValidationError as exc:
                self._append_observation(_Observation(action_name, "validation_error", str(exc)))
                continue
            except ActionError as exc:
                self._append_observation(_Observation(action_name, "failed", str(exc)))
                continue

            self.actions.append(action.to_dict())
            self._append_observation(_Observation(action_name, "success", output))

            if action_name == "final_answer":
                self.final_response = output
                self.status = "completed"
                self.finished_at = _utc_now_iso()
                break

        if self.status == "completed" and self.final_response is not None:
            return self.final_response
        if self.status == "cancelled":
            raise TaskError("task was cancelled")
        raise TaskError(self.error or "task failed")

    def _call_llm(self) -> str:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=self.task_context,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise TaskError("empty response from LLM")
        return text

    def _parse_llm_response(self, raw_text: str) -> LLMResponse:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise TaskError(f"invalid JSON response from LLM: {exc}") from exc
        try:
            parsed = LLMResponse.model_validate(payload)
        except ValidationError as exc:
            raise TaskError(f"invalid LLM response: {exc}") from exc
        if not isinstance(parsed.params, dict):
            raise TaskError("invalid LLM response: params must be object")
        return parsed

    def _append_observation(self, observation: _Observation) -> None:
        self.task_context.append({"role": "user", "parts": [{"text": observation.to_text()}]})

    def force_stop(self) -> None:
        self._stop_requested = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "cycle_index": self.cycle_index,
            "max_cycle": self.max_cycle,
            "user_request": self.user_request,
            "final_response": self.final_response,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "actions_count": len(self.actions),
            "context_length": len(self.task_context),
        }

    def get_status(self) -> str:
        return self.status

    def get_error(self) -> str | None:
        return self.error

    def get_final_response(self) -> str | None:
        return self.final_response
