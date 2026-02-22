import csv
from db.database import SessionLocal
from db.models import User

REQUIRED = {"full_name", "role", "rank"}

ALLOWED_RANKS = {
    # Officers
    "2LT", "LTA", "CPT", "MAJ", "LTC", "SLTC", "COL", "BG", "MG", "LG", "GEN",
    # WOSpec
    "3WO", "2WO", "1WO", "MWO", "SWO", "CWO",
    # Specialists/Enlistees
    "REC", "PTE", "LCP", "CPL", "CFC", "3SG", "2SG", "1SG", "SSG", "MSG",
    # Military Experts (adjust to your unit's official list)
    "ME1", "ME2", "ME3", "ME4", "ME4A", "ME4T", "ME5", "ME6", "ME7", "ME8",
}

ROLE_MAP = {
    "instructor": "Instructor",
    "cadet": "Cadet",
    "admin": "Admin",
}

BASE_ROLES = {"Instructor", "Cadet"}


def _parse_bool(value):
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "t"}


def _require_full_caps(name):
    if not name or name != name.strip():
        return False
    return name == name.upper()

def _normalize_username(value):
    if value is None:
        return None
    name = str(value).strip()
    if not name:
        return None
    if name.startswith("@"):
        name = name[1:]
    return name or None

def _normalize_header(value):
    if value is None:
        return ""
    text = str(value).lstrip("\ufeff") 
    text = text.strip().lower()
    if text.endswith(":"):
        text = text[:-1].strip()
    text = text.replace("-", " ").replace("  ", " ")
    return "_".join(text.split())


def import_users(path, require_username=False):
    session = SessionLocal()
    created = 0
    updated = 0
    processed = 0
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            normalized_fieldnames = [
                _normalize_header(name) for name in (reader.fieldnames or [])
            ]
            header_fields = set(normalized_fieldnames)
            if not REQUIRED.issubset(header_fields):
                raise ValueError(f"Missing columns: {REQUIRED - header_fields}")
            if "telegram_id" not in header_fields and "telegram_username" not in header_fields:
                raise ValueError("CSV must include telegram_id or telegram_username column")
            if require_username and "telegram_username" not in header_fields:
                raise ValueError("CSV must include telegram_username column")

            for row in reader:
                processed += 1
                normalized_row = {
                    _normalize_header(key): value for key, value in row.items()
                }
                telegram_id_raw = (normalized_row.get("telegram_id") or "").strip()
                telegram_id = None
                if telegram_id_raw:
                    try:
                        telegram_id = int(telegram_id_raw)
                    except ValueError:
                        raise ValueError(f"telegram_id must be a valid integer: {telegram_id_raw!r}")

                telegram_username = _normalize_username(
                    normalized_row.get("telegram_username")
                )
                if telegram_id is None and not telegram_username:
                    raise ValueError("Each row must include telegram_id or telegram_username")
                if require_username and not telegram_username:
                    raise ValueError("Each row must include telegram_username")

                full_name = (normalized_row.get("full_name") or "").strip()
                if not _require_full_caps(full_name):
                    raise ValueError(f"full_name must be FULL CAPS with no leading/trailing spaces: {full_name!r}")

                rank = (normalized_row.get("rank") or "").strip().upper()
                if not rank:
                    raise ValueError("rank is required and cannot be empty")
                if rank not in ALLOWED_RANKS:
                    raise ValueError(f"rank must be a valid SAF rank: {rank!r}")

                role_raw = (normalized_row.get("role") or "").strip().lower()
                if role_raw not in ROLE_MAP:
                   raise ValueError(
                        f"role must be one of {sorted(ROLE_MAP.values())}: {normalized_row.get('role')!r}"
                    )
                role = ROLE_MAP[role_raw]

                is_admin = _parse_bool(normalized_row.get("is_admin"))
                if role == "Admin":
                    base_role_raw = (normalized_row.get("base_role") or "").strip().lower()
                    if not base_role_raw:
                        raise ValueError(
                            "role=Admin requires base_role column set to Instructor or Cadet"
                        )
                    if base_role_raw not in ROLE_MAP or ROLE_MAP[base_role_raw] not in BASE_ROLES:
                        raise ValueError(
                            f"base_role must be Instructor or Cadet when role=Admin: {normalized_row.get('base_role')!r}")
                    role = ROLE_MAP[base_role_raw]
                    is_admin = True
                if is_admin and role not in BASE_ROLES:
                    raise ValueError("is_admin can only be true when role is Instructor or Cadet")

                user = None
                if telegram_id is not None:
                    user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if user is None and telegram_username:
                    user = session.query(User).filter_by(telegram_username=telegram_username).first()
                if not user:
                    user = User()
                    session.add(user)
                    created += 1
                else:
                    updated += 1

                if telegram_id is not None:
                    user.telegram_id = telegram_id
                if telegram_username:
                    user.telegram_username = telegram_username
                user.full_name = full_name
                user.rank = rank
                user.role = role
                user.is_admin = is_admin
                is_active = normalized_row.get("is_active", "true")
                user.is_active = str(is_active).lower() != "false"

        session.commit()
        return {"processed": processed, "created": created, "updated": updated}
    except:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m db.import_users_csv <path-to-csv>")
    result = import_users(sys.argv[1])
    print(
        "Import complete.",
        f"Processed: {result['processed']}, created: {result['created']}, updated: {result['updated']}",
    )
