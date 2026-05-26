"""Standardized payloads between dispatcher and sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IncomingMessage:
    session_id: str
    text: str


@dataclass(frozen=True)
class OutgoingMessage:
    session_id: str
    text: str


@dataclass(frozen=True)
class SessionInboundMsg:
    message: str
    time: datetime


@dataclass(frozen=True)
class SessionOutboundMsg:
    session_id: str
    message: str
    time: datetime
