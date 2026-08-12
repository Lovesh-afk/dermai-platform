"""Seed the platform-level roles needed before anyone can register.
Run once against a fresh DB: python scripts/seed_roles.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import SessionLocal
from app.models.role import Role

PLATFORM_ROLES = [
    {"name": "SUPER_ADMIN", "permissions": ["*"], "hospital_id": None},
    {"name": "PATIENT", "permissions": ["appointments:read", "appointments:write", "predictions:read"], "hospital_id": None},
]


def main():
    db = SessionLocal()
    try:
        for role_data in PLATFORM_ROLES:
            exists = db.query(Role).filter_by(name=role_data["name"], hospital_id=role_data["hospital_id"]).first()
            if not exists:
                db.add(Role(**role_data))
                print(f"Seeded role: {role_data['name']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
