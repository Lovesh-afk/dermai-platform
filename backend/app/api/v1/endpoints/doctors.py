"""Public-ish doctor directory endpoints — a patient needs to browse
doctors to pick who to book with. Profile *creation* stays here too
for now (a doctor setting up their own profile) since the Doctor
Portal's richer management screens are Phase 5 — this is just enough
surface for Phase 4's booking flow to work end-to-end."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.doctor import DoctorProfileCreate, DoctorProfileOut
from app.services import doctor_service

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.post("/me", response_model=DoctorProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_doctor_profile(payload: DoctorProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        doctor = doctor_service.create_doctor_profile(db, current_user, payload)
    except AlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return doctor


@router.get("", response_model=list[DoctorProfileOut])
def list_doctors(hospital_id: str = Query(...), db: Session = Depends(get_db)):
    return doctor_service.list_doctors_by_hospital(db, uuid.UUID(hospital_id))


@router.get("/{doctor_id}", response_model=DoctorProfileOut)
def get_doctor(doctor_id: str, db: Session = Depends(get_db)):
    try:
        return doctor_service.get_doctor_by_id(db, uuid.UUID(doctor_id))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
