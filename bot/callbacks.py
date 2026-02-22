from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from bot.helpers import reply
from core.report_manager import ReportManager
from utils.time_utils import is_valid_24h_time, now_hhmm
from config.constants import (
    IC_GROUP_CHAT_ID,
    MOVEMENT_TOPIC_ID,
    LOCATIONS,
    PARADE_STATE_TOPIC_ID
)

# IMPORTANT: import ONLY the real SFT handler
from core.sft_manager import handle_sft_callbacks
from services.auth_service import is_admin_user
from services.auth_service import get_all_admin_user_ids
from utils.rate_limiter import user_rate_limiter

# ==================================================
# CALLBACK ROUTER
# ==================================================
async def callback_router(update, context):
    """
    Central router for all inline button callbacks.
    Routes by callback_data prefix (NOT fragile mode state).
    """
    query = update.callback_query
    data = query.data

    user_id = update.effective_user.id if update.effective_user else None
    if not user_rate_limiter.allow(user_id, "callback_router", max_requests=25, window_seconds=10):
        await query.answer("Too many requests. Please slow down.", show_alert=False)
        return
    
    # ------------------------------
    # MOVEMENT (always starts with "mov")
    # ------------------------------
    if data.startswith("mov"):
        context.user_data["mode"] = "MOVEMENT"
        await handle_movement_callbacks(update, context)
        return

    # ------------------------------
    # SFT (always starts with "sft")
    # ------------------------------
    if data.startswith("sft"):
        context.user_data["mode"] = "SFT"
        await handle_sft_callbacks(update, context)
        return

    # ------------------------------
    # PT ADMIN
    # ------------------------------
    if data.startswith("ptadmin"):
        context.user_data["mode"] = "PT_ADMIN"
        from core.pt_sft_admin import handle_pt_admin_callbacks
        await handle_pt_admin_callbacks(update, context)
        return

    # ------------------------------
    # PARADE STATE (always starts with "parade")
    # ------------------------------

    if data.startswith("parade"):
        context.user_data["mode"] = "PARADE_CONFIRM"
        await handle_parade_callbacks(update, context)
        return


    # ------------------------------
    # STATUS/import-user callbacks are handled by pattern handlers
    # ------------------------------
    return


# ==================================================
# TEXT INPUT ROUTER
# ==================================================
async def text_input_router(update, context):
    """
    Routes free-text input based on mode.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not user_rate_limiter.allow(user_id, "text_input_router", max_requests=12, window_seconds=15):
        await reply(update, "⏳ Too many messages in a short time. Please slow down.")
        return
    
    mode = context.user_data.get("mode")

    if mode == "MOVEMENT":
        await movement_text_input(update, context)
        return

    if mode == "PT_ADMIN":
        from core.pt_sft_admin import handle_pt_admin_text
        await handle_pt_admin_text(update, context)

    if mode in {
        "report",
        "update",
        "ma_report",
        "rsi_report",
        "rsi_update",
        "update_ma",
    }:
        from bot.rso_handler import manual_input_handler
        await manual_input_handler(update, context)

    if mode == "PARADE_STATE":
        from bot.parade_state import generate_parade_state
        await generate_parade_state(update, context)


# ==================================================
# STATUS MENU HANDLER
# ==================================================
async def status_menu_handler(update, context):
    query = update.callback_query
    await query.answer()
    _, action = query.data.split("|", 1)

    if action == "report_rso":
        from bot.rso_handler import start_status_report
        await start_status_report(update, context)

    elif action == "update_rso":
        from bot.rso_handler import start_update_status
        await start_update_status(update, context)

    elif action == "report_ma":
        from bot.rso_handler import start_ma_report
        await start_ma_report(update, context)

    elif action == "update_ma":
        from bot.rso_handler import update_endorsed
        await update_endorsed(update, context)

    elif action == "report_rsi":
        from bot.rso_handler import start_rsi_report
        await start_rsi_report(update, context)

    elif action == "update_rsi":
        from bot.rso_handler import start_update_rsi
        await start_update_rsi(update, context)

    elif action == "cancel":
        context.user_data.clear()
        await reply(update, "❌ Cancelled. Use /start_status to begin again.")


def register_status_handlers(dispatcher):
    """
    Registers all status-related callback handlers.
    These are pattern-based and bypass the main router.
    """
    from bot.rso_handler import (
        name_selection_handler,
        confirm_handler,
        cancel,
        mc_days_button_handler,
        confirm_ma_handler,
        confirm_ma_update_handler,
        instructor_selection_handler,
        rsi_days_button_handler,
        rsi_status_type_handler,
        confirm_rsi_report_handler,
        confirm_rsi_update_handler,
        continue_reporting_handler,
        done_reporting_handler,
        send_batch_to_ic_handler,
        cancel_batch_send_handler,
    )

    dispatcher.add_handler(
        CallbackQueryHandler(status_menu_handler, pattern=r"^status_menu\|")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            name_selection_handler,
            pattern=r"^(name|rsi_name|update_name|update_ma_name|rsi_update_name)\|",
        )
    )
    dispatcher.add_handler(
        CallbackQueryHandler(mc_days_button_handler, pattern=r"^mc_days\|")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(confirm_handler, pattern=r"^confirm$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(cancel, pattern=r"^cancel$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(confirm_ma_handler, pattern=r"^confirm_ma$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(confirm_ma_update_handler, pattern=r"^confirm_ma_update$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(instructor_selection_handler, pattern=r"^instructor\|")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(rsi_days_button_handler, pattern=r"^rsi_days\|")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(rsi_status_type_handler, pattern=r"^rsi_type\|")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            confirm_rsi_report_handler, pattern=r"^confirm_rsi_report$"
        )
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            confirm_rsi_update_handler, pattern=r"^confirm_rsi_update$"
        )
    )
    dispatcher.add_handler(
        CallbackQueryHandler(continue_reporting_handler, pattern=r"^continue_reporting\|")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(done_reporting_handler, pattern=r"^done_reporting$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(send_batch_to_ic_handler, pattern=r"^send_batch_ic$")
    )
    dispatcher.add_handler(
        CallbackQueryHandler(cancel_batch_send_handler, pattern=r"^cancel_batch_send$")
    )


# ==================================================
# MOVEMENT CALLBACKS
# ==================================================
async def handle_movement_callbacks(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    def build_movement_keyboard():
        names = context.user_data.get("all_names", [])
        selected = context.user_data.get("selected", set())
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if name in selected else '⬜'} {name}",
                    callback_data=f"mov:name|{name}",
                )
            ]
            for name in names
        ]
        keyboard.append(
            [InlineKeyboardButton("✅ Done Selecting", callback_data="mov:done")]
        )
        return InlineKeyboardMarkup(keyboard)

    def build_location_keyboard(prefix: str):
        keyboard = [
            [InlineKeyboardButton(location, callback_data=f"{prefix}|{location}")]
            for location in LOCATIONS
        ]
        return InlineKeyboardMarkup(keyboard)

    def build_time_keyboard():
        keyboard = [
            [InlineKeyboardButton("🕒 Use current time", callback_data="mov:time|now")],
            [InlineKeyboardButton("✍️ Enter time manually", callback_data="mov:time|manual")],
        ]
        return InlineKeyboardMarkup(keyboard)

    if data.startswith("mov:name|"):
        _, name = data.split("|", 1)
        selected = context.user_data.setdefault("selected", set())
        if name in selected:
            selected.remove(name)
        else:
            selected.add(name)
        await query.edit_message_reply_markup(
            reply_markup=build_movement_keyboard()
        )
        return

    if data == "mov:done":
        selected = context.user_data.get("selected", set())
        if not selected:
            await reply(update, "❌ Please select at least one cadet.")
            return
        context.user_data["awaiting_from"] = True
        await reply(
            update,
            "📍 Where are they moving from?",
            reply_markup=build_location_keyboard("mov:from"),
        )
        return

    if data.startswith("mov:from|"):
        _, from_loc = data.split("|", 1)
        context.user_data["from"] = from_loc
        context.user_data["awaiting_from"] = False
        context.user_data["awaiting_to"] = True
        await reply(
            update,
            "📍 Where are they moving to?",
            reply_markup=build_location_keyboard("mov:to"),
        )
        return

    if data.startswith("mov:to|"):
        _, to_loc = data.split("|", 1)
        if to_loc == context.user_data.get("from"):
            await reply(update, "❌ 'From' and 'To' locations cannot be the same.")
            return
        context.user_data["to"] = to_loc
        context.user_data["awaiting_to"] = False
        context.user_data["awaiting_time"] = False
        await reply(
            update,
            "⏰ Select the time:",
            reply_markup=build_time_keyboard(),
        )
        return

    if data == "mov:time|now":
        time_hhmm = now_hhmm()
        msg = ReportManager.build_movement_message(
            names=context.user_data["selected"],
            from_loc=context.user_data["from"],
            to_loc=context.user_data["to"],
            time_hhmm=time_hhmm,
        )
        context.user_data["final_message"] = msg
        keyboard = [[
            InlineKeyboardButton("✅ Confirm & Send", callback_data="mov:confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="mov:cancel"),
        ]]
        await reply(
            update,
            "📋 Preview\n\n" + msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "mov:time|manual":
        context.user_data["awaiting_time"] = True
        await reply(update, "⏰ Enter time manually (HHMM).")
        return

    if data == "mov:confirm":
        msg = context.user_data.get("final_message")
        if not msg:
            await reply(update, "❌ No movement data found.")
            return

    if data == "mov:cancel":
        context.user_data.clear()
        await reply(update, "❌ Movement reporting cancelled.")
        return

    # Send to IC group
    await context.bot.send_message(
        chat_id=IC_GROUP_CHAT_ID,
        message_thread_id=MOVEMENT_TOPIC_ID,
        text=msg,
    )

    # Notify admins
    for admin in get_all_admin_user_ids():
        await context.bot.send_message(
            chat_id=admin,
            text="Movement report sent:\n\n" + msg,
        )

    await reply(update, "✅ Movement report sent.")


# ==================================================
# MOVEMENT TEXT INPUT
# ==================================================
async def movement_text_input(update, context):
    if context.user_data.get("mode") != "MOVEMENT":
        return

    if context.user_data.get("awaiting_from"):
        value = update.message.text.strip()
        if not value:
            await reply(update, "❌ Please enter a valid location.")
            return
        context.user_data["from"] = value
        context.user_data["awaiting_from"] = False
        context.user_data["awaiting_to"] = True
        await reply(update, "📍 Where are they moving to?")
        return

    if context.user_data.get("awaiting_to"):
        value = update.message.text.strip()
        if not value:
            await reply(update, "❌ Please enter a valid location.")
            return
        context.user_data["to"] = value
        context.user_data["awaiting_to"] = False
        context.user_data["awaiting_time"] = True
        await reply(update, "⏰ What time? (HHMM)")
        return

    if not context.user_data.get("awaiting_time"):
        return

    value = update.message.text.strip()

    if not is_valid_24h_time(value):
        await reply(update, "❌ Invalid time format (HHMM).")
        return

    context.user_data["time"] = value
    context.user_data["awaiting_time"] = False

    msg = ReportManager.build_movement_message(
        names=context.user_data["selected"],
        from_loc=context.user_data["from"],
        to_loc=context.user_data["to"],
        time_hhmm=value,
    )

    context.user_data["final_message"] = msg

    keyboard = [[
        InlineKeyboardButton("✅ Confirm & Send", callback_data="mov:confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="mov:cancel"),
    ]]

    await reply(
        update,
        "📋 Preview\n\n" + msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _can_send_parade_state(user_id: int | None) -> bool:
    return is_admin_user(user_id)

# ==================================================
# PARADE STATE CALLBACKS
# ==================================================
async def handle_parade_callbacks(update, context):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    if not _can_send_parade_state(user_id):
        await query.edit_message_text("❌ You are not authorized to send parade state.")
        context.user_data.clear()
        return
    
    data = query.data
    text = context.user_data.get("generated_text")

    thread_id = PARADE_STATE_TOPIC_ID
    chat_id = IC_GROUP_CHAT_ID

    if not text and not data == "parade|cancel":
        await query.edit_message_text("Session expired. Please start again.")
        context.user_data.clear()
        return

    if data == "parade|send":
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=text
        )
        await query.edit_message_text("✅ Parade state sent.")
        context.user_data.clear()

    elif data == "parade|cancel":
        await query.edit_message_text("❌ Parade state cancelled.")
        context.user_data.clear()
