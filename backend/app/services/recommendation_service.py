"""
Doctor recommendation: ranks the dermatologists a patient can book,
and explains each ranking in plain words.

Deliberately a transparent, rule-based score rather than a learned
model: in healthcare, "why was this doctor suggested?" must have a
clear answer, and there is no historical outcome data to learn from yet.

Score (0-100) = four weighted factors:
    condition match   40  doctor's specialization/bio mentions the patient's condition
    availability      25  fewer upcoming appointments in the next 2 weeks
    experience        20  years in practice, capped at 20
    continuity        15  patient has booked with this doctor before
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.skin_image import SkinImage
from app.models.user import User

WEIGHT_CONDITION, WEIGHT_AVAILABILITY, WEIGHT_EXPERIENCE, WEIGHT_CONTINUITY = 40, 25, 20, 15
EXPERIENCE_CAP_YEARS = 20
AVAILABILITY_WINDOW = timedelta(days=14)
BUSY_AT_APPOINTMENTS = 10  # this many upcoming appointments = zero availability score

# Words in a doctor's specialization or bio that suggest experience with
# each condition the AI photo model can flag. ("normal" has no entry:
# nothing condition-specific to match on.)
CONDITION_KEYWORDS = {
    "acne": ["acne", "cosmetic", "aesthetic"],
    "eczema": ["eczema", "atopic", "dermatitis", "allerg"],
    "fungal": ["fungal", "infection", "infectious", "tinea", "ringworm"],
}
CONDITION_NAMES = {"acne": "acne", "eczema": "eczema", "fungal": "fungal infections"}


@dataclass
class Recommendation:
    doctor: Doctor
    hospital_name: str
    score: int
    reasons: list[str] = field(default_factory=list)


def _aware(dt: datetime) -> datetime:
    """SQLite (tests) returns naive datetimes; Postgres returns aware ones."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def latest_photo_condition(db: Session, patient: Patient) -> str | None:
    """The condition from the patient's most recent analysed photo, or
    None if they have none (or the model saw none of its conditions)."""
    images = db.execute(
        select(SkinImage).where(SkinImage.patient_id == patient.id).order_by(SkinImage.created_at.desc())
    ).scalars().all()
    for image in images:
        if image.prediction is not None:
            cls = image.prediction.predicted_class
            return cls if cls in CONDITION_KEYWORDS else None
    return None


def recommend_doctors(
    db: Session, patient: Patient, patient_user: User,
    condition: str | None = None, max_fee: float | None = None, limit: int = 5,
) -> list[Recommendation]:
    # Patients registered with a hospital see that hospital's doctors;
    # patients who signed up independently can book anywhere on the platform.
    query = (
        select(Doctor, Hospital.name)
        .join(Hospital, Doctor.hospital_id == Hospital.id)
        .join(User, Doctor.user_id == User.id)
        .where(Doctor.is_accepting_appointments.is_(True), Hospital.is_active.is_(True), User.is_active.is_(True))
    )
    if patient_user.hospital_id:
        query = query.where(Doctor.hospital_id == patient_user.hospital_id)
    candidates = db.execute(query).all()
    if max_fee is not None:
        candidates = [(d, h) for d, h in candidates if d.consultation_fee is None or float(d.consultation_fee) <= max_fee]
    if not candidates:
        return []

    doctor_ids = [d.id for d, _ in candidates]
    appointments = db.execute(
        select(Appointment).where(Appointment.doctor_id.in_(doctor_ids), Appointment.status != AppointmentStatus.CANCELLED)
    ).scalars().all()

    now = datetime.now(timezone.utc)
    upcoming_load = {d_id: 0 for d_id in doctor_ids}
    seen_before = set()
    for appt in appointments:
        if appt.status in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED) and now <= _aware(appt.scheduled_at) <= now + AVAILABILITY_WINDOW:
            upcoming_load[appt.doctor_id] += 1
        if appt.patient_id == patient.id:
            seen_before.add(appt.doctor_id)

    results = [
        _score(doctor, hospital_name, condition, upcoming_load[doctor.id], doctor.id in seen_before)
        for doctor, hospital_name in candidates
    ]
    # Best score first; ties go to the more experienced doctor, then alphabetically
    results.sort(key=lambda r: (-r.score, -(r.doctor.years_experience or 0), r.doctor.full_name or ""))
    return results[:limit]


def _score(doctor: Doctor, hospital_name: str, condition: str | None, load: int, seen_before: bool) -> Recommendation:
    score, reasons = 0.0, []

    if condition:
        profile_text = f"{doctor.specialization} {doctor.bio or ''}".lower()
        if any(k in profile_text for k in CONDITION_KEYWORDS[condition]):
            score += WEIGHT_CONDITION
            reasons.append(f"Experienced with {CONDITION_NAMES[condition]}")

    availability = max(0.0, 1 - load / BUSY_AT_APPOINTMENTS)
    score += WEIGHT_AVAILABILITY * availability
    if load == 0:
        reasons.append("Fully available in the next 2 weeks")
    elif load <= 3:
        reasons.append("Good availability in the next 2 weeks")

    if doctor.years_experience:
        score += WEIGHT_EXPERIENCE * min(doctor.years_experience, EXPERIENCE_CAP_YEARS) / EXPERIENCE_CAP_YEARS
        reasons.append(f"{doctor.years_experience} years of experience")

    if seen_before:
        score += WEIGHT_CONTINUITY
        reasons.append("You've booked with this doctor before")

    return Recommendation(doctor=doctor, hospital_name=hospital_name, score=round(score), reasons=reasons)
