from bot.helpers import reply
from services.auth_service import is_admin_user


def _status_opt_out_set(context) -> set[int]:
    return context.bot_data.setdefault("status_notification_opt_out", set())


def admin_wants_status_notifications(context, admin_id: int) -> bool:
    return admin_id not in _status_opt_out_set(context)


async def notifications(update, context):
    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin_user(user_id):
        await reply(update, "❌ Only admins can configure notification preferences.")
        return

    args = getattr(context, "args", []) or []
    if len(args) != 2 or args[0].lower() != "status" or args[1].lower() not in {"on", "off"}:
        await reply(
            update,
            "Usage: /notifications status on|off\n"
            "Example: /notifications status off",
        )
        return

    toggle = args[1].lower()
    opt_out = _status_opt_out_set(context)

    if toggle == "off":
        opt_out.add(user_id)
        await reply(update, "🔕 Status notifications turned OFF for your account.")
        return

    opt_out.discard(user_id)
    await reply(update, "🔔 Status notifications turned ON for your account.")
