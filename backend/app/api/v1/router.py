from fastapi import APIRouter

from app.api.v1.endpoints import admin, appointments, auth, chat, doctors, hospitals, medical_records, notifications, patients, payments

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(hospitals.router)
api_router.include_router(patients.router)
api_router.include_router(doctors.router)
api_router.include_router(appointments.router)
api_router.include_router(medical_records.router)
api_router.include_router(admin.router)
api_router.include_router(chat.router)
api_router.include_router(notifications.router)
api_router.include_router(payments.router)
