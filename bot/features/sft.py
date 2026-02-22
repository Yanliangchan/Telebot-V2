from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from bot.shared.state import reset_session
from config.constants import ACTIVITIES
from db.crud import get_user_by_telegram_id
from services.db_service import SFTService, get_sft_window


async def start_sft(update, context):
    window = get_sft_window()
    if not window:
        await reply(
            update,
            "❌ PT SFT has not been opened by IC yet.\nPlease wait for instructions.",
        )
        return

    reset_session(context, mode="SFT")
    context.user_data.update({"start": window.start, "end": window.end, "date": window.date})

    keyboard = [[InlineKeyboardButton(activity, callback_data=f"sft_activity|{activity}")] for activity in ACTIVITIES]
    await reply(
        update,
        f"🏋️ *PT SFT Open*\n\nTime: {window.start}-{window.end}\n\nSelect activity:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def quit_sft(update, context):
    telegram_id = update.effective_user.id if update.effective_user else None
    if telegram_id is None:
        await reply(update, "❌ Unable to identify your account.")
        return

    user = get_user_by_telegram_id(telegram_id)
    if not user:
        await reply(update, "❌ You are not registered in the system.")
        return

    removed = SFTService.remove_submission(user.id)
    if removed:
        await reply(update, "✅ You have quit SFT. All your submitted SFT entries were removed.")
        return

    await reply(update, "ℹ️ You currently have no SFT submissions to remove.")
