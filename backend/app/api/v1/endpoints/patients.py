"""Patient Portal endpoints — everything here operates on "my own"
data only (the logged-in user's own patient profile), enforced by
always resolving the patient record from get_current_user rather
than trusting a patient_id in the URL. Cross-patient access (a doctor
viewing a specific patient) is a Phase 5 (Doctor Portal) concern with
its own RBAC checks — deliberately not mixed in here."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.appointment import AppointmentOut
from app.schemas.medical_record import MedicalRecordOut
from app.schemas.patient import PatientProfileCreate, PatientProfileOut, PatientProfileUpdate
from app.schemas.skin_image import SkinImageOut
from app.services import appointment_service, patient_service, prediction_service, skin_image_service
from app.services.prediction_service import AnalysisNotAllowedError
from app.services.medical_record_service import list_records_for_patient
from app.services.skin_image_service import ImageTooLargeError, UnsupportedImageTypeError

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("/me", response_model=PatientProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(payload: PatientProfileCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        patient = patient_service.create_patient_profile(db, current_user, payload)
    except AlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return PatientProfileOut(id=str(patient.id), user_id=str(patient.user_id), **payload.model_dump())


@router.get("/me", response_model=PatientProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        patient = patient_service.get_patient_by_user_id(db, current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return patient


@router.patch("/me", response_model=PatientProfileOut)
def update_my_profile(payload: PatientProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = _require_patient_profile(db, current_user)
    return patient_service.update_patient_profile(db, patient, payload)


@router.get("/me/appointments", response_model=list[AppointmentOut])
def get_my_appointments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = _require_patient_profile(db, current_user)
    return appointment_service.list_appointments_for_patient(db, patient.id)


@router.get("/me/medical-records", response_model=list[MedicalRecordOut])
def get_my_medical_records(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = _require_patient_profile(db, current_user)
    return list_records_for_patient(db, patient.id)


@router.post("/me/images", response_model=SkinImageOut, status_code=status.HTTP_201_CREATED)
async def upload_skin_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = _require_patient_profile(db, current_user)
    content = await file.read()
    try:
        image = skin_image_service.upload_skin_image(
            db, patient, content, filename=file.filename or "upload", content_type=file.content_type or "application/octet-stream"
        )
    except (UnsupportedImageTypeError, ImageTooLargeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Start AI analysis right away; the response comes back immediately
    # with status "queued_for_analysis" and the frontend polls for the result.
    return prediction_service.request_analysis(db, image)


@router.post("/me/images/{image_id}/analyze", response_model=SkinImageOut, status_code=status.HTTP_202_ACCEPTED)
def analyze_my_image(image_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-runs analysis for an image whose previous attempt failed."""
    patient = _require_patient_profile(db, current_user)
    try:
        image = skin_image_service.get_image_for_patient(db, uuid.UUID(image_id), patient.id)
        return prediction_service.request_analysis(db, image)
    except (NotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    except AnalysisNotAllowedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/me/images", response_model=list[SkinImageOut])
def get_my_images(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient = _require_patient_profile(db, current_user)
    return skin_image_service.list_images_for_patient(db, patient.id)


def _require_patient_profile(db: Session, user: User):
    try:
        return patient_service.get_patient_by_user_id(db, user.id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patient profile found — create one via POST /patients/me first",
        )
