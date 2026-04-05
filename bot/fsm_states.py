"""Aiogram FSM states."""
from aiogram.fsm.state import State, StatesGroup


class TrackerStates(StatesGroup):
    default = State()
    awaiting_clarification = State()
