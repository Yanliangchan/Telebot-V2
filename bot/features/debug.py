from bot.helpers import reply


async def debug_ids(update, context):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    user_id = user.id if user else "Unknown"
    chat_id = chat.id if chat else "Unknown"
    thread_id = getattr(message, "message_thread_id", None)

    lines = [
        "🪪 Debug IDs",
        f"- Your Telegram user ID: `{user_id}`",
        f"- Current chat ID: `{chat_id}`",
    ]

    if thread_id is not None:
        lines.append(f"- Current topic/thread ID: `{thread_id}`")

    await reply(update, "\n".join(lines), parse_mode="Markdown")
