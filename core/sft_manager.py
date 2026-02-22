from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from services.db_service import SFTService
from db.crud import get_user_by_telegram_id


# =========================
# TIME HELPERS
# =========================

def _time_to_minutes(t: str) -> int:
    return int(t[:2]) * 60 + int(t[2:])


def _minutes_to_time(m: int) -> str:
    return f"{m // 60:02d}{m % 60:02d}"


def _generate_time_slots(start: str, end: str):
    """
    Generate 15-min interval times between start and end (inclusive).
    """
    start_m = _time_to_minutes(start)
    end_m = _time_to_minutes(end)

    return [
        _minutes_to_time(m)
        for m in range(start_m, end_m + 1, 15)
    ]


# =========================
# SFT CALLBACK HANDLER
# =========================
async def handle_sft_callbacks(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ------------------------------
    # SAFETY: window must exist
    # ------------------------------
    window = SFTService.get_window()
    if not window:
        await reply(
            update,
            "❌ PT SFT has not been opened by IC yet.\n"
            "Please wait for instructions."
        )
        context.user_data.clear()
        return

    # ------------------------------
    # Resolve user via Telegram ID
    # ------------------------------
    telegram_id = update.effective_user.id
    user = get_user_by_telegram_id(telegram_id)

    if not user:
        await reply(
            update,
            "❌ You are not registered in the system.\n"
            "Please contact the administrator."
        )
        context.user_data.clear()
        return

    context.user_data["user_id"] = user.id
    context.user_data["user_name"] = user.full_name

    # Precompute allowed times
    allowed_times = _generate_time_slots(window.start, window.end)
    context.user_data["allowed_times"] = allowed_times

    # ------------------------------
    # ACTIVITY SELECTED
    # ------------------------------
    if data.startswith("sft_activity|"):
        payload = data.split("|", 1)[1]

        if "|" in payload:
            activity, location = payload.split("|", 1)
        elif " @ " in payload:
            activity, location = payload.split(" @ ", 1)
            activity = activity.strip()
            location = location.strip()
        else:
            activity = payload.strip()
            location = ""

        context.user_data["activity"] = activity
        context.user_data["location"] = location

        keyboard = [
            [InlineKeyboardButton(t, callback_data=f"sft_start|{t}")]
            for t in allowed_times
        ]

        await reply(
            update,
            "Select *START* time:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ------------------------------
    # START TIME SELECTED
    # ------------------------------
    elif data.startswith("sft_start|"):
        start = data.split("|")[1]
        context.user_data["start"] = start

        end_times = [
            t for t in allowed_times
            if _time_to_minutes(t) > _time_to_minutes(start)
        ]

        keyboard = [
            [InlineKeyboardButton(t, callback_data=f"sft_end|{t}")]
            for t in end_times
        ]

        await reply(
            update,
            "Select *END* time:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ------------------------------
    # END TIME SELECTED → PREVIEW
    # ------------------------------
    elif data.startswith("sft_end|"):
        end = data.split("|")[1]
        start = context.user_data["start"]

        context.user_data["end"] = end

        preview = (
            f"📋 *SFT Submission Preview*\n\n"
            f"{context.user_data['user_name']}\n"
            f"{context.user_data['activity']}{(' @ ' + context.user_data['location']) if context.user_data['location'] else ''}\n"
            f"{start}-{end}\n\n"
            f"Confirm submission?"
        )

        keyboard = [[
            InlineKeyboardButton("✅ Confirm", callback_data="sft_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="sft_cancel"),
        ]]

        await reply(
            update,
            preview,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ------------------------------
    # CONFIRM SUBMISSION
    # ------------------------------
    elif data == "sft_confirm":
        try:
            SFTService.add_submission(
                user_id=context.user_data["user_id"],
                user_name=context.user_data["user_name"],
                activity=context.user_data["activity"],
                location=context.user_data["location"],
                start=context.user_data["start"],
                end=context.user_data["end"],
            )

        except ValueError as e:
            await reply(update, f"❌ {str(e)}")
            context.user_data.clear()
            return

        await reply(
            update,
            "✅ *SFT successfully submitted.*\n\n"
            f"{context.user_data['activity']}{(' @ ' + context.user_data['location']) if context.user_data['location'] else ''}\n"
            f"Time: {context.user_data['start']}-{context.user_data['end']}",
            parse_mode="Markdown",
        )

        context.user_data.clear()

    # ------------------------------
    # CANCEL
    # ------------------------------
    elif data == "sft_cancel":
        context.user_data.clear()
        await reply(update, "❌ SFT submission cancelled.")
