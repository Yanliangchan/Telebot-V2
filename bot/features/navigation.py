from bot.features.start import start
from bot.helpers import reply
from bot.shared.state import reset_session


async def menu(update, context):
    await start(update, context)


async def cancel(update, context):
    reset_session(context)
    await reply(update, "❌ Cancelled. Use /menu to start again.")
