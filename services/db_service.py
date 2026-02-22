from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

def _display_instructor_name(instructor_name: str) -> str:
    parts = instructor_name.split(maxsplit=1)
    if len(parts) == 2:
        return parts[1]
    return instructor_name


# =========================
# DATA MODELS   
# =========================

@dataclass
class SFTSubmission:
    user_id: int
    user_name: str
    activity: str
    location: str
    start: str
    end: str
    date: str


@dataclass
class SFTWindow:
    date: str
    start: str
    end: str


# =========================
# DATABASE SERVICE
# =========================

class DatabaseService:
    @staticmethod
    def initialise():
        from db.init_db import init_db
        init_db()


# =========================
# SFT SERVICE
# =========================

class SFTService:
    _submissions: List[SFTSubmission] = []
    _window: Optional[SFTWindow] = None

    # ---------- WINDOW CONTROL ----------

    @classmethod
    def set_window(cls, date: str, start: str, end: str):
        cls._window = SFTWindow(date=date, start=start, end=end)

    @classmethod
    def get_window(cls) -> Optional[SFTWindow]:
        return cls._window

    @classmethod
    def clear_window(cls):
        cls._window = None

    # ---------- SUBMISSIONS ----------

    @classmethod
    def add_submission(
        cls,
        user_id: int,
        activity: str,
        location: str,
        start: str,
        end: str,
        user_name: str,
    ):
        if not cls._window:
            raise ValueError("SFT window not set")

        cls._submissions.append(
            SFTSubmission(
                user_id=user_id,
                user_name=user_name,
                activity=activity,
                location=location,
                start=start,
                end=end,
                date=cls._window.date,
            )
        )

    @classmethod
    def remove_submission(cls, user_id: int) -> bool:
        before = len(cls._submissions)
        cls._submissions = [
            s for s in cls._submissions if s.user_id != user_id
        ]
        return len(cls._submissions) < before

    @classmethod
    def clear_submissions(cls):
        cls._submissions = []

    @classmethod
    def get_submissions_for_date(cls, date: str) -> List[SFTSubmission]:
        return [s for s in cls._submissions if s.date == date]

    # ---------- SUMMARY GENERATION ----------

    @classmethod
    def generate_summary(cls, date: str, instructor_name: str, salutation: str) -> str:
        grouped = defaultdict(list)

        for s in cls._submissions:
            if s.date != date:
                continue
            key = f"{s.activity} @ {s.location}" if s.location else s.activity
            grouped[key].append(s)

        if not grouped:
            return f"❌ No SFT submissions for {date}."

        # 🚨 VALIDATION: each activity must have >= 2 pax
        invalid = [
            activity
            for activity, entries in grouped.items()
            if len(entries) < 2
        ]

        if invalid:
            lines = [
                "❌ SFT summary cannot be generated.",
                "",
                "The following activities have fewer than 2 participants:",
            ]
            for a in invalid:
                lines.append(f"- {a}")
            lines.append("")
            lines.append("Please resolve before generating summary.")
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


# =========================
# FUNCTIONAL EXPORT
# =========================

def get_sft_window():
    return SFTService.get_window()

def set_sft_window(date: str, start: str, end: str):
    SFTService.set_window(date=date, start=start, end=end)
