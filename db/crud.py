from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy import text

from db.database import SessionLocal, session_scope
from db.models import AdminApproval, MedicalEvent, MedicalStatus, MovementLog, SFTSession, SFTSubmission, User
from utils.datetime_utils import SG_TZ, now_sg


CLEAR_DATABASE_ACTION = "CLEAR_DATABASE"


def register_clear_database_approval(admin_telegram_id: int, window_minutes: int = 10) -> int:
    cutoff = now_sg() - timedelta(minutes=window_minutes)
    with session_scope() as session:
        session.query(AdminApproval).filter(AdminApproval.action == CLEAR_DATABASE_ACTION, AdminApproval.created_at < cutoff).delete(synchronize_session=False)
        existing = session.query(AdminApproval).filter(
            AdminApproval.action == CLEAR_DATABASE_ACTION,
            AdminApproval.admin_telegram_id == admin_telegram_id,
        ).first()
        if existing:
            existing.created_at = now_sg()
        else:
            session.add(AdminApproval(action=CLEAR_DATABASE_ACTION, admin_telegram_id=admin_telegram_id))
        session.flush()
        count = session.query(func.count(func.distinct(AdminApproval.admin_telegram_id))).filter(
            AdminApproval.action == CLEAR_DATABASE_ACTION,
            AdminApproval.created_at >= cutoff,
        ).scalar()
        return int(count or 0)


def clear_database_approvals() -> None:
    with session_scope() as session:
        session.query(AdminApproval).filter(AdminApproval.action == CLEAR_DATABASE_ACTION).delete(synchronize_session=False)


def get_user_by_telegram_id(telegram_id: int):
    with SessionLocal() as session:
        return session.query(User).filter(User.telegram_id == telegram_id).first()


def get_admin_telegram_ids() -> list[int]:
    with SessionLocal() as session:
        rows = session.query(User.telegram_id).filter(
            User.is_admin.is_(True),
            User.is_active.is_(True),
            User.telegram_id.isnot(None),
        ).all()
    return [row[0] for row in rows]


def _normalize_username(value: str | None):
    if value is None:
        return None
    name = value.strip()
    if not name:
        return None
    if name.startswith("@"):
        name = name[1:]
    return name or None


def create_user(
    full_name: str,
    rank: str,
    role: str,
    telegram_id: int | None = None,
    telegram_username: str | None = None,
    is_admin: bool = False,
    is_active: bool = True,
):
    telegram_username = _normalize_username(telegram_username)
    if telegram_id is None and not telegram_username:
        raise ValueError("telegram_id or telegram_username is required")

    with session_scope() as session:
        if telegram_id is not None and session.query(User).filter(User.telegram_id == telegram_id).first():
            raise ValueError("telegram_id already exists")
        if telegram_username and session.query(User).filter(User.telegram_username == telegram_username).first():
            raise ValueError("telegram_username already exists")

        user = User(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            full_name=full_name,
            rank=rank,
            role=role,
            is_admin=is_admin,
            is_active=is_active,
        )
        session.add(user)
        session.flush()
        return user


def clear_user_data() -> dict[str, int]:
    with session_scope() as session:
        # Remove SFT submissions first because they reference users.
        sft_submissions_deleted = session.query(SFTSubmission).delete(synchronize_session=False)
        statuses_deleted = session.query(MedicalStatus).delete(synchronize_session=False)
        events_deleted = session.query(MedicalEvent).delete(synchronize_session=False)
        users_deleted = session.query(User).delete(synchronize_session=False)
    return {
        "sft_submissions": sft_submissions_deleted,
        "medical_statuses": statuses_deleted,
        "medical_events": events_deleted,
        "users": users_deleted,
    }


def clear_all_data() -> dict[str, int]:
    clear_targets = [
        (AdminApproval.__tablename__, "admin_approvals", AdminApproval),
        (SFTSubmission.__tablename__, "sft_submissions", SFTSubmission),
        (SFTSession.__tablename__, "sft_sessions", SFTSession),
        (MovementLog.__tablename__, "movement_logs", MovementLog),
        (MedicalStatus.__tablename__, "medical_statuses", MedicalStatus),
        (MedicalEvent.__tablename__, "medical_events", MedicalEvent),
        (User.__tablename__, "users", User),
    ]

    with session_scope() as session:
        counts = {
            key: int(session.query(func.count()).select_from(model).scalar() or 0)
            for _, key, model in clear_targets
        }

        table_sql = ", ".join(table_name for table_name, _, _ in clear_targets)
        session.execute(text(f"TRUNCATE TABLE {table_sql} RESTART IDENTITY CASCADE"))

    return counts


def list_users(limit: int = 200) -> list[User]:
    with SessionLocal() as session:
        return session.query(User).order_by(User.rank, User.full_name).limit(limit).all()


def get_all_cadet_names():
    with SessionLocal() as session:
        records = session.query(User).filter(func.lower(User.role) == "cadet", User.is_active.is_(True)).all()
    return [record.rank + " " + record.full_name for record in records]


def get_all_instructor_names():
    with SessionLocal() as session:
        records = session.query(User).filter(func.lower(User.role) == "instructor").all()
    return [record.rank + " " + record.full_name for record in records]


def create_medical_event(
    user_id: int,
    event_type: str,
    symptoms: str,
    diagnosis: str,
    event_datetime: datetime | None = None,
):
    if event_datetime is None:
        event_datetime = now_sg().replace(microsecond=0)

    with session_scope() as session:
        event = MedicalEvent(
            user_id=user_id,
            event_type=event_type,
            symptoms=symptoms,
            diagnosis=diagnosis,
            event_datetime=event_datetime,
        )
        session.add(event)
        session.flush()
        return event


def create_medical_status(
    user_id: int,
    status_type: str,
    description: str,
    start_date,
    end_date,
    source_event_id: int | None = None,
):
    with session_scope() as session:
        status = MedicalStatus(
            user_id=user_id,
            status_type=status_type,
            description=description,
            start_date=start_date,
            end_date=end_date,
            source_event_id=source_event_id,
        )
        session.add(status)
        session.flush()
        return status


def get_active_statuses(today):
    if isinstance(today, str):
        today = datetime.strptime(today, "%Y-%m-%d").date()

    with SessionLocal() as session:
        return (
            session.query(MedicalStatus, User, MedicalEvent)
            .join(User, MedicalStatus.user_id == User.id)
            .join(MedicalEvent, MedicalStatus.source_event_id == MedicalEvent.id)
            .filter(MedicalStatus.start_date <= today, MedicalStatus.end_date >= today)
            .all()
        )


def delete_expired_statuses_and_events(target_date: date) -> tuple[int, int]:
    with session_scope() as session:
        target_start = datetime.combine(target_date, time.min, tzinfo=SG_TZ)
        statuses_deleted = session.query(MedicalStatus).filter(MedicalStatus.end_date < target_date).delete(synchronize_session=False)
        events_deleted = session.query(MedicalEvent).filter(MedicalEvent.event_datetime < target_start).delete(synchronize_session=False)
    return statuses_deleted, events_deleted


def get_user_records(name: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        return []
    rank, full_name = parts
    with SessionLocal() as session:
        return (
            session.query(MedicalEvent)
            .join(User)
            .filter(User.rank == rank, User.full_name == full_name, MedicalEvent.event_type == "RSO")
            .all()
        )


def _has_diagnosis(value: str | None) -> bool:
    return bool(value and value.strip())


def update_user_record(record_id: int, symptoms: str, diagnosis: str, status: str, start_date: str, end_date: str):
    with session_scope() as session:
        record = session.query(MedicalEvent).filter(MedicalEvent.id == record_id).first()
        if not record:
            return None
        if _has_diagnosis(record.diagnosis):
            return record

        record.symptoms = symptoms
        record.diagnosis = diagnosis
        session.add(
            MedicalStatus(
                user_id=record.user_id,
                status_type="MC",
                description=status,
                start_date=datetime.strptime(start_date, "%d%m%y").date(),
                end_date=datetime.strptime(end_date, "%d%m%y").date(),
                source_event_id=record.id,
            )
        )
        session.flush()
        return record


def create_user_record(name: str, symptoms: str, diagnosis: str | None = None):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid name format")
    rank, full_name = parts

    with session_scope() as session:
        user = session.query(User).filter(User.rank == rank, User.full_name == full_name).first()
        if not user:
            raise ValueError("User not found")

        event = MedicalEvent(
            user_id=user.id,
            event_type="RSO",
            symptoms=symptoms,
            diagnosis=diagnosis,
            event_datetime=now_sg().replace(microsecond=0),
        )
        session.add(event)
        session.flush()
        return event


def get_ma_records(name: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        return []
    rank, full_name = parts
    with SessionLocal() as session:
        return (
            session.query(MedicalEvent)
            .join(User)
            .filter(User.rank == rank, User.full_name == full_name, MedicalEvent.event_type == "MA")
            .all()
        )


def create_ma_record(name: str, appointment: str, appointment_location: str, appointment_date: str, appointment_time: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid name format")
    rank, full_name = parts

    with session_scope() as session:
        user = session.query(User).filter(User.rank == rank, User.full_name == full_name).first()
        if not user:
            raise ValueError("User not found")

        appointment_dt = datetime.combine(
            datetime.strptime(appointment_date, "%d%m%y").date(),
            datetime.strptime(appointment_time, "%H%M").time(),
            tzinfo=SG_TZ,
        )
        event = MedicalEvent(
            user_id=user.id,
            event_type="MA",
            appointment_type=appointment,
            location=appointment_location,
            event_datetime=appointment_dt,
        )
        session.add(event)
        session.flush()
        return event


def update_ma_record(record_id: int, appointment: str, appointment_location: str, appointment_date: str, appointment_time: str, instructor: str | None = None):
    with session_scope() as session:
        record = session.query(MedicalEvent).filter(MedicalEvent.id == record_id).first()
        if not record:
            return None

        record.appointment_type = appointment
        record.location = appointment_location
        record.event_datetime = datetime.combine(
            datetime.strptime(appointment_date, "%d%m%y").date(),
            datetime.strptime(appointment_time, "%H%M").time(),
            tzinfo=SG_TZ,
        )
        if instructor:
            record.endorsed_by = instructor
        session.flush()
        return record


def get_user_rsi_records(name: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        return []
    rank, full_name = parts
    with SessionLocal() as session:
        return (
            session.query(MedicalEvent)
            .join(User)
            .filter(User.rank == rank, User.full_name == full_name, MedicalEvent.event_type == "RSI")
            .all()
        )


def create_rsi_record(name: str, symptoms: str, diagnosis: str | None = None):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid name format")
    rank, full_name = parts

    with session_scope() as session:
        user = session.query(User).filter(User.rank == rank, User.full_name == full_name).first()
        if not user:
            raise ValueError("User not found")

        event = MedicalEvent(
            user_id=user.id,
            event_type="RSI",
            symptoms=symptoms,
            diagnosis=diagnosis or "",
            event_datetime=now_sg().replace(microsecond=0),
        )
        session.add(event)
        session.flush()
        return event


def update_rsi_record(record_id: int, diagnosis: str, status_type: str, status: str, start_date: str, end_date: str):
    with session_scope() as session:
        record = session.query(MedicalEvent).filter(MedicalEvent.id == record_id).first()
        if not record:
            return None
        if _has_diagnosis(record.diagnosis):
            return record

        record.diagnosis = diagnosis
        if status != "N/A":
            session.add(
                MedicalStatus(
                    user_id=record.user_id,
                    status_type=status_type,
                    description=status,
                    start_date=datetime.strptime(start_date, "%d%m%y").date(),
                    end_date=datetime.strptime(end_date, "%d%m%y").date(),
                    source_event_id=record.id,
                )
            )
        session.flush()
        return record


def get_medical_events():
    with SessionLocal() as session:
        return session.query(MedicalEvent, User).join(User, MedicalEvent.user_id == User.id).all()


def get_all_cadets():
    with SessionLocal() as session:
        return session.query(User).filter(func.lower(User.role) == "cadet").all()


def get_all_instructors():
    with SessionLocal() as session:
        return session.query(User).filter(func.lower(User.role) == "instructor").all()


# ---------- SFT (Persistent) ----------

def get_active_sft_session() -> SFTSession | None:
    with SessionLocal() as session:
        return session.query(SFTSession).filter(SFTSession.is_active.is_(True)).order_by(SFTSession.id.desc()).first()


def set_active_sft_session(date_str: str, start: str, end: str) -> SFTSession:
    with session_scope() as session:
        session.query(SFTSession).filter(SFTSession.is_active.is_(True)).update({SFTSession.is_active: False})
        active = SFTSession(date=date_str, start=start, end=end, is_active=True)
        session.add(active)
        session.flush()
        return active


def clear_active_sft_session() -> None:
    with session_scope() as session:
        session.query(SFTSession).filter(SFTSession.is_active.is_(True)).update({SFTSession.is_active: False})


def add_sft_submission(user_id: int, user_name: str, activity: str, location: str, start: str, end: str) -> SFTSubmission:
    with session_scope() as session:
        active = session.query(SFTSession).filter(SFTSession.is_active.is_(True)).order_by(SFTSession.id.desc()).first()
        if not active:
            raise ValueError("SFT window not set")

        existing = session.query(SFTSubmission).filter(
            SFTSubmission.session_id == active.id,
            SFTSubmission.user_id == user_id,
        ).all()
        for item in existing:
            session.delete(item)

        submission = SFTSubmission(
            session_id=active.id,
            user_id=user_id,
            user_name=user_name,
            activity=activity,
            location=location,
            start=start,
            end=end,
        )
        session.add(submission)
        session.flush()
        return submission


def remove_sft_submission(user_id: int) -> bool:
    with session_scope() as session:
        active = session.query(SFTSession).filter(SFTSession.is_active.is_(True)).order_by(SFTSession.id.desc()).first()
        if not active:
            return False
        deleted = session.query(SFTSubmission).filter(
            SFTSubmission.session_id == active.id,
            SFTSubmission.user_id == user_id,
        ).delete(synchronize_session=False)
        return deleted > 0


def clear_sft_submissions() -> None:
    with session_scope() as session:
        active = session.query(SFTSession).filter(SFTSession.is_active.is_(True)).order_by(SFTSession.id.desc()).first()
        if active:
            session.query(SFTSubmission).filter(SFTSubmission.session_id == active.id).delete(synchronize_session=False)


def get_sft_submissions_for_date(date_str: str):
    with SessionLocal() as session:
        return (
            session.query(SFTSubmission)
            .join(SFTSession, SFTSubmission.session_id == SFTSession.id)
            .filter(SFTSession.date == date_str)
            .order_by(SFTSubmission.id.asc())
            .all()
        )
