from bot.helpers import parade_state_cancel_button, reply
from bot.shared.state import reset_session
from config.constants import IC_GROUP_CHAT_ID, PARADE_STATE_TOPIC_ID
from services.auth_service import is_admin_user


async def start_parade_state(update, context):
    reset_session(context, mode="PARADE_STATE")

    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin_user(user_id):
        await reply(update, "❌ You are not authorized to generate parade state.")
        return

    await reply(
        update,
        "📋Parade State started.\n\nPlease input the number of out-of-camp personnel:",
        reply_markup=parade_state_cancel_button(),
    )


async def handle_parade_callbacks(update, context):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    if not is_admin_user(user_id):
        await query.edit_message_text("❌ You are not authorized to send parade state.")
        reset_session(context)
        return

    data = query.data
    text = context.user_data.get("generated_text")
    if not text and data != "parade|cancel":
        await query.edit_message_text("Session expired. Please start again.")
        reset_session(context)
        return

    if data == "parade|send":
        await context.bot.send_message(chat_id=IC_GROUP_CHAT_ID, message_thread_id=PARADE_STATE_TOPIC_ID, text=text)
        await query.edit_message_text("✅ Parade state sent.")
        reset_session(context)
        return

    if data == "parade|cancel":
        await query.edit_message_text("❌ Parade state cancelled.")
        reset_session(context)
