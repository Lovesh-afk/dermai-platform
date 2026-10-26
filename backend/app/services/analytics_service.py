"""
Dashboard analytics for one hospital or the whole platform.

How it works: load the rows for the period with only the columns needed,
then aggregate in Python. Two reasons:
  - Days must be bucketed in the HOSPITAL's time zone ("Monday" in
    Kolkata), which plain SQL GROUP BY date() can't do portably.
  - It's simple, readable and testable at this scale. At large scale,
    the same numbers would come from SQL aggregates or a nightly
    pre-computed summary table (see docs/DECISIONS.md).

Only aggregates leave this module: no patient names or records.

Definitions (used consistently everywhere):
  appointments        = real bookings scheduled in the period; unpaid holds
                        and abandoned checkouts are NOT appointments
  no-show rate        = no-shows / (completed + no-shows)
  cancellation rate   = cancelled / appointments
  checkout conversion = paid / (paid + abandoned)
  revenue             = by payment date: collected (gross), refunded, net
"""
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.payment import Payment, PaymentStatus
from app.models.prediction import Prediction
from app.models.skin_image import SkinImage, SkinImageStatus
from app.schemas.analytics import (
    AIUsage, AnalyticsOut, AnalyticsRates, AnalyticsRevenue, AnalyticsTotals, DailyPoint, DoctorRow, HospitalRow,
)

S = AppointmentStatus


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _is_abandoned_checkout(appt: Appointment) -> bool:
    """A paid booking that was never paid: expired or cancelled before payment."""
    return appt.status == S.CANCELLED and appt.payment is not None and appt.payment.paid_at is None


def hospital_analytics(db: Session, hospital_id: uuid.UUID, days: int) -> AnalyticsOut:
    hospital = db.get(Hospital, hospital_id)
    return _build(db, days, ZoneInfo(hospital.timezone), hospital_id=hospital_id)


def platform_analytics(db: Session, days: int) -> AnalyticsOut:
    return _build(db, days, ZoneInfo("UTC"), hospital_id=None)


def _build(db: Session, days: int, zone: ZoneInfo, hospital_id: uuid.UUID | None) -> AnalyticsOut:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    in_period = lambda dt: dt is not None and start <= _utc(dt) <= now  # noqa: E731
    scoped = lambda query, model: query.where(model.hospital_id == hospital_id) if hospital_id else query  # noqa: E731

    appointments = db.execute(scoped(select(Appointment), Appointment)).scalars().all()
    payments = db.execute(scoped(select(Payment), Payment)).scalars().all()
    doctors = db.execute(scoped(select(Doctor), Doctor)).scalars().all()

    # --- Appointments ---
    real, abandoned = [], 0
    for appt in appointments:
        if not in_period(appt.scheduled_at) or appt.status == S.AWAITING_PAYMENT:
            continue
        if _is_abandoned_checkout(appt):
            abandoned += 1
        else:
            real.append(appt)
    status_counts = Counter(a.status for a in real)
    upcoming = sum(
        1 for a in appointments
        if a.status in (S.PENDING, S.CONFIRMED) and now <= _utc(a.scheduled_at) <= now + timedelta(days=7)
    )

    # --- Revenue (by when money moved, not by appointment date) ---
    paid = [p for p in payments if in_period(p.paid_at)]
    refunded = [p for p in payments if p.status == PaymentStatus.REFUNDED and in_period(p.refunded_at)]
    gross = sum(p.amount_paise for p in paid)
    refunded_total = sum(p.amount_paise for p in refunded)

    # --- Daily series, bucketed in the local time zone ---
    day_keys = [(start.astimezone(zone) + timedelta(days=i)).date() for i in range(days + 1)]
    daily = {d: Counter() for d in day_keys}
    for appt in real:
        day = _utc(appt.scheduled_at).astimezone(zone).date()
        if day in daily:
            daily[day]["appointments"] += 1
            daily[day][appt.status.value] += 1
    for p in paid:
        day = _utc(p.paid_at).astimezone(zone).date()
        if day in daily:
            daily[day]["revenue"] += p.amount_paise
    for p in refunded:
        day = _utc(p.refunded_at).astimezone(zone).date()
        if day in daily:
            daily[day]["revenue"] -= p.amount_paise

    # --- Per doctor ---
    per_doctor = defaultdict(Counter)
    for appt in real:
        per_doctor[appt.doctor_id][appt.status.value] += 1
        per_doctor[appt.doctor_id]["appointments"] += 1
    appt_doctor = {a.id: a.doctor_id for a in appointments}
    for p in paid:
        per_doctor[appt_doctor.get(p.appointment_id)]["revenue"] += p.amount_paise
    for p in refunded:
        per_doctor[appt_doctor.get(p.appointment_id)]["revenue"] -= p.amount_paise
    doctor_rows = sorted(
        (
            DoctorRow(
                doctor_id=d.id, name=d.full_name, appointments=per_doctor[d.id]["appointments"],
                completed=per_doctor[d.id]["completed"], no_show=per_doctor[d.id]["no_show"],
                cancelled=per_doctor[d.id]["cancelled"], net_revenue_paise=per_doctor[d.id]["revenue"],
                no_show_rate=_rate(per_doctor[d.id]["no_show"], per_doctor[d.id]["completed"] + per_doctor[d.id]["no_show"]),
            )
            for d in doctors
        ),
        key=lambda r: (-r.appointments, r.name or ""),
    )

    # --- AI photo analysis ---
    images = [i for i in db.execute(scoped(select(SkinImage), SkinImage)).scalars().all() if in_period(i.created_at)]
    image_ids = [i.id for i in images]
    classes = db.execute(select(Prediction.predicted_class).where(Prediction.skin_image_id.in_(image_ids))).scalars().all() if image_ids else []
    ai = AIUsage(
        photos_uploaded=len(images),
        analyzed=sum(1 for i in images if i.status == SkinImageStatus.ANALYZED),
        failed=sum(1 for i in images if i.status == SkinImageStatus.FAILED),
        by_class=dict(Counter(classes)),
    )

    # --- Per hospital (platform only) ---
    hospital_rows = []
    if hospital_id is None:
        for h in db.execute(select(Hospital).order_by(Hospital.name)).scalars().all():
            h_real = [a for a in real if a.hospital_id == h.id]
            h_net = sum(p.amount_paise for p in paid if p.hospital_id == h.id) - sum(p.amount_paise for p in refunded if p.hospital_id == h.id)
            hospital_rows.append(HospitalRow(
                hospital_id=h.id, name=h.name, doctors=sum(1 for d in doctors if d.hospital_id == h.id),
                appointments=len(h_real), completed=sum(1 for a in h_real if a.status == S.COMPLETED), net_revenue_paise=h_net,
            ))

    completed, no_show = status_counts[S.COMPLETED], status_counts[S.NO_SHOW]
    return AnalyticsOut(
        scope="platform" if hospital_id is None else "hospital",
        period_days=days, start=start, end=now, timezone=zone.key,
        totals=AnalyticsTotals(
            appointments=len(real), completed=completed, cancelled=status_counts[S.CANCELLED], no_show=no_show,
            upcoming_7d=upcoming, active_patients=len({a.patient_id for a in real}), abandoned_checkouts=abandoned,
        ),
        rates=AnalyticsRates(
            no_show_rate=_rate(no_show, completed + no_show),
            cancellation_rate=_rate(status_counts[S.CANCELLED], len(real)),
            checkout_conversion=_rate(len(paid), len(paid) + abandoned),
        ),
        revenue=AnalyticsRevenue(
            gross_paise=gross, refunded_paise=refunded_total, net_paise=gross - refunded_total,
            paid_count=len(paid), refund_count=len(refunded),
        ),
        daily=[
            DailyPoint(date=d, appointments=c["appointments"], completed=c["completed"], cancelled=c["cancelled"],
                       no_show=c["no_show"], revenue_paise=c["revenue"])
            for d, c in daily.items()
        ],
        doctors=doctor_rows, ai=ai, hospitals=hospital_rows,
    )
