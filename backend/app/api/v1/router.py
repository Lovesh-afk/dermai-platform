from fastapi import APIRouter

from app.api.v1.endpoints import appointments, auth, doctors, hospitals, medical_records, patients

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(hospitals.router)
api_router.include_router(patients.router)
api_router.include_router(doctors.router)
api_router.include_router(appointments.router)
api_router.include_router(medical_records.router)
