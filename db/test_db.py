from datetime import date
from db.database import SessionLocal
from db import crud

def run():
    db = SessionLocal()

    # 1. Create test user
    user = crud.create_user(
        db=db,
        telegram_id=123456789,
        telegram_username="test_cadet",
        full_name="ME4T TEST CADET",
        rank="ME4T",
        role="cadet"
    )
    print("Created user:", user.id, user.full_name)

    # 2. Create RSI
    crud.create_medical_event(
        db=db,
        user_id=user.id,
        event_type="RSI",
        symptoms="COUGH, SORE THROAT",
        diagnosis="VIRAL INFECTION"
    )
    print("Created RSI event")

    # 3. Create MC
    crud.create_medical_status(
        db=db,
        user_id=user.id,
        status_type="MC",
        description="MEDICAL CERTIFICATE",
        start_date=date.today(),
        end_date=date.today()
    )
    print("Created MC status")

    db.close()
    print("Test completed successfully.")

if __name__ == "__main__":
    run()
