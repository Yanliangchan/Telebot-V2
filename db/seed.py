# db/seed.py
from db.database import SessionLocal
from db.models import User, MovementLog

def seed():
    session = SessionLocal()
    try:
        user = User(
            telegram_id=123456789,
            telegram_username="testuser",
            full_name="TEST USER",
            rank="ME4T",
            role="Cadet",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        session.flush()  # assign PKs without commit

        log = MovementLog(
            from_location="HQ",
            to_location="Training",
            time="0930",
            created_by=user.telegram_id,
        )
        session.add(log)

        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    seed()
    print("Seeded.")
