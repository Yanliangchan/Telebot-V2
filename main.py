from config.settings import BOT_TOKEN
from config.constants import IC_GROUP_CHAT_ID
from services.db_service import DatabaseService

from bot.features.import_users import import_user, import_user_callback, import_user_document
from bot.features.debug import debug_ids
from bot.features.navigation import cancel, menu
from bot.features.movement import start_movement
from bot.features.parade import start_parade_state
from bot.features.sft import quit_sft, start_sft
from bot.features.start import start, start_menu_callback
from bot.features.status import start_status
from bot.router import callback_router, register_status_handlers, text_input_router

from bot.cet import cet_handler
from bot.daily_msg import send_daily_msg
from core.pt_sft_admin import start_pt_admin, handle_pt_admin_callbacks

from utils.time_utils import SG_TZ, DAILY_MSG_TIME

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)


def main():
    print("BOOT: main entered", flush=True)

    # -----------------------------
    # Initialise Database
    # -----------------------------
    DatabaseService.initialise()

    # -----------------------------
    # Build Telegram Application
    # -----------------------------
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------
    # Command Handlers
    # -----------------------------

    application.add_handler(
        MessageHandler(
            filters.Chat(chat_id=IC_GROUP_CHAT_ID)
            & (filters.TEXT | filters.CAPTION)
            & ~filters.COMMAND,
            cet_handler,
            block=False,
        )
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("start_sft", start_sft))
    application.add_handler(CommandHandler("quit_sft", quit_sft))
    application.add_handler(CommandHandler("start_status", start_status))
    application.add_handler(CommandHandler("start_movement", start_movement))
    application.add_handler(CommandHandler("pt_admin", start_pt_admin))
    application.add_handler(CommandHandler("pt_sft_admin", start_pt_admin))
    application.add_handler(CommandHandler("start_parade_state", start_parade_state))
    application.add_handler(CommandHandler("import_user", import_user))
    application.add_handler(CommandHandler("debug_ids", debug_ids))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("cancel", cancel))
    register_status_handlers(application)


    # -----------------------------
    # Callback Handlers (Buttons)
    # -----------------------------
    application.add_handler(
        CallbackQueryHandler(handle_pt_admin_callbacks, pattern=r"^ptadmin:")
    )
    application.add_handler(
        CallbackQueryHandler(start_menu_callback, pattern=r"^start_menu\|")
    )
    application.add_handler(
        CallbackQueryHandler(callback_router, pattern=r"^(mov|sft|parade)")
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_router)
    )
    application.add_handler(
        CallbackQueryHandler(import_user_callback, pattern=r"^import_user\|")
    )
    application.add_handler(
        MessageHandler(filters.Document.ALL, import_user_document)
    )


    # -----------------------------
    # Job Queue (Daily Message)
    # -----------------------------
    application.job_queue.scheduler.timezone = SG_TZ
    application.job_queue.run_daily(
        send_daily_msg,
        time=DAILY_MSG_TIME,
    )

    # -----------------------------
    # Start Bot (Polling)
    # -----------------------------
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    main()
