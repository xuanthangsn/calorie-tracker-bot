"""Chat layer: queue-based dispatcher and session bases (see implementation_plan/chat_system.md)."""

from chat.dispatcher import BaseDispatcher
from chat.messages import IncomingMessage, OutgoingMessage
from chat.session import BaseChatSession

__all__ = [
    "BaseChatSession",
    "BaseDispatcher",
    "IncomingMessage",
    "OutgoingMessage",
]
