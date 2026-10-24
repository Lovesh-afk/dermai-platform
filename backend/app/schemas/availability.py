from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import UUIDStr


class WorkingHoursBlock(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0 = Monday ... 6 = Sunday
    start_time: time
    end_time: time

    @field_validator("start_time", "end_time")
    @classmethod
    def on_half_hour(cls, v: time) -> time:
        # Slots are 30 minutes, so blocks must start/end on :00 or :30
        if v.minute not in (0, 30) or v.second or v.microsecond:
            raise ValueError("Times must be on the hour or half hour, e.g. 09:00 or 09:30")
        return v

    @model_validator(mode="after")
    def start_before_end(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self

    model_config = {"from_attributes": True}


class WeeklyHoursIn(BaseModel):
    """Replaces the whole weekly schedule. Days with no blocks are days
    off. An empty list restores the default hours."""
    blocks: list[WorkingHoursBlock] = Field(max_length=28)

    @model_validator(mode="after")
    def no_overlaps(self):
        by_day: dict[int, list[WorkingHoursBlock]] = {}
        for b in self.blocks:
            by_day.setdefault(b.weekday, []).append(b)
        for blocks in by_day.values():
            blocks.sort(key=lambda b: b.start_time)
            for earlier, later in zip(blocks, blocks[1:]):
                if later.start_time < earlier.end_time:
                    raise ValueError("Working hours on the same day must not overlap")
        return self


class WeeklyHoursOut(BaseModel):
    is_default: bool  # True = doctor hasn't set hours; defaults apply
    timezone: str
    slot_minutes: int
    blocks: list[WorkingHoursBlock]


class Slot(BaseModel):
    start: datetime  # UTC; send this back when booking
    label: str       # local wall-clock time, e.g. "09:30"


class SlotDay(BaseModel):
    date: date  # in the hospital's time zone
    slots: list[Slot]


class DoctorSlotsOut(BaseModel):
    doctor_id: UUIDStr
    timezone: str
    slot_minutes: int
    days: list[SlotDay]
