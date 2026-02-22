from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import CallbackContext



from db.crud import (
    get_user_records,
    update_user_record,
    create_user_record,
    get_ma_records,
    create_ma_record,
    update_ma_record,
    get_user_rsi_records,
    create_rsi_record,
    update_rsi_record,
    get_all_cadet_names,
    get_all_instructor_names,
)

from bot.helpers import reply
from services.auth_service import get_all_admin_user_ids

from config.constants import IC_GROUP_CHAT_ID, PARADE_STATE_TOPIC_ID, CADET_CHAT_ID
from utils.input_normalizers import to_ddmmyy, to_hhmm

# ------------ Common Utility Functions ------------ #

def set_mode(context: CallbackContext, mode: str):
    context.user_data["mode"] = mode


def reset_entry_state(context: CallbackContext):
    keep_keys = {"all_names", "all_instructors", "pending_reports", "mode"}
    preserved = {
        key: value
        for key, value in context.user_data.items()
        if key in keep_keys
    }
    context.user_data.clear()
    context.user_data.update(preserved)


def add_pending_report(context: CallbackContext, report: dict):
    pending = context.user_data.setdefault("pending_reports", [])
    pending.append(report)


def cadet_already_in_batch(context: CallbackContext, name: str, mode: str) -> bool:
    """Check if a cadet with the same name is already in the batch for new reports."""
    # Only check for new reports (report and rsi_report), not updates
    if mode not in ["report", "rsi_report"]:
        return False

    pending = context.user_data.get("pending_reports", [])
    for report in pending:
        # Check if same cadet already reported in the same mode (or compatible modes)
        report_name = report.get("name", "")
        report_mode = report.get("mode", "")
        # For RSO: check "report" mode; for RSI: check "rsi_report" mode
        if report_name and report_name.lower() == name.lower():
            if (mode == "report" and report_mode == "report") or (mode == "rsi_report" and report_mode == "rsi_report"):
                return True
    return False


def has_nonempty_value(value: str | None) -> bool:
    return bool(value and value.strip())


def pending_update_exists(context: CallbackContext, record_id: int | None, modes: set[str]) -> bool:
    if record_id is None:
        return False
    pending = context.user_data.get("pending_reports", [])
    for report in pending:
        if report.get("record_id") == record_id and report.get("mode") in modes:
            return True
    return False


def mark_action_once(context: CallbackContext, action_key: str) -> bool:
    completed = context.user_data.setdefault("completed_actions", set())
    if action_key in completed:
        return False
    completed.add(action_key)
    return True


def format_pending_reports(reports: list[dict], mode: str) -> str:
    lines = []
    if mode =='rsi_report' or mode == 'rsi_update':
        lines.append("RSI")
    elif mode == 'report' or mode == 'update':
        lines.append("RSO")
    for idx, report in enumerate(reports, 1):
        name = report.get("name", "N/A")
        symptoms = report.get("symptoms", "")
        diagnosis = report.get("diagnosis", "")
        status = report.get("status", "")

        lines.append(f"{idx}. {name}")
        lines.append(f"SYMPTOMS: {symptoms}")
        lines.append(f"DIAGNOSIS: {diagnosis}")
        lines.append(f"STATUS: {status}")
        lines.append("")
    return "\n".join(lines).strip()


def persist_pending_reports(reports: list[dict]):
    for report in reports:
        mode = report.get("mode")
        if mode == "report":
            create_user_record(
                name=report.get("name", ""),
                symptoms=report.get("symptoms", ""),
                diagnosis=report.get("diagnosis", ""),
            )
        elif mode == "update":
            update_user_record(
                record_id=report.get("record_id"),
                symptoms=report.get("symptoms", ""),
                diagnosis=report.get("diagnosis", ""),
                status=report.get("status", ""),
                start_date=report.get("start_date", ""),
                end_date=report.get("end_date", ""),
            )
        elif mode == "rsi_report":
            create_rsi_record(
                name=report.get("name", ""),
                symptoms=report.get("symptoms", ""),
                diagnosis=report.get("diagnosis", ""),
            )
        elif mode == "rsi_update":
            update_rsi_record(
                record_id=report.get("record_id"),
                diagnosis=report.get("diagnosis", ""),
                status_type=report.get("status_type", "MC"),
                status=report.get("status", ""),
                start_date=report.get("start_date", ""),
                end_date=report.get("end_date", ""),
            )


def make_name_keyboard(context, prefix: str) -> InlineKeyboardMarkup:
    names = context.user_data.get('all_names', [])
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"{prefix}|{name}")]
        for name in names
    ]
    return InlineKeyboardMarkup(keyboard)


async def prompt_name_selection(update: Update, context: CallbackContext, mode: str, prompt: str, prefix: str):
    set_mode(context, mode)
    await reply(update, prompt, reply_markup=make_name_keyboard(context, prefix))


async def send_to_ic_group(update: Update, context: CallbackContext, message: str):
    await context.bot.send_message(
        chat_id=IC_GROUP_CHAT_ID,
        text=message,
        message_thread_id=PARADE_STATE_TOPIC_ID,
    )
    await notify_admins(update, context, message, destination_label="IC parade thread")

async def send_to_cadet_chat(update: Update, context: CallbackContext, message: str):
    await context.bot.send_message(
        chat_id=CADET_CHAT_ID,
        text=message,
    )


def _actor_label(update: Update | None) -> str:
    actor = update.effective_user if update else None
    if not actor:
        return "Unknown user"
    if actor.username:
        return f"@{actor.username}"
    return actor.full_name


async def notify_admins(update: Update, context: CallbackContext, message: str, destination_label: str):
    actor = _actor_label(update)
    payload = f"🔔 Status update by {actor} sent to {destination_label}:\n\n{message}"
    sender_id = update.effective_user.id if update and update.effective_user else None

    for admin_id in get_all_admin_user_ids():
        if sender_id and admin_id == sender_id:
            continue
        try:
            await context.bot.send_message(chat_id=admin_id, text=payload)
        except TelegramError:
            continue


# ------------ Common Handlers for RSO, RSI and MA ------------ #

async def name_selection_handler(update: Update, context: CallbackContext):  # manual input for symptoms
    query = update.callback_query
    await query.answer()
    key, name = query.data.split("|", 1)

    if key == "name" and context.user_data.get("mode") == "report":
        # Check for duplicate cadets in batch for new RSO reports
        if cadet_already_in_batch(context, name, "report"):
            await reply(update, f"{name} is already in this batch. Cannot report the same cadet twice.")
            return

        context.user_data["name"] = name
        context.user_data["symptoms"] = ""
        context.user_data["awaiting_symptoms"] = True
        await reply(update, f"Name selected: {name}. Describe your symptoms.")
        return

    if key == "name" and context.user_data.get("mode") == "ma_report":
        context.user_data["name"] = name
        context.user_data["awaiting_appointment"] = True
        await reply(
            update,
            f"Name selected: {name}. Enter the name of your appointment. (E.g., Dental, Otolaryngology)"
        )
        return

    if key == "rsi_name":
        # Check for duplicate cadets in batch for new RSI reports
        if cadet_already_in_batch(context, name, "rsi_report"):
            await reply(update, f"{name} is already in this batch. Cannot report the same cadet twice.")
            return

        context.user_data["name"] = name
        context.user_data["symptoms"] = ""
        context.user_data["awaiting_rsi_symptoms"] = True
        await reply(update, f"Name selected: {name}. Describe your symptoms.")
        return

    if key == "update_name":
        context.user_data["name"] = name
        context.user_data["updating"] = True
        context.user_data["awaiting_diagnosis"] = True

        records = get_user_records(name)
        if not records:
            await reply(
                update,
                f"No existing report found for {name}. Please use /start_status to create a new report."
            )
            context.user_data.clear()
            return

        latest_record = records[-1]
        if has_nonempty_value(getattr(latest_record, "diagnosis", "")):
            await reply(
                update,
                f"{name} already has a diagnosis on record. Further updates are not allowed."
            )
            context.user_data.clear()
            return
        if pending_update_exists(context, getattr(latest_record, "id", None), {"update"}):
            await reply(
                update,
                f"{name} already has an update queued in this batch."
            )
            context.user_data.clear()
            return
        context.user_data["symptoms"] = getattr(latest_record, "symptoms", "")
        context.user_data["diagnosis"] = getattr(latest_record, "diagnosis", "")
        context.user_data["status"] = getattr(latest_record, "status", "")
        context.user_data["record_id"] = getattr(latest_record, "id", None)
        await reply(update, f"Updating report for {name}. What is your diagnosis?")
        return

    if key == "update_ma_name":
        context.user_data["name"] = name
        user_records = get_ma_records(name)
        if not user_records:
            await reply(update, f"No existing MA reports found for {name}.")
            context.user_data.clear()
            return

        latest_record = user_records[-1]
        # Extract from correct MedicalEvent fields
        context.user_data["appointment"] = getattr(latest_record, "appointment_type", "") or ""
        context.user_data["appointment_location"] = getattr(latest_record, "location", "") or ""

        # Parse event_datetime to get date and time
        event_dt = getattr(latest_record, "event_datetime", None)
        if event_dt:
            context.user_data["appointment_date"] = event_dt.strftime("%d%m%y")
            context.user_data["appointment_time"] = event_dt.strftime("%H%M")
        else:
            context.user_data["appointment_date"] = ""
            context.user_data["appointment_time"] = ""

        context.user_data["record_id"] = getattr(latest_record, "id", None)

        instructors = get_all_instructor_names()
        keyboard = [
            [InlineKeyboardButton(instructor, callback_data=f"instructor|{instructor}")]
            for instructor in instructors
        ]
        await reply(update, "Select who endorsed:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if key == "rsi_update_name":
        context.user_data["name"] = name
        records = get_user_rsi_records(name)
        if not records:
            await reply(update, f"No existing RSI report found for {name}.")
            context.user_data.clear()
            return

        latest_record = records[-1]
        if has_nonempty_value(getattr(latest_record, "diagnosis", "")):
            await reply(
                update,
                f"{name} already has a diagnosis on record. Further updates are not allowed."
            )
            context.user_data.clear()
            return
        if pending_update_exists(context, getattr(latest_record, "id", None), {"rsi_update"}):
            await reply(
                update,
                f"{name} already has an update queued in this batch."
            )
            context.user_data.clear()
            return
        context.user_data["record_id"] = getattr(latest_record, "id", None)
        context.user_data["symptoms"] = getattr(latest_record, "symptoms", "")
        context.user_data["awaiting_rsi_diagnosis"] = True
        await reply(update, f"Updating RSI report for {name}. What is your diagnosis?")
        return

async def manual_input_handler(update: Update, context: CallbackContext):
    if not update.message:
        return

    user_input = update.message.text.strip()
    if not user_input:
        return

    if context.user_data.get("mode") == "report":
        if context.user_data.get("awaiting_symptoms"):
            # Validate symptoms: not empty and reasonable length
            if len(user_input) < 3:
                await reply(update, "Symptoms must be at least 3 characters. Please try again.")
                return
            if len(user_input) > 200:
                await reply(update, "Symptoms too long (max 200 characters). Please be more concise.")
                return

            context.user_data['symptoms'] += user_input.upper()
            context.user_data['awaiting_symptoms'] = False
            context.user_data['awaiting_diagnosis'] = True
            await reply(
                update,
                f"Symptom recorded: {user_input.upper()}."
            )
            await show_preview_summary(update, context)
            return

    if context.user_data.get("mode") == "update":
        if context.user_data.get("awaiting_diagnosis"):
            context.user_data['diagnosis'] = user_input.upper()
            context.user_data['awaiting_diagnosis'] = False
            context.user_data['awaiting_mc_days'] = True
            await reply(
                update,
                f"Diagnosis updated to: '{user_input.upper()}'"
            )
            await show_mc_days_buttons(update, context)
            return

        if context.user_data.get("awaiting_custom_mc_days"):
            # Validate that input is a number
            try:
                mc_days = int(user_input)
                if mc_days <= 0:
                    await reply(update, "MC days must be a positive number. Please try again.")
                    return
                if mc_days > 365:
                    await reply(update, "MC days seems unreasonably long. Please enter a value less than 365.")
                    return

                if mc_days == 1:
                    context.user_data['status'] = "1 DAY MC"
                else:
                    context.user_data['status'] = f"{mc_days} DAYS MC"
                context.user_data['awaiting_custom_mc_days'] = False
                context.user_data['number_of_mc_days'] = mc_days
                await reply(
                    update,
                    f"Status updated to: '{context.user_data['status']}'"
                )
                await show_preview_summary(update, context)
            except ValueError:
                await reply(
                    update,
                    "Please enter a valid number for MC days."
                )
            return

    if context.user_data.get("mode") == "ma_report":
        if context.user_data.get("awaiting_appointment"):
            # Validate appointment: not empty and reasonable length
            if len(user_input) < 2:
                await reply(update, "Appointment type must be at least 2 characters. Please try again.")
                return
            if len(user_input) > 200:
                await reply(update, "Appointment type too long (max 200 characters). Please be more concise.")
                return

            context.user_data['appointment'] = user_input.upper()
            context.user_data['awaiting_appointment'] = False
            context.user_data['awaiting_location'] = True
            await reply(
                update,
                f"Step 1/4 complete. Appointment recorded: {user_input.upper()}.\n\n"
                "Step 2/4: Please enter the location of your appointment."
            )
            return

        if context.user_data.get("awaiting_location"):
            # Validate location: not empty and reasonable length
            if len(user_input) < 2:
                await reply(update, "Location must be at least 2 characters. Please try again.")
                return
            if len(user_input) > 200:
                await reply(update, "Location too long (max 200 characters). Please be more concise.")
                return

            context.user_data['appointment_location'] = user_input.upper()
            context.user_data['awaiting_location'] = False
            context.user_data['awaiting_date'] = True
            await reply(
                update,
                f"Step 2/4 complete. Location recorded: {user_input.upper()}.\n\n"
                "Step 3/4: Please enter your appointment date in DDMMYY or YYYY-MM-DD format."
            )
            return

        if context.user_data.get("awaiting_date"):
            try:
                normalized_date = to_ddmmyy(user_input)
                appointment_date = datetime.strptime(normalized_date, "%d%m%y").date()

                # Check if date is in the past
                if appointment_date < datetime.now().date():
                    await reply(update, "Appointment date cannot be in the past. Please enter a future date.")
                    return
            except ValueError:
                await reply(update, "Invalid date. Use DDMMYY or YYYY-MM-DD.")
                return

            context.user_data['appointment_date'] = normalized_date
            context.user_data['awaiting_date'] = False
            context.user_data['awaiting_time'] = True
            await reply(
                update,
                f"Step 3/4 complete. Appointment date recorded: {context.user_data['appointment_date']}.\n\n"
                "Step 4/4: Please enter your appointment time in HHMM or HH:MM (24H)."
            )
            return

        if context.user_data.get("awaiting_time"):
            try:
                normalized_time = to_hhmm(user_input)
            except ValueError:
                await reply(update, "Invalid time. Use HHMM or HH:MM (24-hour).")
                return

            context.user_data['appointment_time'] = normalized_time
            context.user_data['awaiting_time'] = False
            await reply(
                update,
                f"Step 4/4 complete. Appointment time recorded: {context.user_data['appointment_time']}."
            )
            await show_ma_preview_summary(update, context)
            return

    if context.user_data.get("mode") == "rsi_report":
        if context.user_data.get("awaiting_rsi_symptoms"):
            # Validate RSI symptoms: not empty and reasonable length
            if len(user_input) < 3:
                await reply(update, "Symptoms must be at least 3 characters. Please try again.")
                return
            if len(user_input) > 200:
                await reply(update, "Symptoms too long (max 200 characters). Please be more concise.")
                return

            context.user_data['symptoms'] += user_input.upper()
            context.user_data['awaiting_rsi_symptoms'] = False
            await show_rsi_preview_summary(update, context, include_status=False)
            return

    if context.user_data.get("mode") == "rsi_update":
        if context.user_data.get("awaiting_rsi_diagnosis"):
            # Validate RSI diagnosis: not empty and reasonable length
            if len(user_input) < 2:
                await reply(update, "Diagnosis must be at least 2 characters. Please try again.")
                return
            if len(user_input) > 200:
                await reply(update, "Diagnosis too long (max 200 characters). Please be more concise.")
                return

            context.user_data['diagnosis'] = user_input.upper()
            context.user_data['awaiting_rsi_diagnosis'] = False
            await show_rsi_days_buttons(update, context)
            return

        if context.user_data.get("awaiting_rsi_custom_days"):
            try:
                days = int(user_input)
                if days < 0:
                    await reply(update, "Number of days must be a positive number. Please try again.")
                    return
                if days > 365:
                    await reply(update, "Number of days seems unreasonably long. Please enter a value less than 365.")
                    return

                context.user_data['number_of_days'] = days
                context.user_data['awaiting_rsi_custom_days'] = False
                await show_rsi_status_type_buttons(update, context)
            except ValueError:
                await reply(update, "Please enter a valid number of days.")
            return

async def start_status_report(update: Update, context: CallbackContext):
    await prompt_name_selection(update, context, "report", "Step 1/3: Select your name:", "name")

# ------------ RSO Handlers and Functions ------------ #
async def start_update_status(update: Update, context: CallbackContext):
    """Start the update process - get user name to find their report"""
    await prompt_name_selection(
        update,
        context,
        "update",
        "Step 1/3: Select your name to update your status report:",
        "update_name"
    )


async def show_mc_days_buttons(update: Update, context: CallbackContext):
    """Show buttons for selecting MC days"""
    keyboard = [
        [InlineKeyboardButton("1 day", callback_data="mc_days|1")],
        [InlineKeyboardButton("2 days", callback_data="mc_days|2")],
        [InlineKeyboardButton("3 days", callback_data="mc_days|3")],
        [InlineKeyboardButton("4 days", callback_data="mc_days|4")],
        [InlineKeyboardButton("5 days", callback_data="mc_days|5")],
        [InlineKeyboardButton("Other", callback_data="mc_days|other")]
    ]
    await reply(
        update,
        "Step 3/3: How many days of MC have you gotten?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mc_days_button_handler(update: Update, context: CallbackContext):
    """Handle MC days selection"""
    query = update.callback_query
    await query.answer()

    _, days = query.data.split("|")

    if days == "other":
        context.user_data['awaiting_custom_mc_days'] = True
        context.user_data['number_of_mc_days'] = None
        await reply(
            update,
            "Enter the number of MC days:"
        )
    else:
        if days == "1":
            context.user_data['status'] = "1 DAY MC"
        else:
            context.user_data['status'] = f"{days} DAYS MC"
        context.user_data['number_of_mc_days'] = int(days)
        context.user_data['awaiting_mc_days'] = False
        await show_preview_summary(update, context)


async def show_preview_summary(update: Update, context: CallbackContext):
    name = context.user_data.get('name', 'N/A')
    symptoms = context.user_data.get('symptoms', '')
    diagnosis = context.user_data.get('diagnosis', '')
    status = context.user_data.get('status', '')
    if status != '':
        number_days = context.user_data.get('number_of_mc_days', 0)
        start_date = datetime.now().date().strftime("%d%m%y")
        end_date = start_date  # Initialize end_date same as start_date
        if number_days and number_days > 0:
            end_date = (datetime.now().date() + timedelta(days=number_days - 1)).strftime("%d%m%y")
        status += f" ({start_date}-{end_date})"
        context.user_data['start_date'] = start_date
        context.user_data['end_date'] = end_date

    summary = f"NAME: {name}\n"
    summary += f"SYMPTOMS: {symptoms}\n"
    summary += f"DIAGNOSIS: {diagnosis}\n"
    summary += f"STATUS: {status}\n"

    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="confirm"),
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    await reply(
        update,
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return


async def confirm_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not mark_action_once(context, "confirm_rso"):
        await reply(update, "ℹ️ This report was already confirmed.")
        return

    name = context.user_data.get('name', 'N/A')
    symptoms = context.user_data.get('symptoms', '')
    diagnosis = context.user_data.get('diagnosis', '')
    status = context.user_data.get('status', '')
    mode = context.user_data.get("mode")

    if status != '':
        start_date = context.user_data.get('start_date', '')
        end_date = context.user_data.get('end_date', '')
        status += f" ({start_date}-{end_date})"

    else:
        start_date = ''
        end_date = ''


    if mode == "update" and pending_update_exists(context, context.user_data.get("record_id"), {"update"}):
        await reply(update, "This update is already queued in the current batch.")
        reset_entry_state(context)
        return

    add_pending_report(
        context,
        {
            "mode": mode,
            "name": name,
            "symptoms": symptoms,
            "diagnosis": diagnosis,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "record_id": context.user_data.get("record_id"),
        },
    )

    keyboard = [
        [InlineKeyboardButton("➕ Report Another", callback_data=f"continue_reporting|{mode}")],
        [InlineKeyboardButton("✅ Done", callback_data="done_reporting")]
    ]
    await reply(
        update,
        "✅ Added to batch. Report another?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    reset_entry_state(context)


async def cancel(update: Update, context: CallbackContext):
    context.user_data.clear()
    await reply(update, "Cancelled.")

async def continue_reporting_handler(update: Update, context: CallbackContext):
    """Handle continuing to report another person"""
    query = update.callback_query
    await query.answer()

    _, mode = query.data.split("|", 1)
    reset_entry_state(context)

    if mode == "report":
        await start_status_report(update, context)
    elif mode == "update":
        await start_update_status(update, context)
    elif mode == "rsi_report":
        await start_rsi_report(update, context)
    elif mode == "rsi_update":
        await start_update_rsi(update, context)

async def done_reporting_handler(update: Update, context: CallbackContext):
    """Handle completion of all reporting"""
    query = update.callback_query
    await query.answer()
    reports = context.user_data.get("pending_reports", [])
    mode = context.user_data.get("mode")
    if not reports:
        context.user_data.clear()
        await reply(update, "All done! Use /start_status to report again.")
        return

    summary = format_pending_reports(reports, mode)
    context.user_data.clear()
    context.user_data["last_batch_summary"] = summary
    context.user_data["last_batch_reports"] = reports
    keyboard = [
        [InlineKeyboardButton("📤 Send to IC Group", callback_data="send_batch_ic")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_batch_send")],
    ]
    await reply(
        update,
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def send_batch_to_ic_handler(update: Update, context: CallbackContext):
    """Send the last completed batch summary to IC group chat."""
    query = update.callback_query
    await query.answer()

    summary = context.user_data.get("last_batch_summary")
    reports = context.user_data.get("last_batch_reports")
    if not summary or not reports:
        await reply(update, "No batch summary found to send.")
        return


    persist_pending_reports(reports)
    await send_to_ic_group(update, context, summary)
    context.user_data.clear()
    await reply(update, "✅ Sent to IC group.")


async def cancel_batch_send_handler(update: Update, context: CallbackContext):
    """Cancel sending the last completed batch summary."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await reply(update, "Cancelled. Batch not sent to IC group.")


# def report_rso_command(update: Update, context: CallbackContext):
#     start_status_report(update, context)


# def update_rso_command(update: Update, context: CallbackContext):
#     start_update_status(update, context)


# def start_command(update: Update, context: CallbackContext):
#     reply(
#         update,
#         "Welcome. Use /start_status to submit a RSO report or /update_status to update RSO report.\nUse /report_ma to submit an MA report or /update_ma to update MA endorsement.\nUse /report_rsi to submit an RSI report or /update_rsi to update RSI status."
#     )

# ------------ MA Handlers and Functions ------------ #

async def start_ma_report(update: Update, context: CallbackContext):
    await prompt_name_selection(update, context, "ma_report", "Step 1/4: Select your name for MA report:", "name")

async def show_ma_preview_summary(update: Update, context: CallbackContext):
    name = context.user_data.get('name', 'N/A')
    appointment = context.user_data.get('appointment', 'N/A')
    appointment_location = context.user_data.get('appointment_location', 'N/A')
    appointment_date = context.user_data.get('appointment_date', 'N/A')
    appointment_time = context.user_data.get('appointment_time', 'N/A')

    summary = f"{name}\n"
    summary += f"NAME: {appointment}\n"
    summary += f"LOCATION: {appointment_location}\n"
    summary += f"DATE: {appointment_date}\n"
    summary += f"TIME OF APPOINTMENT: {appointment_time}H\n"

    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="confirm_ma"),
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    await reply(
        update,
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return

async def confirm_ma_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not mark_action_once(context, "confirm_ma"):
        await reply(update, "ℹ️ This MA report was already confirmed.")
        return

    name = context.user_data.get('name', 'N/A')
    appointment = context.user_data.get('appointment', 'N/A')
    appointment_location = context.user_data.get('appointment_location', 'N/A')
    appointment_date = context.user_data.get('appointment_date', 'N/A')
    appointment_time = context.user_data.get('appointment_time', 'N/A')

    # Save new MA report to database
    create_ma_record(
        name=name,
        appointment=appointment,
        appointment_location=appointment_location,
        appointment_date=appointment_date,
        appointment_time=appointment_time
    )

    # Format and send to CBC
    summary = f"MA\n"
    summary += f"{name}\n"
    summary += f"NAME: {appointment}\n"
    summary += f"LOCATION: {appointment_location}\n"
    summary += f"DATE: {appointment_date}\n"
    summary += f"TIME OF APPOINTMENT: {appointment_time}H\n"

    await send_to_cadet_chat(update, context, summary)

    await reply(
        update,
        "MA Report saved. Thank you!"
    )
    context.user_data.clear()



async def update_endorsed(update: Update, context: CallbackContext):
    """Start the update endorsed process - select name first"""
    await prompt_name_selection(update, context, "update_ma", "Step 1/2: Select your name to update MA endorsement:", "update_ma_name")

async def instructor_selection_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    key, instructor = query.data.split("|")
    if key == "instructor":
        context.user_data['instructor'] = instructor
        await show_ma_update_summary(update, context)
        return

async def show_ma_update_summary(update: Update, context: CallbackContext):
    name = context.user_data.get('name', 'N/A')
    appointment = context.user_data.get('appointment', 'N/A')
    appointment_location = context.user_data.get('appointment_location', 'N/A')
    appointment_date = context.user_data.get('appointment_date', 'N/A')
    appointment_time = context.user_data.get('appointment_time', 'N/A')
    instructor = context.user_data.get('instructor', 'N/A')

    summary = f"{name}\n"
    summary += f"NAME: {appointment}\n"
    summary += f"LOCATION: {appointment_location}\n"
    summary += f"DATE: {appointment_date}\n"
    summary += f"TIME OF APPOINTMENT: {appointment_time}H\n"
    summary += f"ENDORSED BY: {instructor}\n"

    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="confirm_ma_update"),
            InlineKeyboardButton("Cancel", callback_data="cancel")
        ]
    ]
    await reply(
        update,
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return

async def confirm_ma_update_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not mark_action_once(context, "confirm_ma_update"):
        await reply(update, "ℹ️ This MA update was already confirmed.")
        return

    name = context.user_data.get('name', 'N/A')
    appointment = context.user_data.get('appointment', 'N/A')
    appointment_location = context.user_data.get('appointment_location', 'N/A')
    appointment_date = context.user_data.get('appointment_date', 'N/A')
    appointment_time = context.user_data.get('appointment_time', 'N/A')
    instructor = context.user_data.get('instructor', 'N/A')

    # Update MA record in database
    update_ma_record(
        record_id=context.user_data.get('record_id'),
        appointment=appointment,
        appointment_location=appointment_location,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        instructor=instructor
    )

    # Format and send to parade state IC group
    summary = f"MA\n"
    summary += f"{name}\n"
    summary += f"NAME: {appointment}\n"
    summary += f"LOCATION: {appointment_location}\n"
    summary += f"DATE: {appointment_date}\n"
    summary += f"TIME OF APPOINTMENT: {appointment_time}H\n"
    summary += f"ENDORSED BY: {instructor}\n"

    await send_to_ic_group(update, context, summary)

    await reply(
        update,
        "MA endorsement updated and sent. Thank you!"
    )
    context.user_data.clear()

# def report_ma_command(update: Update, context: CallbackContext):
#     start_ma_report(update, context)

# ------------ RSI Handlers and Functions ------------ #

async def start_rsi_report(update: Update, context: CallbackContext):
    await prompt_name_selection(update, context, "rsi_report", "Step 1/3: Select your name to report RSI:", "rsi_name")

async def start_update_rsi(update: Update, context: CallbackContext):
    await prompt_name_selection(update, context, "rsi_update", "Step 1/3: Select your name to update RSI status:", "rsi_update_name")

async def show_rsi_days_buttons(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("No Status Given", callback_data="rsi_days|0")],
        [InlineKeyboardButton("1 day", callback_data="rsi_days|1")],
        [InlineKeyboardButton("2 days", callback_data="rsi_days|2")],
        [InlineKeyboardButton("3 days", callback_data="rsi_days|3")],
        [InlineKeyboardButton("4 days", callback_data="rsi_days|4")],
        [InlineKeyboardButton("5 days", callback_data="rsi_days|5")],
        [InlineKeyboardButton("Other", callback_data="rsi_days|other")]
    ]
    await reply(
        update,
        "How many days of status?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def rsi_days_button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    _, days = query.data.split("|")
    if days == "other":
        context.user_data["awaiting_rsi_custom_days"] = True
        await reply(update, "Enter the number of days:")
        return

    days_int = int(days)
    context.user_data["number_of_days"] = days_int

    # If no status given, skip status type selection
    if days_int == 0:
        context.user_data["status_type"] = "N/A"
        context.user_data["status"] = "N/A"
        context.user_data["start_date"] = ""
        context.user_data["end_date"] = ""
        await show_rsi_preview_summary(update, context, include_status=True)
    else:
        await show_rsi_status_type_buttons(update, context)

async def show_rsi_status_type_buttons(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("MC", callback_data="rsi_type|MC")],
        [InlineKeyboardButton("LD", callback_data="rsi_type|LD")]
    ]
    await reply(
        update,
        "Select status type:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def rsi_status_type_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    _, status_type = query.data.split("|")
    days = context.user_data.get("number_of_days", 1)

    if status_type == 'LD':
        status_full = "LIGHT DUTY"
    else:
        status_full = status_type

    if days == 1:
        status = f"1 DAY {status_full}"
    elif days == 0:
        status = "N/A"
    else:
        status = f"{days} DAYS {status_full}"

    if status == "N/A":
        start_date = ""
        end_date = ""
    else:
        start_date = datetime.now().date().strftime("%d%m%y")
        end_date = (datetime.now().date() + timedelta(days=days - 1)).strftime("%d%m%y")

    context.user_data["status_type"] = status_type
    context.user_data["status"] = status
    context.user_data["start_date"] = start_date
    context.user_data["end_date"] = end_date

    await show_rsi_preview_summary(update, context,include_status=True)

async def show_rsi_preview_summary(update: Update, context: CallbackContext, include_status: bool):
    name = context.user_data.get("name", "N/A")
    symptoms = context.user_data.get("symptoms", '')
    diagnosis = context.user_data.get("diagnosis", "")

    status_line = ""
    if include_status:
        status = context.user_data.get("status", "")
        start_date = context.user_data.get("start_date", "")
        end_date = context.user_data.get("end_date", "")
        if status == "N/A":
            status_line = "N/A"
        else:
            status_line = f"{status} ({start_date}-{end_date})" if status else ""

    summary = f"NAME: {name}\n"
    summary += f"SYMPTOMS: {symptoms}\n"
    summary += f"DIAGNOSIS: {diagnosis}\n"
    summary += f"STATUS: {status_line}\n"

    confirm_cb = "confirm_rsi_report" if context.user_data.get("mode") == "rsi_report" else "confirm_rsi_update"
    keyboard = [[InlineKeyboardButton("Confirm", callback_data=confirm_cb),
                 InlineKeyboardButton("Cancel", callback_data="cancel")]]
    await reply(
        update,
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_rsi_report_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not mark_action_once(context, "confirm_rsi_report"):
        await reply(update, "ℹ️ This RSI report was already confirmed.")
        return

    name = context.user_data.get("name", "N/A")
    symptoms = context.user_data.get("symptoms", "")

    keyboard = [
        [InlineKeyboardButton("➕ Report Another", callback_data="continue_reporting|rsi_report")],
        [InlineKeyboardButton("✅ Done", callback_data="done_reporting")]
    ]
    add_pending_report(
        context,
        {
            "mode": "rsi_report",
            "name": name,
            "symptoms": symptoms,
            "diagnosis": context.user_data.get("diagnosis", ""),
            "status": "",
        },
    )
    await reply(
        update,
        "✅ Added to batch. Report another?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    reset_entry_state(context)

async def confirm_rsi_update_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not mark_action_once(context, "confirm_rsi_update"):
        await reply(update, "ℹ️ This RSI update was already confirmed.")
        return

    record_id = context.user_data.get("record_id")
    diagnosis = context.user_data.get("diagnosis", "")
    status_type = context.user_data.get("status_type", "MC")
    status = context.user_data.get("status", "")
    start_date = context.user_data.get("start_date", "")
    end_date = context.user_data.get("end_date", "")

    # Append dates to status for consistent formatting (like RSO)
    if status and start_date and end_date:
        status += f" ({start_date}-{end_date})"

    if pending_update_exists(context, record_id, {"rsi_update"}):
        await reply(update, "This update is already queued in the current batch.")
        reset_entry_state(context)
        return

    keyboard = [
        [InlineKeyboardButton("➕ Update Another", callback_data="continue_reporting|rsi_update")],
        [InlineKeyboardButton("✅ Done", callback_data="done_reporting")]
    ]
    add_pending_report(
        context,
        {
            "mode": "rsi_update",
            "record_id": record_id,
            "name": context.user_data.get("name", "N/A"),
            "symptoms": context.user_data.get("symptoms", ""),
            "diagnosis": diagnosis,
            "status_type": status_type,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    await reply(
        update,
        "✅ Added to batch. Update another?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    reset_entry_state(context)

# def report_rsi_command(update: Update, context: CallbackContext):
#     start_rsi_report(update, context)

# def update_rsi_command(update: Update, context: CallbackContext):
#     start_update_rsi(update, context)
