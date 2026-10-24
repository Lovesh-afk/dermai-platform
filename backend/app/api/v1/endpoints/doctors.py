"""Doctor directory (public-ish, used by patients browsing) + Doctor
Portal endpoints (the doctor managing their own queue and patients).
Everything under /doctors/me/* resolves "which doctor" from the
logged-in user, same "operate on my own data only" rule used
throughout the app — a doctor can never pass another doctor's ID to
see their queue."""
import uuid
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import AlreadyExistsError, NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.schemas.appointment import AppointmentOut
from app.schemas.availability import DoctorSlotsOut, Slot, SlotDay, WeeklyHoursIn, WeeklyHoursOut, WorkingHoursBlock
from app.schemas.doctor import DoctorProfileCreate, DoctorProfileOut, DoctorProfileUpdate
from app.schemas.medical_record import MedicalRecordOut
from app.schemas.patient import PatientProfileOut
from app.schemas.skin_image import SkinImageOut
from app.services import appointment_service, doctor_service, medical_record_service, patient_service, scheduling_service, skin_image_service

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


@router.get("/me", response_model=DoctorProfileOut)
def get_my_doctor_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    return doctor


@router.patch("/me", response_model=DoctorProfileOut)
def update_my_doctor_profile(payload: DoctorProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    return doctor_service.update_doctor_profile(db, doctor, payload)


@router.get("/me/appointments", response_model=list[AppointmentOut])
def get_my_appointment_queue(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    return appointment_service.list_appointments_for_doctor(db, doctor.id)


@router.get("/me/patients", response_model=list[PatientProfileOut])
def get_my_patients(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    return patient_service.list_patients_for_doctor(db, doctor.id)


@router.get("/me/patients/{patient_id}", response_model=PatientProfileOut)
def get_my_patient(patient_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    try:
        return patient_service.get_patient_for_doctor(db, uuid.UUID(patient_id), doctor.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/me/patients/{patient_id}/images", response_model=list[SkinImageOut])
def get_my_patient_images(patient_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A patient's skin photos and AI results — same access rule as
    viewing their profile: only doctors with a shared appointment."""
    doctor = _require_doctor_profile(db, current_user)
    try:
        patient = patient_service.get_patient_for_doctor(db, uuid.UUID(patient_id), doctor.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return skin_image_service.list_images_for_patient(db, patient.id)


@router.get("/me/medical-records", response_model=list[MedicalRecordOut])
def get_my_created_records(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    return medical_record_service.list_records_by_doctor(db, doctor.id)


@router.get("/me/availability", response_model=WeeklyHoursOut)
def get_my_hours(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = _require_doctor_profile(db, current_user)
    return _hours_out(db, doctor)


@router.put("/me/availability", response_model=WeeklyHoursOut)
def set_my_hours(payload: WeeklyHoursIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Replaces the weekly schedule. Existing bookings are kept even if
    they now fall outside the new hours; the doctor can cancel them."""
    doctor = _require_doctor_profile(db, current_user)
    scheduling_service.set_weekly_hours(db, doctor, [(b.weekday, b.start_time, b.end_time) for b in payload.blocks])
    return _hours_out(db, doctor)


@router.get("/{doctor_id}/slots", response_model=DoctorSlotsOut)
def get_doctor_slots(doctor_id: str, days: int = Query(14, ge=1, le=scheduling_service.MAX_SLOT_DAYS), db: Session = Depends(get_db)):
    """Open 30-minute slots for the next `days` days. Empty if the doctor
    isn't currently accepting appointments."""
    try:
        doctor = doctor_service.get_doctor_by_id(db, uuid.UUID(doctor_id))
    except (NotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    zone = scheduling_service.hospital_zone(db, doctor)
    days_out = []
    if doctor.is_accepting_appointments:
        days_out = [
            SlotDay(date=d, slots=[Slot(start=t.astimezone(timezone.utc), label=t.strftime("%H:%M")) for t in slots])
            for d, slots in scheduling_service.available_slots(db, doctor, days)
        ]
    return DoctorSlotsOut(doctor_id=doctor.id, timezone=zone.key, slot_minutes=scheduling_service.SLOT_MINUTES, days=days_out)


def _hours_out(db: Session, doctor) -> WeeklyHoursOut:
    blocks, is_default = scheduling_service.get_weekly_hours(db, doctor)
    return WeeklyHoursOut(
        is_default=is_default,
        timezone=scheduling_service.hospital_zone(db, doctor).key,
        slot_minutes=scheduling_service.SLOT_MINUTES,
        blocks=[WorkingHoursBlock(weekday=w, start_time=st, end_time=et) for w, st, et in blocks],
    )


@router.get("", response_model=list[DoctorProfileOut])
def list_doctors(hospital_id: str = Query(...), db: Session = Depends(get_db)):
    return doctor_service.list_doctors_by_hospital(db, uuid.UUID(hospital_id))


@router.get("/{doctor_id}", response_model=DoctorProfileOut)
def get_doctor(doctor_id: str, db: Session = Depends(get_db)):
    try:
        return doctor_service.get_doctor_by_id(db, uuid.UUID(doctor_id))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def _require_doctor_profile(db: Session, user: User):
    try:
        return doctor_service.get_doctor_by_user_id(db, user.id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No doctor profile found — create one via POST /doctors/me first",
        )
