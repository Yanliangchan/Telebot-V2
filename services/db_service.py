from collections import defaultdict
from dataclasses import dataclass

from db.crud import (
    add_sft_submission,
    clear_active_sft_session,
    clear_sft_submissions,
    get_active_sft_session,
    get_sft_submissions_for_date,
    remove_sft_submission,
    set_active_sft_session,
)


def _display_instructor_name(instructor_name: str) -> str:
    parts = instructor_name.split(maxsplit=1)
    return parts[1] if len(parts) == 2 else instructor_name


@dataclass
class SFTWindow:
    date: str
    start: str
    end: str


class DatabaseService:
    @staticmethod
    def initialise():
        from db.init_db import init_db

        init_db()


class SFTService:
    @classmethod
    def set_window(cls, date: str, start: str, end: str):
        set_active_sft_session(date, start, end)

    @classmethod
    def get_window(cls):
        session = get_active_sft_session()
        if not session:
            return None
        return SFTWindow(date=session.date, start=session.start, end=session.end)

    @classmethod
    def clear_window(cls):
        clear_active_sft_session()

    @classmethod
    def add_submission(cls, user_id: int, activity: str, location: str, start: str, end: str, user_name: str):
        add_sft_submission(user_id=user_id, user_name=user_name, activity=activity, location=location, start=start, end=end)

    @classmethod
    def remove_submission(cls, user_id: int) -> bool:
        return remove_sft_submission(user_id)

    @classmethod
    def clear_submissions(cls):
        clear_sft_submissions()

    @classmethod
    def get_submissions_for_date(cls, date: str):
        return get_sft_submissions_for_date(date)

    @classmethod
    def generate_summary(cls, date: str, instructor_name: str, salutation: str) -> str:
        grouped = defaultdict(list)
        submissions = cls.get_submissions_for_date(date)

        for s in submissions:
            key = f"{s.activity} @ {s.location}" if s.location else s.activity
            grouped[key].append(s)

        if not grouped:
            return f"❌ No SFT submissions for {date}."

        invalid = [activity for activity, entries in grouped.items() if len(entries) < 2]
        if invalid:
            lines = [
                "❌ SFT summary cannot be generated.",
                "",
                "The following activities have fewer than 2 participants:",
            ]
            lines.extend(f"- {activity}" for activity in invalid)
            lines.extend(["", "Please resolve before generating summary."])
            return "\n".join(lines)

        all_entries = [entry for entries in grouped.values() for entry in entries]
        earliest = min(entry.start for entry in all_entries)
        latest = max(entry.end for entry in all_entries)
        display_name = _display_instructor_name(instructor_name)

        lines = [
            (
                f"Good Afternoon {salutation} {display_name}, below are the cadets "
                f"participating in SFT for {date} from {earliest}H to {latest}H."
            ),
            "",
            "Submission of names",
        ]

        counter = 1
        for activity, entries in grouped.items():
            for entry in entries:
                lines.append(f"{counter}. {entry.user_name} {entry.start}-{entry.end}")
                counter += 1
            lines.append(activity)
            lines.append("")

        return "\n".join(lines).rstrip()


def get_sft_window():
    return SFTService.get_window()


def set_sft_window(date: str, start: str, end: str):
    SFTService.set_window(date=date, start=start, end=end)
