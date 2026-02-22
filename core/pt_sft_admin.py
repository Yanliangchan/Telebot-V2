import re
from datetime import datetime

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.helpers import reply
from config.constants import IC_GROUP_CHAT_ID, SFT_TOPIC_ID
from db.crud import get_all_instructor_names
from services.db_service import SFTService, set_sft_window
from services.auth_service import is_admin_user
from utils.rate_limiter import user_rate_limiter


SG_TZ = pytz.timezone("Asia/Singapore")


def today_sg():
    return datetime.now(SG_TZ).strftime("%d%m%Y")


def _valid_time_range(text: str):
    """
    Expects HHMM-HHMM
    """
    if not re.fullmatch(r"\d{4}-\d{4}", text):
        return None

    start, end = text.split("-")

    if not (start < end):
        return None

    hh1, mm1 = int(start[:2]), int(start[2:])
    hh2, mm2 = int(end[:2]), int(end[2:])

    if hh1 > 23 or hh2 > 23 or mm1 > 59 or mm2 > 59:
        return None

    return start, end

def _admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕒 Set SFT timing", callback_data="ptadmin:set_timing")],
        [InlineKeyboardButton("🗑️ Remove cadets from SFT", callback_data="ptadmin:remove")],
        [InlineKeyboardButton("📊 Generate SFT report", callback_data="ptadmin:generate")],
    ])


async def _show_admin_menu(update, context):
    context.user_data["mode"] = "PT_ADMIN"
    context.user_data["pt_admin_state"] = "menu"

    await reply(
        update,
        "📋 *PT Admin Panel*\n\nChoose an action:",
        reply_markup=_admin_menu_keyboard(),
        parse_mode="Markdown",
    )

# =========================
# ENTRY POINT
# =========================
async def start_pt_admin(update, context):
    if not is_admin_user(update.effective_user.id if update.effective_user else None):
        await reply(update, "❌ You are not authorised.")
        return

    user_id = update.effective_user.id if update.effective_user else None
    if not user_rate_limiter.allow(user_id, "start_pt_admin", max_requests=5, window_seconds=30):
        await reply(update, "⏳ Too many requests. Please wait a bit before accessing the PT Admin panel again.")
        return

    context.user_data.clear()
    await _show_admin_menu(update, context)


# =========================
# CALLBACK HANDLER
# =========================
async def handle_pt_admin_callbacks(update, context):
    if not is_admin_user(update.effective_user.id if update.effective_user else None):
        await reply(update, "❌ You are not authorised.")
        return

    context.user_data["mode"] = "PT_ADMIN"

    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "ptadmin:set_timing":
        context.user_data["mode"] = "PT_ADMIN"
        context.user_data["pt_admin_state"] = "awaiting_time_range"
        await reply(
            update,
            "🕒 Enter SFT time range in 24H format.\nExample: `1500-1700`\n\n"
            "⚠️ Setting a new timing will clear all existing SFT submissions.",
            parse_mode="Markdown",
        )
        return

    if data == "ptadmin:remove":
        window = SFTService.get_window()
        if not window:
            await reply(
                update,
                "❌ No active SFT timing found. Set timing first.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        submissions = SFTService.get_submissions_for_date(window.date)
        if not submissions:
            await reply(
                update,
                "ℹ️ No SFT submissions to remove for current window.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        keyboard = []
        for s in submissions:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ {s.user_name} ({s.start}-{s.end})",
                    callback_data=f"ptadmin:remove_user|{s.user_id}",
                )
            ])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="ptadmin:menu")])

        await reply(
            update,
            "Select submission(s) to remove:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("ptadmin:remove_user|"):
        user_id = int(data.split("|", 1)[1])
        removed = SFTService.remove_submission(user_id)
        message = "✅ Submission removed." if removed else "ℹ️ Submission already removed."
        await reply(update, message, reply_markup=_admin_menu_keyboard())
        return

    if data == "ptadmin:generate":
        window = SFTService.get_window()
        if not window:
            await reply(
                update,
                "❌ No active SFT timing found. Set timing first.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        instructor_names = get_all_instructor_names()
        if not instructor_names:
            await reply(
                update,
                "❌ No instructors found. Please import instructor data first.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"ptadmin:pick_instructor|{name}")]
            for name in instructor_names
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="ptadmin:menu")])

        await reply(
            update,
            "Select instructor for the SFT report greeting:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("ptadmin:pick_instructor|"):
        window = SFTService.get_window()
        if not window:
            await reply(
                update,
                "❌ No active SFT timing found. Set timing first.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        instructor_name = data.split("|", 1)[1]
        context.user_data["pending_sft_instructor"] = instructor_name

        salutation_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Sir", callback_data="ptadmin:pick_salutation|Sir"),
                InlineKeyboardButton("Mdm", callback_data="ptadmin:pick_salutation|Mdm"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="ptadmin:generate")],
        ])

        await reply(
            update,
            f"Select salutation for {instructor_name}:",
            reply_markup=salutation_keyboard,
        )
        return

    if data.startswith("ptadmin:pick_salutation|"):
        window = SFTService.get_window()
        if not window:
            await reply(
                update,
                "❌ No active SFT timing found. Set timing first.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        instructor_name = context.user_data.get("pending_sft_instructor")
        if not instructor_name:
            await reply(
                update,
                "❌ No instructor selected. Please generate report again.",
                reply_markup=_admin_menu_keyboard(),
            )
            return

        salutation = data.split("|", 1)[1]
        summary = SFTService.generate_summary(window.date, instructor_name, salutation)
        context.user_data["pending_sft_summary"] = summary


        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm & Send", callback_data="ptadmin:send_report")],
            [InlineKeyboardButton("⬅️ Back", callback_data="ptadmin:menu")],
        ])

        await reply(
            update,
            f"📋 *SFT Report Preview*\n\n{summary}",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return

    if data == "ptadmin:send_report":
        summary = context.user_data.get("pending_sft_summary")
        if not summary:
            await reply(update, "❌ No report preview found.", reply_markup=_admin_menu_keyboard())
            return

        await context.bot.send_message(
            chat_id=IC_GROUP_CHAT_ID,
            message_thread_id=SFT_TOPIC_ID,
            text=summary,
        )

        await reply(update, "✅ SFT report sent to IC chat.", reply_markup=_admin_menu_keyboard())
        context.user_data.pop("pending_sft_summary", None)
        context.user_data.pop("pending_sft_instructor", None)
        return

    if data == "ptadmin:menu":
        await _show_admin_menu(update, context)


# =========================
# TEXT HANDLER
# =========================
async def handle_pt_admin_text(update, context):
    if context.user_data.get("mode") != "PT_ADMIN":
        return

    if context.user_data.get("pt_admin_state") != "awaiting_time_range":
        return

    result = _valid_time_range(update.message.text.strip())
    if not result:
        await reply(update, "❌ Invalid format. Use HHMM-HHMM (24H).")
        return

    start, end = result
    date = today_sg()

    # Requirement: any new SFT timing clears all previous submissions.
    SFTService.clear_submissions()
    set_sft_window(date, start, end)

    await reply(
        update,
        f"✅ *PT SFT window set*\n\n"
        f"Date: {date}\n"
        f"Time: {start}-{end}\n\n"
        f"Cadets may now submit SFT.",
        reply_markup=_admin_menu_keyboard(),
        parse_mode="Markdown",
    )

    context.user_data["pt_admin_state"] = "menu"
async def start_pt_sft_admin(update, context):
    await start_pt_admin(update, context)