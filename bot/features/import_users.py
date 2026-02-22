import os
import tempfile
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from bot.shared.state import reset_session
from config.constants import MAX_IMPORT_CSV_SIZE_BYTES
from db.crud import clear_all_data, clear_user_data, list_users
from db.import_users_csv import import_users
from services.auth_service import is_admin_user
from utils.datetime_utils import now_sg
from utils.rate_limiter import user_rate_limiter

CLEAR_CONFIRM_WINDOW_MINUTES = 10
_pending_clear_request: dict[str, object] = {"admins": set(), "expires_at": None}


def _is_admin(user_id: int | None) -> bool:
    return is_admin_user(user_id)


def _clear_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Confirm clear database", callback_data="import_user|confirm_clear")],
        [InlineKeyboardButton("❌ Cancel clear request", callback_data="import_user|cancel_clear")],
    ])


def _reset_clear_request() -> None:
    _pending_clear_request["admins"] = set()
    _pending_clear_request["expires_at"] = None


def _is_request_expired() -> bool:
    expires_at = _pending_clear_request.get("expires_at")
    return bool(expires_at and now_sg() > expires_at)


async def import_user(update, context):
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_admin(user_id):
        await reply(update, "❌ You are not authorized to use /import_user.")
        return

    if not user_rate_limiter.allow(user_id, "import_user_cmd", max_requests=4, window_seconds=30):
        await reply(update, "⏳ Too many requests. Please wait a bit before using /import_user again.")
        return

    reset_session(context)
    keyboard = [
        [InlineKeyboardButton("📥 Import users (CSV)", callback_data="import_user|import")],
        [InlineKeyboardButton("👥 Display current users", callback_data="import_user|list")],
        [InlineKeyboardButton("🧹 Clear database", callback_data="import_user|clear")],
    ]
    await reply(update, "Choose an action:", reply_markup=InlineKeyboardMarkup(keyboard))


async def import_user_callback(update, context):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    if not _is_admin(user_id):
        await reply(update, "❌ You are not authorized to manage imports.")
        return

    _, action = query.data.split("|", 1)

    if action == "import":
        reset_session(context, mode="IMPORT_USER")
        context.user_data["import_clear"] = True
        await reply(
            update,
            "📥 Send the CSV file to import users. Existing users and medical records will be cleared before import.",
        )
        return

    if action == "clear":
        if _is_request_expired():
            _reset_clear_request()

        admins = _pending_clear_request["admins"]
        if user_id not in admins:
            admins.add(user_id)

        if len(admins) == 1:
            _pending_clear_request["expires_at"] = now_sg() + timedelta(minutes=CLEAR_CONFIRM_WINDOW_MINUTES)
            await reply(
                update,
                "⚠️ Clear-database request initiated by Admin #1.\n"
                "A different admin must provide Admin #2 confirmation within "
                f"{CLEAR_CONFIRM_WINDOW_MINUTES} minutes.\n\n"
                "Any admin can press confirm below to continue.",
                reply_markup=_clear_confirm_keyboard(),
            )
            return

        await _clear_database_now(update)
        return

    if action == "confirm_clear":
        if _is_request_expired():
            _reset_clear_request()
            await reply(update, "⌛ Clear request expired. Please start again using '🧹 Clear database'.")
            return

        admins = _pending_clear_request["admins"]
        if user_id in admins and len(admins) < 2:
            await reply(update, "⚠️ Waiting for a second different admin confirmation.")
            return

        admins.add(user_id)
        if len(admins) < 2:
            await reply(update, "⚠️ Waiting for a second different admin confirmation.")
            return

        await _clear_database_now(update)
        return

    if action == "cancel_clear":
        _reset_clear_request()
        await reply(update, "❌ Clear-database request cancelled.")
        return

    if action == "list":
        users = list_users()
        if not users:
            await reply(update, "No users found.")
            return
        lines = ["Current users:"]
        for user in users[:200]:
            admin_flag = " (admin)" if user.is_admin else ""
            lines.append(f"- {user.rank} {user.full_name} [{user.role}]{admin_flag}")
        if len(users) >= 200:
            lines.append("\nShowing first 200 users.")
        await reply(update, "\n".join(lines))


async def _clear_database_now(update):
    cleared = clear_all_data()
    _reset_clear_request()
    await reply(
        update,
        "✅ Database fully cleared after 2-admin confirmation.\n\n"
        f"Users: {cleared['users']}\n"
        f"Medical events: {cleared['medical_events']}\n"
        f"Medical statuses: {cleared['medical_statuses']}\n"
        f"Movement logs: {cleared['movement_logs']}\n"
        f"SFT sessions: {cleared['sft_sessions']}\n"
        f"SFT submissions: {cleared['sft_submissions']}",
    )


async def import_user_document(update, context):
    if context.user_data.get("mode") != "IMPORT_USER":
        return

    user_id = update.effective_user.id if update.effective_user else None
    if not _is_admin(user_id):
        await reply(update, "❌ You are not authorized to import users.")
        return

    if not user_rate_limiter.allow(user_id, "import_user_document", max_requests=3, window_seconds=60):
        await reply(update, "⏳ Too many import attempts. Please wait 1 minute and try again.")
        return

    document = update.message.document if update.message else None
    if document and document.file_size and document.file_size > MAX_IMPORT_CSV_SIZE_BYTES:
        max_size_mb = MAX_IMPORT_CSV_SIZE_BYTES // (1024 * 1024)
        await reply(update, f"❌ File too large. Maximum allowed size is {max_size_mb} MB.")
        return

    clear_first = bool(context.user_data.get("import_clear"))
    reset_session(context)
    await _handle_import_csv(update, context, clear_first)


async def _handle_import_csv(update, context, clear_first: bool):
    document = update.message.document if update.message else None
    if not document:
        await reply(update, "❌ Please attach a CSV file for import.")
        return

    if not document.file_name or not document.file_name.lower().endswith(".csv"):
        await reply(update, "❌ Only .csv files are supported.")
        return

    if clear_first:
        cleared = clear_user_data()
        await reply(
            update,
            "🧹 Cleared existing data: "
            f"{cleared['users']} users, "
            f"{cleared['medical_events']} medical events, "
            f"{cleared['medical_statuses']} medical statuses.",
        )

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(tmp_path)
        result = import_users(tmp_path)
    except ValueError as exc:
        await reply(update, f"❌ Import failed: {exc}")
        return
    except Exception:
        await reply(update, "❌ Import failed due to an unexpected error.")
        return
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    await reply(
        update,
        "✅ Import complete. "
        f"Processed: {result['processed']}, created: {result['created']}, updated: {result['updated']}.",
    )
