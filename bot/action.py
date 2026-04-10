from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from datetime import date

meal_type = Literal["breakfast", "lunch", "dinner", "snack", "other"]

class MealItem(BaseModel):
    food: str
    quantity: str
    calories: Optional[int] = None   # LLM can leave empty if it doesn't know


class LogMealAction(BaseModel):
    action: Literal["log_meal"]
    date: Optional[str] = Field(default=None, pattern=r"\d{4}-\d{2}-\d{2}")
    meal_type: meal_type
    items: List[MealItem]

class EditMealAction(BaseModel):
    action: Literal["edit_meal"]
    target_meal_id: int
    meal_type: Optional[meal_type] = None
    items: Optional[List[MealItem]] = None

class DeleteMealAction(BaseModel):
    action: Literal["delete_meal"]
    target_meal_id: int

class SetGoalAction(BaseModel):
    action: Literal["set_goal"]
    daily: Optional[int] = None
    weekly: Optional[int] = None
    monthly: Optional[int] = None

class GetReportAction(BaseModel):
    action: Literal["get_report"]
    period: Literal["daily", "weekly", "monthly"]
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class AskClarificationAction(BaseModel):
    action: Literal["ask_clarification"]
    message: str  

class RefuseAction(BaseModel):
    action: Literal["refuse"]
    message: str


# Action = Union[
#     LogMealAction,
#     EditMealAction,
#     DeleteMealAction,
#     SetGoalAction,
#     GetReportAction,
#     AskClarificationAction,
#     RefuseAction,
# ]

Action = Union[
    LogMealAction,
    EditMealAction,
    AskClarificationAction,
    RefuseAction,
]
