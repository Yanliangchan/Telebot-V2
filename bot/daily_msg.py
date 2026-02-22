from config.constants import DAILY_MSGS, CADET_CHAT_ID
from utils.time_utils import day_sg

from telegram.ext import ContextTypes


async def send_daily_msg(context: ContextTypes.DEFAULT_TYPE):
    today = day_sg()

    if today in DAILY_MSGS:
        await context.bot.send_message(
            chat_id=CADET_CHAT_ID,
            text=DAILY_MSGS[today],
            parse_mode="HTML",
        )

        print(f"---- {today} message sent ----")
