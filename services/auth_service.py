from config.constants import ADMIN_IDS
from db.crud import get_admin_telegram_ids, get_user_by_telegram_id


def is_admin_user(user_id: int | None) -> bool:
    if user_id is None:
        return False

    if user_id in ADMIN_IDS:
        return True

    user = get_user_by_telegram_id(user_id)
    return bool(user and user.is_admin and user.is_active)


def get_all_admin_user_ids() -> list[int]:
    return sorted(set(ADMIN_IDS) | set(get_admin_telegram_ids()))
