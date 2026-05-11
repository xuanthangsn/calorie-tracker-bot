"""Standardized payloads between dispatcher and sessions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    session_id: str
    text: str


@dataclass(frozen=True)
class OutgoingMessage:
    session_id: str
    text: str
