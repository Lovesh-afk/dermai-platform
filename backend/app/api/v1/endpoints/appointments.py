"""Booking/cancelling appointments. Booking always books on behalf of
the logged-in patient (never a patient_id passed by the client) —
same "operate on my own data only" rule as patients.py."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.schemas.appointment import AppointmentCancel, AppointmentCreate, AppointmentOut, AppointmentStatusUpdate
from app.services import appointment_service, doctor_service, patient_service
from app.services.appointment_service import DoctorUnavailableError, SlotConflictError

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(payload: AppointmentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        patient = patient_service.get_patient_by_user_id(db, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create a patient profile first via POST /patients/me")

    try:
        return appointment_service.book_appointment(db, patient, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DoctorUnavailableError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except SlotConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(appointment_id: str, payload: AppointmentCancel, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return appointment_service.cancel_appointment(
            db, uuid.UUID(appointment_id), payload.cancellation_reason, current_user.id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
def update_appointment_status(appointment_id: str, payload: AppointmentStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        doctor = doctor_service.get_doctor_by_user_id(db, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can update an appointment's status")

    try:
        return appointment_service.update_appointment_status(db, uuid.UUID(appointment_id), payload.status, doctor)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
