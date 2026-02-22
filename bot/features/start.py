from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from bot.shared.state import reset_session


async def start(update, context):
    reset_session(context)

    keyboard = [
        [InlineKeyboardButton("🏋️ Start SFT", callback_data="start_menu|start_sft")],
        [InlineKeyboardButton("🚶 Movement Report", callback_data="start_menu|start_movement")],
        [InlineKeyboardButton("📊 Status Report", callback_data="start_menu|start_status")],
        [InlineKeyboardButton("🪖 Parade State", callback_data="start_menu|start_parade_state")],
        [InlineKeyboardButton("🛠️ PT Admin", callback_data="start_menu|pt_admin")],
        [InlineKeyboardButton("📥 Import Users", callback_data="start_menu|import_user")],
        [InlineKeyboardButton("🪪 Debug IDs", callback_data="start_menu|debug_ids")],
    ]

    await reply(
        update,
        "👋 Welcome.\n\nChoose an action below:"
        "\n(Use /cancel anytime to reset your current flow.)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def start_menu_callback(update, context):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    _, action = query.data.split("|", 1)
    if action == "start_sft":
        from bot.features.sft import start_sft
        await start_sft(update, context)
        return
    if action == "start_movement":
        from bot.features.movement import start_movement
        await start_movement(update, context)
        return
    if action == "start_status":
        from bot.features.status import start_status
        await start_status(update, context)
        return
    if action == "start_parade_state":
        from bot.features.parade import start_parade_state
        await start_parade_state(update, context)
        return
    if action == "pt_admin":
        from core.pt_sft_admin import start_pt_admin
        await start_pt_admin(update, context)
        return
    if action == "import_user":
        from bot.features.import_users import import_user
        await import_user(update, context)
        return
    if action == "debug_ids":
        from bot.features.debug import debug_ids
        await debug_ids(update, context)
        return
