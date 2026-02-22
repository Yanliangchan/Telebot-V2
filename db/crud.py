from datetime import date, datetime, time
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.database import SessionLocal
from db.models import MedicalEvent, MedicalStatus, User
from utils.datetime_utils import now_sg, SG_TZ

db = SessionLocal()

# ---------- Users ----------

db = SessionLocal()

def get_user_by_telegram_id(telegram_id: int):
    session = SessionLocal()
    try:
        return session.query(User).filter(User.telegram_id == telegram_id).first()
    finally:
        session.close()

def get_admin_telegram_ids() -> list[int]:
    session = SessionLocal()
    try:
        rows = session.query(User.telegram_id).filter(
            User.is_admin.is_(True),
            User.is_active.is_(True),
            User.telegram_id.isnot(None),
        ).all()
        return [row[0] for row in rows]
    finally:
        session.close()


def get_admin_telegram_ids() -> list[int]:
    session = SessionLocal()
    try:
        rows = session.query(User.telegram_id).filter(
            User.is_admin.is_(True),
            User.is_active.is_(True),
            User.telegram_id.isnot(None),
        ).all()
        return [row[0] for row in rows]
    finally:
        session.close()

def is_admin_user(user_id: int | None) -> bool:
    if user_id is None:
        return False

    if user_id in ADMIN_IDS:
        return True

    user = get_user_by_telegram_id(user_id)
    return bool(user and user.is_admin and user.is_active)


def get_all_admin_user_ids() -> list[int]:
    return sorted(set(ADMIN_IDS) | set(get_admin_telegram_ids()))



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

    if telegram_id is not None:
        existing = db.query(User).filter(User.telegram_id == telegram_id).first()
        if existing:
            raise ValueError("telegram_id already exists")
    if telegram_username:
        existing = db.query(User).filter(User.telegram_username == telegram_username).first()
        if existing:
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
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def clear_user_data() -> dict[str, int]:
    session = SessionLocal()
    try:
        statuses_deleted = session.query(MedicalStatus).delete(synchronize_session=False)
        events_deleted = session.query(MedicalEvent).delete(synchronize_session=False)
        users_deleted = session.query(User).delete(synchronize_session=False)
        session.commit()
        return {
            "medical_statuses": statuses_deleted,
            "medical_events": events_deleted,
            "users": users_deleted,
        }
    except:
        session.rollback()
        raise
    finally:
        session.close()

def list_users(limit: int = 200) -> list[User]:
    session = SessionLocal()
    try:
        return (
            session.query(User)
            .order_by(User.rank, User.full_name)
            .limit(limit)
            .all()
        )
    finally:
        session.close()

def get_all_cadet_names():
    session = SessionLocal()
    try:
        records = session.query(User).filter(
            func.lower(User.role) == "cadet",
            User.is_active.is_(True),
        ).all()
        return [record.rank + " " + record.full_name for record in records]
    finally:
        session.close()

def get_all_instructor_names():
    session = SessionLocal()
    try:
        records = session.query(User).filter(
            func.lower(User.role) == "instructor"
        ).all()
        return [record.rank + " " + record.full_name for record in records]
    finally:
        session.close()

# ---------- Medical ----------

def create_medical_event(
    user_id: int,
    event_type: str,
    symptoms: str,
    diagnosis: str,
    event_datetime: datetime | None = None,
):
    if event_datetime is None:
        event_datetime = now_sg().replace(microsecond=0)
    event = MedicalEvent(
        user_id=user_id,
        event_type=event_type,
        symptoms=symptoms,
        diagnosis=diagnosis,
        event_datetime=event_datetime,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def create_medical_status(
    user_id: int,
    status_type: str,
    description: str,
    start_date,
    end_date,
    source_event_id: int | None = None,
):
    status = MedicalStatus(
        user_id=user_id,
        status_type=status_type,
        description=description,
        start_date=start_date,
        end_date=end_date,
        source_event_id=source_event_id,
    )
    db.add(status)
    db.commit()
    db.refresh(status)
    return status

def get_active_statuses(today):
    return db.query(
        MedicalStatus,
        User,
        MedicalEvent,
        ).join(
            User, MedicalStatus.user_id == User.id
		).join(
			MedicalEvent, MedicalStatus.source_event_id == MedicalEvent.id
		).filter(
        MedicalStatus.start_date <= today,
        MedicalStatus.end_date >= today
    ).all()

def delete_expired_statuses_and_events(target_date: date) -> tuple[int, int]:
    """Delete medical statuses/events before target_date. Returns (statuses, events)."""
    session = SessionLocal()
    try:
        target_start = datetime.combine(target_date, time.min, tzinfo=SG_TZ)
        statuses_deleted = session.query(MedicalStatus).filter(
            MedicalStatus.end_date < target_date
        ).delete(synchronize_session=False)
        events_deleted = session.query(MedicalEvent).filter(
            MedicalEvent.event_datetime < target_start
        ).delete(synchronize_session=False)
        session.commit()
        return statuses_deleted, events_deleted
    except:
        session.rollback()
        raise
    finally:
        session.close()

# ---------- Medical Events ----------

# RSO Records

def get_user_records(name: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        return []
    rank, full_name = parts
    return db.query(MedicalEvent).join(User).filter(
        User.rank == rank,
        User.full_name == full_name,
        MedicalEvent.event_type == "RSO"
    ).all()


def _has_diagnosis(value: str | None) -> bool:
    return bool(value and value.strip())

def update_user_record(record_id: int, symptoms: str, diagnosis: str,status: str, start_date: str, end_date: str):
    record = db.query(MedicalEvent).filter(MedicalEvent.id == record_id).first()
    if record:
        if _has_diagnosis(record.diagnosis):
            return record
        record.symptoms = symptoms
        record.diagnosis = diagnosis
        #Add Status start_date and end_date to MedicalStatus Table, with reference to MedicalEvent ID
        medical_status = MedicalStatus(
            user_id=record.user_id,
            status_type="MC",
            description=status,
            start_date=datetime.strptime(start_date, "%d%m%y").date(),
            end_date=datetime.strptime(end_date, "%d%m%y").date(),
            source_event_id=record.id
        )
        db.add(medical_status)
        db.commit()
        db.refresh(record)
    return record

def create_user_record(
    name: str,
    symptoms: str,
    diagnosis: str | None = None
):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid name format")
    rank, full_name = parts
    user = db.query(User).filter(User.rank == rank, User.full_name == full_name).first()
    if not user:
        raise ValueError("User not found")

    event = MedicalEvent(
        user_id=user.id,
        event_type="RSO",
        symptoms=symptoms,
        diagnosis=diagnosis,
        event_datetime=now_sg().replace(microsecond=0),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

# MA Records

def get_ma_records(name: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        return []
    rank, full_name = parts
    return db.query(MedicalEvent).join(User).filter(
        User.rank == rank,
        User.full_name == full_name,
        MedicalEvent.event_type == "MA"
    ).all()

def create_ma_record(
    name: str,
    appointment: str,
    appointment_location: str,
    appointment_date: str,
    appointment_time: str
):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid name format")
    rank, full_name = parts
    user = db.query(User).filter(User.rank == rank, User.full_name == full_name).first()
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
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def update_ma_record(
    record_id: int,
    appointment: str,
    appointment_location: str,
    appointment_date: str,
    appointment_time: str,
    instructor: str | None = None
):
    record = db.query(MedicalEvent).filter(MedicalEvent.id == record_id).first()
    if record:
        record.appointment_type = appointment
        record.location = appointment_location
        record.event_datetime = datetime.combine(
            datetime.strptime(appointment_date, "%d%m%y").date(),
            datetime.strptime(appointment_time, "%H%M").time(),
            tzinfo=SG_TZ,
        )
        if instructor:
            record.endorsed_by = instructor
        db.commit()
        db.refresh(record)
    return record

# RSI Records
def get_user_rsi_records(name: str):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        return []
    rank, full_name = parts
    return db.query(MedicalEvent).join(User).filter(
        User.rank == rank,
        User.full_name == full_name,
        MedicalEvent.event_type == "RSI"
    ).all()

def create_rsi_record(
    name: str,
    symptoms: str,
    diagnosis: str | None = None
):
    parts = name.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Invalid name format")
    rank, full_name = parts
    user = db.query(User).filter(User.rank == rank, User.full_name == full_name).first()
    if not user:
        raise ValueError("User not found")

    event = MedicalEvent(
        user_id=user.id,
        event_type="RSI",
        symptoms=symptoms,
        diagnosis=diagnosis or "",
        event_datetime=now_sg().replace(microsecond=0),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def update_rsi_record(
    record_id: int,
    diagnosis: str,
    status_type: str,
    status: str,
    start_date: str,
    end_date: str
):
    record = db.query(MedicalEvent).filter(MedicalEvent.id == record_id).first()
    if record:
        if _has_diagnosis(record.diagnosis):
            return record
        record.diagnosis = diagnosis
        if status == "N/A":
            db.commit()
            db.refresh(record)
        else:
            medical_status = MedicalStatus(
                user_id=record.user_id,
                status_type=status_type,
                description=status,
                start_date=datetime.strptime(start_date, "%d%m%y").date(),
                end_date=datetime.strptime(end_date, "%d%m%y").date(),
                source_event_id=record.id
            )
            db.add(medical_status)
            db.commit()
            db.refresh(record)
        return record


# Other Queries
def get_medical_events():
    return db.query(
        MedicalEvent,
        User
	).join(
		User, MedicalEvent.user_id == User.id
    ).all()

def get_all_cadets():
    return db.query(User).filter(
        User.role == "cadet"
	).all()

def get_all_instructors():
    return db.query(User).filter(
        User.role == "instructor"
    ).all()
