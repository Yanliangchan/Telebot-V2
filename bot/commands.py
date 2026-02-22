"""Backward-compatible command exports.

Use feature modules in ``bot.features`` for new code.
"""

from bot.features.import_users import import_user, import_user_callback, import_user_document
from bot.features.movement import start_movement
from bot.features.parade import start_parade_state
from bot.features.sft import quit_sft, start_sft
from bot.features.start import start
from bot.features.status import start_status

__all__ = [
    "start",
    "start_sft",
    "quit_sft",
    "start_movement",
    "start_status",
    "start_parade_state",
    "import_user",
    "import_user_document",
    "import_user_callback",
]
