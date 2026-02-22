from collections import defaultdict
from typing import List, Dict


class ReportManager:

    # =========================
    # MOVEMENT FORMAT
    # =========================
    @staticmethod
    def build_movement_message(names, from_loc, to_loc, time_hhmm):
        lines = ["Dear Instructors,", ""]

        for i, name in enumerate(sorted(names), 1):
            lines.append(f"{i}. {name}")
            lines.append("")

        lines.append(
            f"MOVEMENT FROM {from_loc} TO {to_loc} @{time_hhmm}HRS"
        )

        return "\n".join(lines)

    # =========================
    # SFT FORMAT
    # =========================
    @staticmethod
    def build_sft_message(sir_name, date, records):
        earliest = min(r["start"] for r in records)
        latest = max(r["end"] for r in records)

        msg = (
            f"Good Evening Sir {sir_name}, below are the cadets "
            f"participating in SFT for {date} "
            f"from {earliest}H to {latest}H.\n\n"
        )

        grouped = defaultdict(list)
        for r in records:
            grouped[(r["activity"], r["location"])].append(r)

        counter = 1
        for (activity, location), entries in grouped.items():
            msg += f"{activity} @ {location}\n"

            for e in entries:
                line = f"{counter}. {e['name']} {e['start']}-{e['end']}"
                if e.get("remark"):
                    line += f" ({e['remark']})"
                msg += line + "\n"
                counter += 1

            msg += "\n"  

        return msg.rstrip()
