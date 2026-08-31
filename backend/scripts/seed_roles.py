"""
Seeds the platform-level roles needed before anyone can register, AND
bootstraps the very first SUPER_ADMIN account — without this, nobody
could ever reach the SUPER_ADMIN-only endpoints added in Phase 6,
since creating a hospital admin requires already being a SUPER_ADMIN.
This is the one deliberate exception to "every account is created
through the API" in the whole app, and it's why this has to be a
one-off script run directly against the database rather than an API
endpoint — there's no user yet to authenticate as.

Run once against a fresh DB: python scripts/seed_roles.py

Credentials come from env vars if set, otherwise fall back to fixed
dev defaults — fine for local development, but change
SUPER_ADMIN_PASSWORD before running this against anything real.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password
from app.db.base import Base  # imports every model so FK resolution works in this standalone process
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User

PLATFORM_ROLES = [
    {"name": "SUPER_ADMIN", "permissions": ["*"], "hospital_id": None},
    {"name": "PATIENT", "permissions": ["appointments:read", "appointments:write", "predictions:read"], "hospital_id": None},
]

SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "admin@dermai-platform.com")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "change-me-immediately")
SUPER_ADMIN_NAME = os.environ.get("SUPER_ADMIN_NAME", "Platform Admin")


def main():
    db = SessionLocal()
    try:
        for role_data in PLATFORM_ROLES:
            exists = db.query(Role).filter_by(name=role_data["name"], hospital_id=role_data["hospital_id"]).first()
            if not exists:
                db.add(Role(**role_data))
                print(f"Seeded role: {role_data['name']}")
        db.commit()

        super_admin_role = db.query(Role).filter_by(name="SUPER_ADMIN", hospital_id=None).first()

        existing_admin = db.query(User).filter_by(email=SUPER_ADMIN_EMAIL).first()
        if existing_admin:
            print(f"SUPER_ADMIN account already exists ({SUPER_ADMIN_EMAIL}) — skipping bootstrap.")
        else:
            admin_user = User(
                email=SUPER_ADMIN_EMAIL,
                hashed_password=hash_password(SUPER_ADMIN_PASSWORD),
                full_name=SUPER_ADMIN_NAME,
                role_id=super_admin_role.id,
                hospital_id=None,
            )
            db.add(admin_user)
            db.commit()
            print(f"Bootstrapped SUPER_ADMIN account: {SUPER_ADMIN_EMAIL}")
            if SUPER_ADMIN_PASSWORD == "change-me-immediately":
                print("WARNING: using the default password — set SUPER_ADMIN_PASSWORD before running this for real.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
