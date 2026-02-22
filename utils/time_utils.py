from datetime import datetime, time
import re
from db.crud import delete_expired_statuses_and_events
from utils.datetime_utils import SG_TZ, now_sg

DAILY_MSG_TIME = time(hour=8, minute=0)


def today_sg() -> str:
    return now_sg().strftime("%d%m%Y")


def day_sg() -> str:
    return now_sg().strftime("%A")


def now_hhmm() -> str:
    return now_sg().strftime("%H%M")


def is_valid_24h_time(value: str) -> bool:
    return bool(re.fullmatch(r"([01][0-9]|2[0-3])[0-5][0-9]", value))

def daily_reset(context=None):
    """Daily cleanup job to remove expired medical statuses/events."""
    today = now_sg().date()
    delete_expired_statuses_and_events(today)
