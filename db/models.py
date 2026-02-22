from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship

from utils.datetime_utils import now_sg


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)
    telegram_username = Column(String, unique=True, nullable=True)
    full_name = Column(String, nullable=False)
    rank = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_sg)
    updated_at = Column(DateTime, default=now_sg, onupdate=now_sg)

    medical_statuses = relationship("MedicalStatus", back_populates="user")
    medical_events = relationship("MedicalEvent", back_populates="user")
    sft_submissions = relationship("SFTSubmission", back_populates="user")


class MovementLog(Base):
    __tablename__ = "movement_logs"

    id = Column(Integer, primary_key=True)
    from_location = Column(String, nullable=False)
    to_location = Column(String, nullable=False)
    time = Column(String, nullable=False)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=now_sg)


class MedicalEvent(Base):
    __tablename__ = "medical_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)
    appointment_type = Column(String)
    location = Column(String)
    symptoms = Column(Text)
    diagnosis = Column(Text)
    endorsed_by = Column(String)
    event_datetime = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=now_sg)

    statuses = relationship("MedicalStatus", back_populates="source_event")
    user = relationship("User", back_populates="medical_events")


class MedicalStatus(Base):
    __tablename__ = "medical_statuses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    source_event_id = Column(Integer, ForeignKey("medical_events.id"))
    created_at = Column(DateTime, default=now_sg)

    user = relationship("User", back_populates="medical_statuses")
    source_event = relationship("MedicalEvent", back_populates="statuses")


class SFTSession(Base):
    __tablename__ = "sft_sessions"

    id = Column(Integer, primary_key=True)
    date = Column(String, nullable=False)
    start = Column(String, nullable=False)
    end = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=now_sg)

    submissions = relationship("SFTSubmission", back_populates="session", cascade="all, delete-orphan")


class SFTSubmission(Base):
    __tablename__ = "sft_submissions"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sft_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_name = Column(String, nullable=False)
    activity = Column(String, nullable=False)
    location = Column(String, nullable=False, default="")
    start = Column(String, nullable=False)
    end = Column(String, nullable=False)
    created_at = Column(DateTime, default=now_sg)

    session = relationship("SFTSession", back_populates="submissions")
    user = relationship("User", back_populates="sft_submissions")
