from datetime import date
from db.models import User, MedicalEvent, MedicalStatus

def generate_parade_state(db, target_date: date):
    # --- Strength ---
    total_strength = db.query(User).filter(
        User.role == "Cadet",
        User.is_active == True
    ).count()

    # --- Active statuses ---
    active_statuses = db.query(MedicalStatus).filter(
        MedicalStatus.start_date <= target_date,
        MedicalStatus.end_date >= target_date
    ).all()

    # --- Count by status type ---
    status_counts = {}
    status_text = {}

    for status in active_statuses:
        status_counts.setdefault(status.status_type, 0)
        status_counts[status.status_type] += 1

        status_text.setdefault(status.status_type, [])
        status_text[status.status_type].append(
            f"{status.user.full_name} ({status.start_date.strftime('%d%m%y')}-"
            f"{status.end_date.strftime('%d%m%y')})"
        )

    current_strength = total_strength - len(active_statuses)
    out_of_camp = status_counts.get("RSO", 0)

    return {
        "total_strength": total_strength,
        "current_strength": current_strength,
        "out_of_camp": out_of_camp,
        "status_counts": status_counts,
        "status_text": status_text,
    }
