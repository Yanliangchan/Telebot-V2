from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from bot.shared.state import reset_session
from config.constants import IC_GROUP_CHAT_ID, LOCATIONS, MOVEMENT_TOPIC_ID
from core.report_manager import ReportManager
from db.crud import get_all_cadet_names
from services.auth_service import get_all_admin_user_ids
from utils.time_utils import is_valid_24h_time, now_hhmm


async def start_movement(update, context):
    reset_session(context, mode="MOVEMENT")
    names = get_all_cadet_names()
    context.user_data["selected"] = set()
    context.user_data["all_names"] = names

    keyboard = [[InlineKeyboardButton(f"⬜ {name}", callback_data=f"mov:name|{name}")] for name in names]
    keyboard.append([InlineKeyboardButton("✅ Done Selecting", callback_data="mov:done")])

    await reply(
        update,
        "🚶 *Movement reporting started*\n\nSelect personnel:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


def _movement_keyboard(context):
    names = context.user_data.get("all_names", [])
    selected = context.user_data.get("selected", set())
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if name in selected else '⬜'} {name}", callback_data=f"mov:name|{name}")]
        for name in names
    ]
    keyboard.append([InlineKeyboardButton("✅ Done Selecting", callback_data="mov:done")])
    return InlineKeyboardMarkup(keyboard)


def _location_keyboard(prefix: str):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(location, callback_data=f"{prefix}|{location}")] for location in LOCATIONS]
    )


async def handle_movement_callbacks(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("mov:name|"):
        _, name = data.split("|", 1)
        selected = context.user_data.setdefault("selected", set())
        if name in selected:
            selected.remove(name)
        else:
            selected.add(name)
        await query.edit_message_reply_markup(reply_markup=_movement_keyboard(context))
        return

    if data == "mov:done":
        if not context.user_data.get("selected"):
            await reply(update, "❌ Please select at least one cadet.")
            return
        context.user_data["awaiting_from"] = True
        await reply(update, "📍 Where are they moving from?", reply_markup=_location_keyboard("mov:from"))
        return

    if data.startswith("mov:from|"):
        _, from_loc = data.split("|", 1)
        context.user_data.update({"from": from_loc, "awaiting_from": False, "awaiting_to": True})
        await reply(update, "📍 Where are they moving to?", reply_markup=_location_keyboard("mov:to"))
        return

    if data.startswith("mov:to|"):
        _, to_loc = data.split("|", 1)
        if to_loc == context.user_data.get("from"):
            await reply(update, "❌ 'From' and 'To' locations cannot be the same.")
            return
        context.user_data.update({"to": to_loc, "awaiting_to": False, "awaiting_time": False})
        keyboard = [
            [InlineKeyboardButton("🕒 Use current time", callback_data="mov:time|now")],
            [InlineKeyboardButton("✍️ Enter time manually", callback_data="mov:time|manual")],
        ]
        await reply(update, "⏰ Select the time:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "mov:time|manual":
        context.user_data["awaiting_time"] = True
        await reply(update, "⏰ Enter time manually (HHMM).")
        return

    if data == "mov:time|now":
        await _prepare_movement_preview(update, context, now_hhmm())
        return

    if data == "mov:cancel":
        reset_session(context)
        await reply(update, "❌ Movement reporting cancelled.")
        return

    if data == "mov:confirm":
        msg = context.user_data.get("final_message")
        if not msg:
            await reply(update, "❌ No movement data found.")
            return

        await context.bot.send_message(chat_id=IC_GROUP_CHAT_ID, message_thread_id=MOVEMENT_TOPIC_ID, text=msg)
        for admin in get_all_admin_user_ids():
            await context.bot.send_message(chat_id=admin, text="Movement report sent:\n\n" + msg)

        await reply(update, "✅ Movement report sent.")
        reset_session(context)


async def _prepare_movement_preview(update, context, hhmm: str):
    msg = ReportManager.build_movement_message(
        names=context.user_data["selected"],
        from_loc=context.user_data["from"],
        to_loc=context.user_data["to"],
        time_hhmm=hhmm,
    )
    context.user_data["final_message"] = msg
    keyboard = [[
        InlineKeyboardButton("✅ Confirm & Send", callback_data="mov:confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="mov:cancel"),
    ]]
    await reply(update, "📋 Preview\n\n" + msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def movement_text_input(update, context):
    if context.user_data.get("mode") != "MOVEMENT":
        return

    value = update.message.text.strip()
    if context.user_data.get("awaiting_from"):
        if not value:
            await reply(update, "❌ Please enter a valid location.")
            return
        context.user_data.update({"from": value, "awaiting_from": False, "awaiting_to": True})
        await reply(update, "📍 Where are they moving to?")
        return

    if context.user_data.get("awaiting_to"):
        if not value:
            await reply(update, "❌ Please enter a valid location.")
            return
        context.user_data.update({"to": value, "awaiting_to": False, "awaiting_time": True})
        await reply(update, "⏰ What time? (HHMM)")
        return

    if context.user_data.get("awaiting_time"):
        if not is_valid_24h_time(value):
            await reply(update, "❌ Invalid time format (HHMM).")
            return
        context.user_data["awaiting_time"] = False
        await _prepare_movement_preview(update, context, value)
