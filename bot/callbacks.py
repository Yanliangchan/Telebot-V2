"""Backward-compatible callback exports.

Use ``bot.router`` and feature modules for new code.
"""

from bot.features.movement import handle_movement_callbacks, movement_text_input
from bot.features.parade import handle_parade_callbacks
from bot.router import callback_router, register_status_handlers, text_input_router

__all__ = [
    "callback_router",
    "text_input_router",
    "register_status_handlers",
    "handle_movement_callbacks",
    "movement_text_input",
    "handle_parade_callbacks",
]
