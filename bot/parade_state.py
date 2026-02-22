from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from db import crud
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.helpers import parade_state_cancel_button

def categorise_medical_events(events):
	"""Categorise medical events as MA, RSO or RSI"""
	ma_events = []
	rso_events = []
	rsi_events = []

	for event in events:
		if event[0].event_type == "MA":
			ma_events.append(event)
		elif event[0].event_type == "RSO":
			rso_events.append(event)
		elif event[0].event_type == "RSI":
			rsi_events.append(event)
		else:
			print("Unsupported event_type. Only RSO, RSI or MA.")

	categorised_medical_events = {"ma": ma_events, "rso": rso_events, "rsi": rsi_events}
	return categorised_medical_events

def categorise_medical_statuses(statuses):
	"""Categorise medical statuses as MC, LD, EUL or RMJ"""
	mc_statuses = []
	ld_statuses = []
	eul_statuses = []
	rmj_statuses = []

	for status in statuses:
		if status[0].status_type == "MC":
			mc_statuses.append(status)
		elif status[0].status_type == "LD":
			ld_statuses.append(status)
		elif status[0].status_type == "EUL":
			eul_statuses.append(status)
		elif status[0].status_type == "RMJ":
			rmj_statuses.append(status)
		else:
			print("Unsupported event_type. Only MC, LD, EUL or RMJ.")

	categorised_medical_statuses = {"mc": mc_statuses, "ld": ld_statuses, "eul": eul_statuses, "rmj": rmj_statuses}
	return categorised_medical_statuses

def format_ma(events):
	"""Format MA events for parade state"""
	final_text = ""
	for i, event in enumerate(events):
		medical_event = event[0]
		user = event[1]

		if medical_event.endorsed_by is None:
			endorsed_by = ""
		else:
			endorsed_by = medical_event.endorsed_by

		final_text += f"""{i+1}. {user.rank} {user.full_name}
a. NAME: {medical_event.appointment_type}
LOCATION: {medical_event.location}
DATE: {medical_event.event_datetime.strftime("%d%m%y")}
TIME OF APPOINTMENT: {medical_event.event_datetime.strftime("%H%M")}
ENDORSED BY: {endorsed_by}

"""
	return final_text
		
def format_rso_rsi(events):
	"""Format RSO and RSI events for parade state"""
	final_text = ""
	for i, event in enumerate(events):
		medical_event = event[0]
		user = event[1]

		final_text += f"""{i+1}. {user.rank} {user.full_name}
SYMPTOMS: {medical_event.symptoms}
DIAGNOSIS: 
STATUS: 

"""
	return final_text

def format_status(statuses):
	"""Format statuses for parade state"""
	final_text = ""
	for i, status in enumerate(statuses):
		medical_status = status[0]
		user = status[1]
		medical_event = status[2]

		status_start = medical_status.start_date
		status_end = medical_status.end_date
		status_duration = status_end - status_start + timedelta(days=1)

		status_start_date = status_start.strftime("%d%m%y")
		status_end_date = status_end.strftime("%d%m%y")
		status_duration_days = status_duration.days

		status_type = medical_status.status_type
		if status_type == "LD":
			status_type = "LIGHT DUTY"
		elif status_type == "EUL":
			status_type = "EXCUSED UPPER LIMB"
		elif status_type == "RMJ":
			status_type = "EXCUSED RUNNING, MARCHING, JUMPING"

		final_text += f"""{i+1}. {user.rank} {user.full_name}
SYMPTOMS: {medical_event.symptoms}
DIAGNOSIS: {medical_event.diagnosis}
STATUS: {status_duration_days} DAY(S) {status_type} ({status_start_date}-{status_end_date})

"""
	return final_text

def count_temp_statuses(temp_statuses):
	count = 0
	for key, value in temp_statuses.items():
		count += len(value)
	return count

async def generate_parade_state(update, context):
	"""Generates the current parade state"""

	tz_singapore = ZoneInfo("Asia/Singapore")

	current_datetime = datetime.now(tz_singapore)
	current_time = current_datetime.time()
	current_date = current_datetime.date()

	all_medical_events = crud.get_medical_events()
	all_medical_statuses = crud.get_active_statuses(current_date.strftime('%Y-%m-%d'))
	all_cadets = crud.get_all_cadets()
	active_medical_events = [item for item in all_medical_events if item[0].diagnosis == "" or item[0].diagnosis == None]
	categorised_medical_events = categorise_medical_events(active_medical_events)
	categorised_medical_statuses = categorise_medical_statuses(all_medical_statuses)

	ma_events = categorised_medical_events["ma"]
	rso_events = categorised_medical_events["rso"]
	rsi_events = categorised_medical_events["rsi"]
	mc_statuses = categorised_medical_statuses["mc"]
	temp_statuses = {key: value for key, value in categorised_medical_statuses.items() if key != "mc"}

	ma_count = len(ma_events)
	rso_count = len(rso_events)
	rsi_count = len(rsi_events)
	mc_count = len(mc_statuses)
	temp_status_count = count_temp_statuses(temp_statuses)
	
	if ma_count > 0:
		ma_text = format_ma(ma_events)
	else:
		ma_text = ""

	if rso_count > 0:
		rso_text = format_rso_rsi(rso_events)
	else:
		rso_text = ""
	
	if rsi_count > 0:
		rsi_text = format_rso_rsi(rsi_events)
	else:
		rsi_text = ""

	if mc_count > 0:
		mc_text = format_status(mc_statuses)
	else:
		mc_text = ""

	if temp_status_count > 0:  # temp status are statuses that are not MC
		temp_statuses_list = [item for sublist in temp_statuses.values() for item in sublist]
		temp_status_text = format_status(temp_statuses_list)
	else:
		temp_status_text = ""

	others_text = perm_status_text = ""
	others_count = perm_status_count = 0
	
	total_strength = len(all_cadets)
	out_of_camp = update.message.text.strip()
	if not out_of_camp.isdigit():
		await update.message.reply_text("❌ Only digits are allowed.\n\nPlease input the number of out-of-camp personnel:", reply_markup=parade_state_cancel_button())
		return
	out_of_camp = int(out_of_camp)
	if out_of_camp > total_strength:
		await update.message.reply_text("❌ Number of personnel cannot be greater than total strength.\n\nPlease input the number of out-of-camp personnel:", reply_markup=parade_state_cancel_button())
		return
	current_strength = total_strength - out_of_camp
	
	ma_section = "\n" + ma_text.rstrip() if ma_text else ""
	rsi_section = "\n" + rsi_text.rstrip() if rsi_text else ""
	rso_section = "\n" + rso_text.rstrip() if rso_text else ""
	mc_section = "\n" + mc_text.rstrip() if mc_text else ""
	others_section = "\n" + others_text.rstrip() if others_text else ""
	statuses_section = "\n" + temp_status_text.rstrip() if temp_status_text else ""
	perm_status_section = "\n" + perm_status_text.rstrip() if perm_status_text else ""

	parade_state_text = f"""
	DIS WING 14/26 PRE-MDST PARADE STATE {current_date.strftime('%d%m%y')}, {current_time.strftime('%H%M')}H
	-------------------------------------------------------- 

	TOTAL STRENGTH: {total_strength}

	CURRENT STRENGTH: {current_strength}
	OUT OF CAMP: {out_of_camp}

	-------------------------------------------------------- 

	MA: {ma_count:02d}{ma_section}

	-------------------------------------------------------- 

	RSI : {rsi_count:02d}{rsi_section}

	RSO : {rso_count:02d}{rso_section}

	-------------------------------------------------------- 

	MC: {mc_count:02d}{mc_section}

	-------------------------------------------------------- 

	OTHERS: {others_count:02d}{others_section}

	--------------------------------------------------------

	STATUSES: {temp_status_count:02d}{statuses_section}

	PERMANENT STATUS: {perm_status_count:02d}{perm_status_section}
	"""
	if len(parade_state_text) > 4096:
		parade_state_text = parade_state_text[:4000] + "\n\n Output truncated: parade_state_text too long."

	context.user_data["generated_text"] = parade_state_text
	context.user_data["mode"] = "PARADE_CONFIRM"

	keyboard = [
		[
			InlineKeyboardButton("📤 Send", callback_data="parade|send"),
			InlineKeyboardButton("❌ Cancel", callback_data="parade|cancel")
		]
	]

	reply_markup = InlineKeyboardMarkup(keyboard)

	await context.bot.send_message(
		chat_id=update.effective_chat.id, 
		message_thread_id=update.effective_message.message_thread_id,
    	text=f"{parade_state_text}",
		reply_markup=reply_markup
	)
