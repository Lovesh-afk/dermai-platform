from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.common import UUIDStr


class AnalyticsTotals(BaseModel):
    appointments: int        # real bookings in the period (abandoned checkouts excluded)
    completed: int
    cancelled: int
    no_show: int
    upcoming_7d: int         # pending/confirmed in the next 7 days
    active_patients: int     # distinct patients with an appointment in the period
    abandoned_checkouts: int  # paid bookings never paid for


class AnalyticsRates(BaseModel):
    # None when there's nothing to divide by (avoids a misleading "0%")
    no_show_rate: float | None        # no-shows / (completed + no-shows)
    cancellation_rate: float | None   # cancelled / appointments
    checkout_conversion: float | None  # paid / (paid + abandoned)


class AnalyticsRevenue(BaseModel):
    gross_paise: int     # collected in the period
    refunded_paise: int  # refunded in the period
    net_paise: int
    paid_count: int
    refund_count: int


class DailyPoint(BaseModel):
    date: date
    appointments: int
    completed: int
    cancelled: int
    no_show: int
    revenue_paise: int  # net: collected minus refunded that day


class DoctorRow(BaseModel):
    doctor_id: UUIDStr
    name: str | None
    appointments: int
    completed: int
    no_show: int
    cancelled: int
    net_revenue_paise: int
    no_show_rate: float | None


class HospitalRow(BaseModel):
    hospital_id: UUIDStr
    name: str
    doctors: int
    appointments: int
    completed: int
    net_revenue_paise: int


class AIUsage(BaseModel):
    photos_uploaded: int
    analyzed: int
    failed: int
    by_class: dict[str, int]  # AI result counts: acne / eczema / fungal / normal


class AnalyticsOut(BaseModel):
    scope: str          # "hospital" | "platform"
    period_days: int
    start: datetime
    end: datetime
    timezone: str       # days are bucketed in this zone
    totals: AnalyticsTotals
    rates: AnalyticsRates
    revenue: AnalyticsRevenue
    daily: list[DailyPoint]
    doctors: list[DoctorRow]
    ai: AIUsage
    hospitals: list[HospitalRow] = []  # platform scope only
