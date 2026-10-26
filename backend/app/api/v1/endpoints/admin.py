"""Admin Portal endpoints, split by scope:
- /admin/platform/*  -> SUPER_ADMIN only, cuts across all hospitals
- /admin/hospital/*  -> SUPER_ADMIN or HOSPITAL_ADMIN, scoped to the
  caller's own hospital (a HOSPITAL_ADMIN's hospital_id comes from
  their own account, same "operate on my own data" pattern used
  throughout the app — they can never pass a different hospital_id)
"""
import uuid

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import HospitalStatsOut, PlatformStatsOut, PromoteToHospitalAdminRequest, StaffMemberOut
from app.schemas.analytics import AnalyticsOut
from app.schemas.hospital import HospitalCreate, HospitalOut, HospitalUpdate
from app.services import admin_service, analytics_service, hospital_service

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Platform-wide (SUPER_ADMIN only) ---

@router.get("/platform/stats", response_model=PlatformStatsOut)
def platform_stats(current_user: User = Depends(require_role("SUPER_ADMIN")), db: Session = Depends(get_db)):
    return admin_service.get_platform_stats(db)


@router.get("/platform/hospitals", response_model=list[HospitalOut])
def list_all_hospitals(current_user: User = Depends(require_role("SUPER_ADMIN")), db: Session = Depends(get_db)):
    return hospital_service.list_hospitals(db, include_inactive=True)


@router.post("/platform/hospitals", response_model=HospitalOut, status_code=status.HTTP_201_CREATED)
def create_hospital(payload: HospitalCreate, current_user: User = Depends(require_role("SUPER_ADMIN")), db: Session = Depends(get_db)):
    try:
        return hospital_service.create_hospital(db, payload, current_user.id)
    except AlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/platform/hospitals/{hospital_id}", response_model=HospitalOut)
def update_hospital(hospital_id: str, payload: HospitalUpdate, current_user: User = Depends(require_role("SUPER_ADMIN")), db: Session = Depends(get_db)):
    try:
        return hospital_service.update_hospital(db, uuid.UUID(hospital_id), payload, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/platform/hospitals/{hospital_id}/admins", response_model=StaffMemberOut)
def promote_hospital_admin(hospital_id: str, payload: PromoteToHospitalAdminRequest, current_user: User = Depends(require_role("SUPER_ADMIN")), db: Session = Depends(get_db)):
    try:
        user = admin_service.promote_user_to_hospital_admin(db, uuid.UUID(hospital_id), payload.email, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return _to_staff_out(db, user)


@router.get("/platform/analytics", response_model=AnalyticsOut)
def platform_analytics(days: int = Query(30, ge=1, le=365), current_user: User = Depends(require_role("SUPER_ADMIN")), db: Session = Depends(get_db)):
    return analytics_service.platform_analytics(db, days)


# --- Own-hospital scope (SUPER_ADMIN or HOSPITAL_ADMIN) ---

@router.get("/hospital/stats", response_model=HospitalStatsOut)
def my_hospital_stats(current_user: User = Depends(require_role("SUPER_ADMIN", "HOSPITAL_ADMIN")), db: Session = Depends(get_db)):
    hospital_id = _resolve_admin_hospital_id(current_user)
    return admin_service.get_hospital_stats(db, hospital_id)


@router.get("/hospital/analytics", response_model=AnalyticsOut)
def my_hospital_analytics(days: int = Query(30, ge=1, le=365), current_user: User = Depends(require_role("SUPER_ADMIN", "HOSPITAL_ADMIN")), db: Session = Depends(get_db)):
    hospital_id = _resolve_admin_hospital_id(current_user)
    return analytics_service.hospital_analytics(db, hospital_id, days)


@router.get("/hospital/staff", response_model=list[StaffMemberOut])
def my_hospital_staff(current_user: User = Depends(require_role("SUPER_ADMIN", "HOSPITAL_ADMIN")), db: Session = Depends(get_db)):
    hospital_id = _resolve_admin_hospital_id(current_user)
    users = admin_service.list_hospital_staff(db, hospital_id)
    return [_to_staff_out(db, u) for u in users]


def _resolve_admin_hospital_id(current_user: User) -> uuid.UUID:
    if not current_user.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account isn't scoped to a hospital — SUPER_ADMIN must use /admin/platform endpoints instead",
        )
    return current_user.hospital_id


def _to_staff_out(db: Session, user: User) -> StaffMemberOut:
    role = db.get(Role, user.role_id)
    return StaffMemberOut(id=str(user.id), email=user.email, full_name=user.full_name, role=role.name, is_active=user.is_active)
