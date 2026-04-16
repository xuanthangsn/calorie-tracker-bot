"""
Structured LLM actions: strict per-action Pydantic models.

`Action` RootModel wraps the union so handlers receive one type; the parser
maps Gemini tool calls to these models and validates with Pydantic.
"""
from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel

MealType = Literal["breakfast", "lunch", "dinner", "snack", "other"]


class MealItem(BaseModel):
    food: str
    quantity: str
    calories: Optional[int] = None


class LogMealAction(BaseModel):
    action: Literal["log_meal"]
    meal_type: MealType
    items: List[MealItem]
    date: Optional[str] = Field(
        default=None,
        description="ISO date YYYY-MM-DD; omit for today.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


class EditMealAction(BaseModel):
    action: Literal["edit_meal"]
    target_meal_id: int
    meal_type: Optional[MealType] = None
    items: Optional[List[MealItem]] = None
    date: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


class DeleteMealAction(BaseModel):
    action: Literal["delete_meal"]
    target_meal_id: int


class SetGoalAction(BaseModel):
    action: Literal["set_goal"]
    daily: Optional[int] = Field(default=None, ge=0)
    weekly: Optional[int] = Field(default=None, ge=0)
    monthly: Optional[int] = Field(default=None, ge=0)


class GetReportAction(BaseModel):
    action: Literal["get_report"]
    period: Literal["daily", "weekly", "monthly"]
    start_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class AskClarificationAction(BaseModel):
    action: Literal["ask_clarification"]
    clarification_question: str = Field(
        min_length=1,
        description="Single short question to disambiguate.",
    )


class RefuseAction(BaseModel):
    action: Literal["refuse"]


ActionPayload = Annotated[
    Union[
        LogMealAction,
        EditMealAction,
        DeleteMealAction,
        SetGoalAction,
        GetReportAction,
        AskClarificationAction,
        RefuseAction,
    ],
    Field(discriminator="action"),
]


class Action(RootModel[ActionPayload]):
    """Root wrapper for handler dispatch (`wrapped.root` is a concrete action)."""


# Concrete type of the parsed payload (for isinstance / match)
ActionVariant = (
    LogMealAction
    | EditMealAction
    | DeleteMealAction
    | SetGoalAction
    | GetReportAction
    | AskClarificationAction
    | RefuseAction
)
