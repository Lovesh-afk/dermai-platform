"""Open for now — see hospital_service.py's docstring and
docs/DECISIONS.md for why, and the plan to lock this behind
SUPER_ADMIN auth once Phase 6 (Admin Portal) exists."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.db.session import get_db
from app.schemas.hospital import HospitalCreate, HospitalOut
from app.services import hospital_service

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.post("", response_model=HospitalOut, status_code=status.HTTP_201_CREATED)
def create_hospital(payload: HospitalCreate, db: Session = Depends(get_db)):
    try:
        return hospital_service.create_hospital(db, payload)
    except AlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("", response_model=list[HospitalOut])
def list_hospitals(db: Session = Depends(get_db)):
    return hospital_service.list_hospitals(db)


@router.get("/{hospital_id}", response_model=HospitalOut)
def get_hospital(hospital_id: str, db: Session = Depends(get_db)):
    try:
        return hospital_service.get_hospital_by_id(db, uuid.UUID(hospital_id))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
