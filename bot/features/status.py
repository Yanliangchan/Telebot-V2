from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from bot.shared.state import reset_session
from db.crud import get_all_cadet_names, get_all_instructor_names


async def start_status(update, context):
    """Main menu for RSO/MA/RSI reporting."""
    reset_session(context)
    context.user_data["all_names"] = get_all_cadet_names()
    context.user_data["all_instructors"] = get_all_instructor_names()

    keyboard = [
        [InlineKeyboardButton("📋 Report RSO", callback_data="status_menu|report_rso")],
        [InlineKeyboardButton("✏️ Update RSO", callback_data="status_menu|update_rso")],
        [InlineKeyboardButton("🏥 Report MA", callback_data="status_menu|report_ma")],
        [InlineKeyboardButton("✏️ Update MA", callback_data="status_menu|update_ma")],
        [InlineKeyboardButton("🤒 Report RSI", callback_data="status_menu|report_rsi")],
        [InlineKeyboardButton("✏️ Update RSI", callback_data="status_menu|update_rsi")],
        [InlineKeyboardButton("❌ Cancel", callback_data="status_menu|cancel")],
    ]

    await reply(
        update,
        "📊 *Status Reporting Menu*\n\nSelect an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
