from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def reply(update, text, reply_markup=None, parse_mode=None):
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

def parade_state_cancel_button():
    keyboard = [[InlineKeyboardButton("❌ Cancel Generation", callback_data="parade|cancel")]] 
    return InlineKeyboardMarkup(keyboard)