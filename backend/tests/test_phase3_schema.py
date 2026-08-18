"""Unit tests for Phase 3: patient/doctor profiles, appointments,
medical records, and audit logging — proving the schema's
relationships and constraints actually hold, not just that the
tables exist."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.appointment import AppointmentStatus
from app.models.hospital import Hospital
from app.models.role import Role
from app.schemas.appointment import AppointmentCreate
from app.schemas.doctor import DoctorProfileCreate
from app.schemas.medical_record import MedicalRecordCreate
from app.schemas.patient import PatientProfileCreate
from app.schemas.auth import UserRegister
from app.services import (
    appointment_service,
    auth_service,
    doctor_service,
    medical_record_service,
    patient_service,
)
from app.services.appointment_service import DoctorUnavailableError, SlotConflictError
from app.services.audit_service import log_audit_event


def _seed_hospital_and_roles(db_session):
    hospital = Hospital(name="Test Hospital", slug="test-hospital")
    db_session.add(hospital)
    db_session.commit()
    db_session.refresh(hospital)

    db_session.add(Role(name="PATIENT", permissions=["appointments:read"], hospital_id=hospital.id))
    db_session.add(Role(name="DOCTOR", permissions=["appointments:read", "appointments:write"], hospital_id=hospital.id))
    db_session.commit()
    return hospital


def _register_user(db_session, email, role_name="PATIENT", hospital_slug="test-hospital"):
    payload = UserRegister(email=email, password="strongpass123", full_name="Test User", hospital_slug=hospital_slug)
    user = auth_service.register_user(db_session, payload)
    return user


# --- Patient profile ---

def test_create_patient_profile_success(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    user = _register_user(db_session, "patient1@example.com")

    profile = patient_service.create_patient_profile(
        db_session, user, PatientProfileCreate(gender="female", phone="1234567890")
    )

    assert profile.user_id == user.id
    assert profile.gender == "female"


def test_duplicate_patient_profile_raises(db_session):
    _seed_hospital_and_roles(db_session)
    user = _register_user(db_session, "patient2@example.com")
    patient_service.create_patient_profile(db_session, user, PatientProfileCreate())

    with pytest.raises(AlreadyExistsError):
        patient_service.create_patient_profile(db_session, user, PatientProfileCreate())


def test_get_patient_by_user_id_not_found_raises(db_session):
    with pytest.raises(NotFoundError):
        patient_service.get_patient_by_user_id(db_session, uuid.uuid4())


# --- Doctor profile ---

def test_create_doctor_profile_success(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    user = _register_user(db_session, "doctor1@example.com", hospital_slug="test-hospital")

    doctor = doctor_service.create_doctor_profile(
        db_session, user,
        DoctorProfileCreate(hospital_id=str(hospital.id), license_number="LIC-001", specialization="Dermatology"),
    )

    assert doctor.hospital_id == hospital.id
    assert doctor.is_accepting_appointments is True


def test_duplicate_license_number_raises(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    user1 = _register_user(db_session, "doctor2@example.com")
    user2 = _register_user(db_session, "doctor3@example.com")

    doctor_service.create_doctor_profile(
        db_session, user1, DoctorProfileCreate(hospital_id=str(hospital.id), license_number="LIC-DUP")
    )
    with pytest.raises(AlreadyExistsError):
        doctor_service.create_doctor_profile(
            db_session, user2, DoctorProfileCreate(hospital_id=str(hospital.id), license_number="LIC-DUP")
        )


def test_create_doctor_profile_unknown_hospital_raises(db_session):
    _seed_hospital_and_roles(db_session)
    user = _register_user(db_session, "doctor4@example.com")

    with pytest.raises(NotFoundError):
        doctor_service.create_doctor_profile(
            db_session, user, DoctorProfileCreate(hospital_id=str(uuid.uuid4()), license_number="LIC-002")
        )


# --- Appointments ---

def _make_patient_and_doctor(db_session, hospital):
    patient_user = _register_user(db_session, "apt-patient@example.com")
    patient = patient_service.create_patient_profile(db_session, patient_user, PatientProfileCreate())

    doctor_user = _register_user(db_session, "apt-doctor@example.com")
    doctor = doctor_service.create_doctor_profile(
        db_session, doctor_user, DoctorProfileCreate(hospital_id=str(hospital.id), license_number="LIC-APT")
    )
    return patient, doctor


def test_book_appointment_success(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)

    slot = datetime.now(timezone.utc) + timedelta(days=1)
    appointment = appointment_service.book_appointment(
        db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot, reason="Skin rash")
    )

    assert appointment.status == AppointmentStatus.PENDING
    assert appointment.hospital_id == hospital.id


def test_book_appointment_with_unavailable_doctor_raises(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)
    doctor.is_accepting_appointments = False
    db_session.add(doctor)
    db_session.commit()

    slot = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(DoctorUnavailableError):
        appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))


def test_double_booking_same_slot_raises(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)
    slot = datetime.now(timezone.utc) + timedelta(days=2)

    appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))

    with pytest.raises(SlotConflictError):
        appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))


def test_cancel_appointment_frees_the_slot(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)
    slot = datetime.now(timezone.utc) + timedelta(days=3)

    appointment = appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))
    appointment_service.cancel_appointment(db_session, appointment.id, "Patient rescheduled", patient.user_id)

    # Same slot should now be bookable again since the prior one is cancelled
    new_appointment = appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))
    assert new_appointment.status == AppointmentStatus.PENDING


def test_list_appointments_for_patient_and_doctor(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)
    slot = datetime.now(timezone.utc) + timedelta(days=4)
    appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))

    assert len(appointment_service.list_appointments_for_patient(db_session, patient.id)) == 1
    assert len(appointment_service.list_appointments_for_doctor(db_session, doctor.id)) == 1


# --- Medical records ---

def test_create_medical_record_success(db_session):
    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)

    record = medical_record_service.create_medical_record(
        db_session,
        MedicalRecordCreate(patient_id=str(patient.id), doctor_id=str(doctor.id), diagnosis="Mild eczema", notes="Prescribed moisturizer"),
        created_by_user_id=doctor.user_id,
    )

    assert record.diagnosis == "Mild eczema"
    assert record.hospital_id == hospital.id


def test_create_medical_record_unknown_patient_raises(db_session):
    with pytest.raises(NotFoundError):
        medical_record_service.create_medical_record(
            db_session, MedicalRecordCreate(patient_id=str(uuid.uuid4())), created_by_user_id=uuid.uuid4()
        )


# --- Audit log ---

def test_booking_an_appointment_writes_an_audit_log_entry(db_session):
    from app.models.audit_log import AuditLog
    from sqlalchemy import select

    hospital = _seed_hospital_and_roles(db_session)
    patient, doctor = _make_patient_and_doctor(db_session, hospital)
    slot = datetime.now(timezone.utc) + timedelta(days=5)

    appointment_service.book_appointment(db_session, patient, AppointmentCreate(doctor_id=str(doctor.id), scheduled_at=slot))

    entries = db_session.execute(select(AuditLog).where(AuditLog.action == "appointment.book")).scalars().all()
    assert len(entries) == 1
    assert entries[0].resource_type == "Appointment"


def test_log_audit_event_directly(db_session):
    entry = log_audit_event(db_session, action="test.event", metadata={"key": "value"})
    assert entry.id is not None
    assert entry.event_metadata == {"key": "value"}
