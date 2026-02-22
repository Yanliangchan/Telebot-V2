from config.constants import (
    IC_GROUP_CHAT_ID,
    CET_TOPIC_ID,
    CADET_CET_TOPIC_ID,
    CADET_CHAT_ID,
    CET_KEYWORDS,
)
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _message_text(msg) -> str:
    """Returns text content from either message text or caption."""
    return (msg.text or msg.caption or "").strip()


def _should_forward_cet(text: str) -> bool:
    """Determines whether a message is CET content that should be mirrored."""
    lowered = text.lower()

    return any(word.lower() in lowered for word in CET_KEYWORDS)

async def cet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if not msg:
        return

    text = _message_text(msg)
    if not text:
        return

    if msg.chat_id != IC_GROUP_CHAT_ID:
        return

    if msg.message_thread_id != CET_TOPIC_ID:
        return

    if not _should_forward_cet(text):
        return

    try:
        await context.application.bot.copy_message(
            chat_id=CADET_CHAT_ID,
            message_thread_id=CADET_CET_TOPIC_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
        )

    except Exception as exc:
        logger.exception("Failed to copy CET into cadet CET topic: %s", exc)
        # Fallback to cadet chat without topic so CET is still delivered.
        await context.application.bot.copy_message(
            chat_id=CADET_CHAT_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
        )

    cet_title = text.split("\n")[0]
    print(f"--- {cet_title} sent ---")
