from dataclasses import dataclass
import os


@dataclass(frozen=True)
class User:
    telegram_id: int
    full_name: str


class UserService:
    @staticmethod
    def _load_id_set(env_key: str):
        raw = os.getenv(env_key, "").strip()
        if not raw:
            return set()
        return {int(value.strip()) for value in raw.split(",") if value.strip()}

    @classmethod
    def require_user(cls, user):
        allowed_ids = cls._load_id_set("ALLOWED_USER_IDS")
        if allowed_ids and user.id not in allowed_ids:
            raise PermissionError("You are not authorized to use this bot.")
        return User(telegram_id=user.id, full_name=user.full_name or f"User {user.id}")

    @classmethod
    def require_admin(cls, user_id):
        admin_ids = cls._load_id_set("ADMIN_USER_IDS")
        if admin_ids and user_id not in admin_ids:
            raise PermissionError("Admin permissions required.")
