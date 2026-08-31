"""Public, read-only hospital directory — used by registration forms
(picking which hospital to join) and the "find a doctor" flow.
Creating/editing hospitals is SUPER_ADMIN-only and lives under
/admin/platform/hospitals (see endpoints/admin.py) — this file
deliberately has no POST or PATCH."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.hospital import HospitalOut
from app.services import hospital_service

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[HospitalOut])
def list_hospitals(db: Session = Depends(get_db)):
    return hospital_service.list_hospitals(db)


@router.get("/{hospital_id}", response_model=HospitalOut)
def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    try:
        return hospital_service.get_hospital_by_id(db, uuid.UUID(hospital_id))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
