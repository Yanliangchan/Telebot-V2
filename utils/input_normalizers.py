from datetime import date, datetime, time


def parse_date_flexible(value: str) -> date:
    raw = (value or "").strip()
    for fmt in ("%d%m%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid date format. Use DDMMYY or YYYY-MM-DD.")


def to_ddmmyy(value: str) -> str:
    return parse_date_flexible(value).strftime("%d%m%y")


def to_yyyy_mm_dd(value: str) -> str:
    return parse_date_flexible(value).strftime("%Y-%m-%d")


def parse_time_flexible(value: str) -> time:
    raw = (value or "").strip()
    normalized = raw.replace(":", "")
    if len(normalized) != 4 or not normalized.isdigit():
        raise ValueError("Invalid time format. Use HHMM or HH:MM.")
    return datetime.strptime(normalized, "%H%M").time()


def to_hhmm(value: str) -> str:
    return parse_time_flexible(value).strftime("%H%M")
