"""Medical record creation — doctor-only, and only for a patient they
share an appointment with (enforced in the service layer via
get_patient_for_doctor). Reading a specific record by ID is left for
a later phase once there's a concrete need for it beyond the
patient's own list (GET /patients/me/medical-records, Phase 4) and
the doctor's own list (GET /doctors/me/medical-records, this phase)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordOut
from app.services import doctor_service, medical_record_service

router = APIRouter(prefix="/medical-records", tags=["medical-records"])


@router.post("", response_model=MedicalRecordOut, status_code=status.HTTP_201_CREATED)
def create_medical_record(payload: MedicalRecordCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        doctor = doctor_service.get_doctor_by_user_id(db, current_user.id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can create medical records")

    try:
        return medical_record_service.create_medical_record(db, payload, doctor)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
