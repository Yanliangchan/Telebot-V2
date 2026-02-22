from datetime import datetime
import pytz
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.helpers import reply
from config.constants import IC_GROUP_CHAT_ID, MOVEMENT_TOPIC_ID, LOCATIONS

SG_TZ = pytz.timezone("Asia/Singapore")


def is_valid_time(value: str) -> bool:
    return bool(re.fullmatch(r"([01][0-9]|2[0-3])[0-5][0-9]", value))


# =========================
# CALLBACK HANDLER
# =========================
async def handle_movement_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ------------------------------
    # NAME TOGGLE
    # ------------------------------
    if data.startswith("move_name|"):
        name = data.split("|", 1)[1]
        selected = context.user_data.setdefault("selected", set())

        if name in selected:
            selected.remove(name)
        else:
            selected.add(name)

        keyboard = []
        for n in context.user_data["all_names"]:
            prefix = "☑️" if n in selected else "⬜"
            keyboard.append(
                [InlineKeyboardButton(f"{prefix} {n}", callback_data=f"move_name|{n}")]
            )

        keyboard.append(
            [InlineKeyboardButton("✅ Done Selecting", callback_data="move_done")]
        )

        await reply(update, "Select personnel moving:", InlineKeyboardMarkup(keyboard))

    # ------------------------------
    # DONE SELECTING
    # ------------------------------
    elif data == "move_done":
        if not context.user_data.get("selected"):
            await query.answer("Select at least one name!", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton(loc, callback_data=f"move_from|{loc}")]
            for loc in LOCATIONS
        ]
        await reply(update, "Select movement FROM:", InlineKeyboardMarkup(keyboard))

    # ------------------------------
    # FROM LOCATION
    # ------------------------------
    elif data.startswith("move_from|"):
        context.user_data["from"] = data.split("|", 1)[1]

        keyboard = [
            [InlineKeyboardButton(loc, callback_data=f"move_to|{loc}")]
            for loc in LOCATIONS
        ]
        await reply(update, "Select movement TO:", InlineKeyboardMarkup(keyboard))

    # ------------------------------
    # TO LOCATION
    # ------------------------------
    elif data.startswith("move_to|"):
        to_loc = data.split("|", 1)[1]
        from_loc = context.user_data["from"]

        if to_loc == from_loc:
            await query.answer("FROM and TO cannot be the same!", show_alert=True)
            return

        context.user_data["to"] = to_loc

        keyboard = [
            [InlineKeyboardButton("⏱ Use current time", callback_data="move_time|auto")],
            [InlineKeyboardButton("⌨️ Enter time manually", callback_data="move_time|manual")],
        ]
        await reply(update, "Select movement time:", InlineKeyboardMarkup(keyboard))

    # ------------------------------
    # TIME CHOICE
    # ------------------------------
    elif data.startswith("move_time|"):
        choice = data.split("|", 1)[1]

        if choice == "auto":
            context.user_data["time"] = datetime.now(SG_TZ).strftime("%H%M")
            await _show_preview(update, context)
        else:
            context.user_data["awaiting_time"] = True
            await reply(update, "Enter time in HHMM (24h):")

    elif data == "move_confirm":
        await handle_movement_confirm(update, context)

    elif data == "move_cancel":
        await reply(update, "❌ Movement report cancelled.")


# =========================
# MANUAL TIME INPUT
# =========================
async def handle_manual_time(update, context):
    if not context.user_data.get("awaiting_time"):
        return

    value = update.message.text.strip()
    if not is_valid_time(value):
        await reply(update, "❌ Invalid time. Use HHMM.")
        return

    context.user_data["awaiting_time"] = False
    context.user_data["time"] = value
    await _show_preview(update, context)


# =========================
# PREVIEW
# =========================
async def _show_preview(update, context):
    names = sorted(context.user_data["selected"])
    from_loc = context.user_data["from"]
    to_loc = context.user_data["to"]
    time_str = context.user_data["time"]

    msg = "Dear Instructors,\n\n"
    for i, name in enumerate(names, 1):
        msg += f"{i}. {name}\n"

    msg += f"\nMOVEMENT FROM {from_loc} TO {to_loc} @{time_str}HRS"

    context.user_data["final_message"] = msg

    keyboard = [[
        InlineKeyboardButton("✅ Confirm & Send", callback_data="move_confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="move_cancel"),
    ]]

    await reply(
        update,
        "📋 *Preview Movement Report*\n\n" + msg,
        InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# =========================
# CONFIRM SEND
# =========================
async def handle_movement_confirm(update, context):
    await context.bot.send_message(
        chat_id=IC_GROUP_CHAT_ID,
        message_thread_id=MOVEMENT_TOPIC_ID,
        text=context.user_data["final_message"],
    )
    await reply(update, "✅ Movement report sent.")
