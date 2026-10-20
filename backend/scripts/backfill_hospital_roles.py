"""
One-off repair: gives every existing hospital any default roles it's
missing (PATIENT / DOCTOR / HOSPITAL_ADMIN).

Hospitals created before Phase 6 only got a PATIENT role, so
appointing a hospital admin there failed. New hospitals already get
all roles, and admin promotion now self-heals too, so this script is
only needed once to tidy up old data. Safe to re-run: hospitals that
already have every role are skipped.

Run: docker compose exec backend python scripts/backfill_hospital_roles.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base import Base  # noqa: F401  (registers every model so FKs resolve)
from app.db.session import SessionLocal
from app.models.hospital import Hospital
from app.services.hospital_service import ensure_hospital_roles


def main():
    db = SessionLocal()
    try:
        hospitals = db.query(Hospital).all()
        for hospital in hospitals:
            created = ensure_hospital_roles(db, hospital.id)
            if created:
                print(f"{hospital.name}: added {', '.join(created)}")
            else:
                print(f"{hospital.name}: already complete")
        print(f"Checked {len(hospitals)} hospital(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
