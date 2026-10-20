"""
Platform-wide (SUPER_ADMIN) and per-hospital (HOSPITAL_ADMIN) admin
operations. Kept as its own service rather than folded into
hospital_service/doctor_service/etc. because these queries cut across
multiple tables for reporting purposes — a different shape of
function than the single-resource CRUD the other services do.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import HospitalStatsOut, PlatformStatsOut
from app.services.audit_service import log_audit_event
from app.services.hospital_service import ensure_hospital_roles


def get_platform_stats(db: Session) -> PlatformStatsOut:
    return PlatformStatsOut(
        total_hospitals=db.execute(select(func.count()).select_from(Hospital)).scalar_one(),
        total_users=db.execute(select(func.count()).select_from(User)).scalar_one(),
        total_patients=db.execute(select(func.count()).select_from(Patient)).scalar_one(),
        total_doctors=db.execute(select(func.count()).select_from(Doctor)).scalar_one(),
        total_appointments=db.execute(select(func.count()).select_from(Appointment)).scalar_one(),
    )


def get_hospital_stats(db: Session, hospital_id: uuid.UUID) -> HospitalStatsOut:
    total_doctors = db.execute(select(func.count()).select_from(Doctor).where(Doctor.hospital_id == hospital_id)).scalar_one()

    # Patients don't carry hospital_id directly (see Patient model —
    # it's derived from their User) so this counts distinct patients
    # via their linked user's hospital_id instead.
    total_patients = db.execute(
        select(func.count()).select_from(Patient).join(User, Patient.user_id == User.id).where(User.hospital_id == hospital_id)
    ).scalar_one()

    total_appointments = db.execute(
        select(func.count()).select_from(Appointment).where(Appointment.hospital_id == hospital_id)
    ).scalar_one()

    total_completed = db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.hospital_id == hospital_id, Appointment.status == AppointmentStatus.COMPLETED
        )
    ).scalar_one()

    return HospitalStatsOut(
        hospital_id=str(hospital_id),
        total_doctors=total_doctors,
        total_patients=total_patients,
        total_appointments=total_appointments,
        total_completed_appointments=total_completed,
    )


def list_hospital_staff(db: Session, hospital_id: uuid.UUID) -> list[User]:
    return list(db.execute(select(User).where(User.hospital_id == hospital_id)).scalars().all())


def promote_user_to_hospital_admin(db: Session, hospital_id: uuid.UUID, email: str, promoted_by_user_id: uuid.UUID) -> User:
    user = db.execute(select(User).where(User.email == email, User.hospital_id == hospital_id)).scalar_one_or_none()
    if not user:
        raise NotFoundError(f"No user with email {email} found in this hospital")

    # Self-heal hospitals created before Phase 6, which never got a
    # HOSPITAL_ADMIN role. Creates it on demand instead of failing.
    ensure_hospital_roles(db, hospital_id)

    admin_role = db.execute(
        select(Role).where(Role.name == "HOSPITAL_ADMIN", Role.hospital_id == hospital_id)
    ).scalar_one()

    user.role_id = admin_role.id
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit_event(
        db, action="user.promote_to_hospital_admin", user_id=promoted_by_user_id, hospital_id=hospital_id,
        resource_type="User", resource_id=str(user.id),
    )
    return user
