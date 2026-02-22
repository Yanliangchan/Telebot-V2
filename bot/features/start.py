from bot.helpers import reply
from bot.shared.state import reset_session


async def start(update, context):
    reset_session(context)
    await reply(
        update,
        "👋 Welcome.\n\n"
        "Use /start_sft for SFT reporting or /start_movement for movement reporting.",
    )
