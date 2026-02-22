from telegram.ext import CallbackQueryHandler

from bot.features.movement import handle_movement_callbacks, movement_text_input
from bot.features.parade import handle_parade_callbacks
from bot.helpers import reply
from bot.shared.state import reset_session
from core.sft_manager import handle_sft_callbacks
from utils.rate_limiter import user_rate_limiter


async def callback_router(update, context):
    query = update.callback_query
    data = query.data

    user_id = update.effective_user.id if update.effective_user else None
    if not user_rate_limiter.allow(user_id, "callback_router", max_requests=25, window_seconds=10):
        await query.answer("Too many requests. Please slow down.", show_alert=False)
        return

    if data.startswith("mov"):
        context.user_data["mode"] = "MOVEMENT"
        await handle_movement_callbacks(update, context)
        return

    if data.startswith("sft"):
        context.user_data["mode"] = "SFT"
        await handle_sft_callbacks(update, context)
        return

    if data.startswith("parade"):
        context.user_data["mode"] = "PARADE_CONFIRM"
        await handle_parade_callbacks(update, context)


async def text_input_router(update, context):
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
        return

    if mode in {"report", "update", "ma_report", "rsi_report", "rsi_update", "update_ma"}:
        from bot.rso_handler import manual_input_handler
        await manual_input_handler(update, context)
        return

    if mode == "PARADE_STATE":
        from bot.parade_state import generate_parade_state
        await generate_parade_state(update, context)


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
        reset_session(context)
        await reply(update, "❌ Cancelled. Use /start_status to begin again.")


def register_status_handlers(dispatcher):
    from bot.rso_handler import (
        cancel,
        cancel_batch_send_handler,
        confirm_handler,
        confirm_ma_handler,
        confirm_ma_update_handler,
        confirm_rsi_report_handler,
        confirm_rsi_update_handler,
        continue_reporting_handler,
        done_reporting_handler,
        instructor_selection_handler,
        mc_days_button_handler,
        name_selection_handler,
        rsi_days_button_handler,
        rsi_status_type_handler,
        send_batch_to_ic_handler,
    )

    dispatcher.add_handler(CallbackQueryHandler(status_menu_handler, pattern=r"^status_menu\|"))
    dispatcher.add_handler(CallbackQueryHandler(name_selection_handler, pattern=r"^(name|rsi_name|update_name|update_ma_name|update_rsi_name)\|"))
    dispatcher.add_handler(CallbackQueryHandler(mc_days_button_handler, pattern=r"^mc_days\|"))
    dispatcher.add_handler(CallbackQueryHandler(confirm_handler, pattern=r"^confirm$"))
    dispatcher.add_handler(CallbackQueryHandler(cancel, pattern=r"^cancel$"))
    dispatcher.add_handler(CallbackQueryHandler(confirm_ma_handler, pattern=r"^confirm_ma$"))
    dispatcher.add_handler(CallbackQueryHandler(confirm_ma_update_handler, pattern=r"^confirm_ma_update$"))
    dispatcher.add_handler(CallbackQueryHandler(instructor_selection_handler, pattern=r"^instructor\|"))
    dispatcher.add_handler(CallbackQueryHandler(rsi_days_button_handler, pattern=r"^rsi_days\|"))
    dispatcher.add_handler(CallbackQueryHandler(rsi_status_type_handler, pattern=r"^rsi_type\|"))
    dispatcher.add_handler(CallbackQueryHandler(confirm_rsi_report_handler, pattern=r"^confirm_rsi_report$"))
    dispatcher.add_handler(CallbackQueryHandler(confirm_rsi_update_handler, pattern=r"^confirm_rsi_update$"))
    dispatcher.add_handler(CallbackQueryHandler(continue_reporting_handler, pattern=r"^continue_reporting\|"))
    dispatcher.add_handler(CallbackQueryHandler(done_reporting_handler, pattern=r"^done_reporting$"))
    dispatcher.add_handler(CallbackQueryHandler(send_batch_to_ic_handler, pattern=r"^send_batch_ic$"))
    dispatcher.add_handler(CallbackQueryHandler(cancel_batch_send_handler, pattern=r"^cancel_batch_send$"))
