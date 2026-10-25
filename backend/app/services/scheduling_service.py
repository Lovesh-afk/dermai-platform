"""
Turns a doctor's weekly working hours into bookable 30-minute slots,
and decides whether a requested appointment time is valid.

Time zones: working hours are wall-clock times in the HOSPITAL's zone
("Mon 09:00" means 09:00 in Kolkata), while appointments are stored in
UTC. All conversion happens here, so no other code has to think about it.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.availability import DoctorAvailability
from app.models.doctor import Doctor
from app.models.hospital import Hospital

SLOT_MINUTES = 30
SLOT = timedelta(minutes=SLOT_MINUTES)
MIN_LEAD_TIME = timedelta(minutes=30)  # can't book a slot starting in the next 30 min
MAX_SLOT_DAYS = 31                     # how far ahead the slots endpoint will look

# Used until a doctor sets their own hours: Monday-Friday, 09:00-17:00.
DEFAULT_WEEKLY_HOURS = [(weekday, time(9, 0), time(17, 0)) for weekday in range(5)]

# Statuses that occupy a slot. An unpaid hold counts until it expires.
ACTIVE_STATUSES = (AppointmentStatus.AWAITING_PAYMENT, AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)


def _utc(dt: datetime) -> datetime:
    """SQLite (tests) returns naive datetimes; treat them as the UTC they are."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def hospital_zone(db: Session, doctor: Doctor) -> ZoneInfo:
    return ZoneInfo(db.get(Hospital, doctor.hospital_id).timezone)


def get_weekly_hours(db: Session, doctor: Doctor) -> tuple[list[tuple[int, time, time]], bool]:
    """Returns (blocks, is_default)."""
    rows = db.execute(
        select(DoctorAvailability).where(DoctorAvailability.doctor_id == doctor.id)
        .order_by(DoctorAvailability.weekday, DoctorAvailability.start_time)
    ).scalars().all()
    if not rows:
        return DEFAULT_WEEKLY_HOURS, True
    return [(r.weekday, r.start_time, r.end_time) for r in rows], False


def set_weekly_hours(db: Session, doctor: Doctor, blocks: list[tuple[int, time, time]]) -> None:
    """Replaces the whole schedule (simpler and safer than patching
    individual blocks). An empty list means "back to default hours"."""
    db.query(DoctorAvailability).filter(DoctorAvailability.doctor_id == doctor.id).delete()
    for weekday, start, end in blocks:
        db.add(DoctorAvailability(doctor_id=doctor.id, weekday=weekday, start_time=start, end_time=end))
    db.commit()


def _taken_starts(db: Session, doctor: Doctor) -> set[datetime]:
    rows = db.execute(
        select(Appointment.scheduled_at).where(Appointment.doctor_id == doctor.id, Appointment.status.in_(ACTIVE_STATUSES))
    ).scalars().all()
    return {_utc(t) for t in rows}


def _slot_starts_on(local_date: date, blocks, zone: ZoneInfo):
    """Every slot start (local time) on one calendar day."""
    for weekday, start, end in blocks:
        if weekday != local_date.weekday():
            continue
        t = datetime.combine(local_date, start, tzinfo=zone)
        block_end = datetime.combine(local_date, end, tzinfo=zone)
        while t + SLOT <= block_end:
            yield t
            t += SLOT


def available_slots(db: Session, doctor: Doctor, days: int) -> list[tuple[date, list[datetime]]]:
    """Open slots for the next `days` days, grouped by local date.
    Each slot is a timezone-aware datetime in the hospital's zone."""
    from app.services.payments.payment_service import expire_unpaid_holds

    expire_unpaid_holds(db)  # expired unpaid holds must show as free slots
    zone = hospital_zone(db, doctor)
    blocks, _ = get_weekly_hours(db, doctor)
    taken = _taken_starts(db, doctor)
    earliest = datetime.now(timezone.utc) + MIN_LEAD_TIME
    today = datetime.now(zone).date()

    result = []
    for offset in range(min(days, MAX_SLOT_DAYS)):
        local_date = today + timedelta(days=offset)
        open_slots = [
            t for t in _slot_starts_on(local_date, blocks, zone)
            if _utc(t) >= earliest and _utc(t) not in taken
        ]
        result.append((local_date, open_slots))
    return result


def booking_problem(db: Session, doctor: Doctor, when: datetime) -> str | None:
    """None if `when` is a valid slot for this doctor, otherwise a
    patient-friendly reason. (Already-booked slots are checked
    separately, so the caller can return a distinct 409 Conflict.)"""
    when = _utc(when)
    if when < datetime.now(timezone.utc) + MIN_LEAD_TIME:
        return "That time has already passed or is too soon to book. Please choose a later slot."

    zone = hospital_zone(db, doctor)
    local = when.astimezone(zone)
    blocks, _ = get_weekly_hours(db, doctor)
    if local not in set(_slot_starts_on(local.date(), blocks, zone)):
        return "That time isn't one of this doctor's available slots. Please pick a time from their schedule."
    return None
