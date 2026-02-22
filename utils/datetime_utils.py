from datetime import datetime
import pytz

SG_TZ = pytz.timezone("Asia/Singapore")


def now_sg() -> datetime:
    return datetime.now(SG_TZ)
