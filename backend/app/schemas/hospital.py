import re

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UUIDStr

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class HospitalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not SLUG_PATTERN.match(v):
            raise ValueError("slug must be lowercase letters, numbers, and hyphens only (e.g. 'city-derma-clinic')")
        return v


class HospitalOut(BaseModel):
    id: UUIDStr
    name: str
    slug: str
    subscription_tier: str
    is_active: bool
    timezone: str

    model_config = {"from_attributes": True}


class HospitalUpdate(BaseModel):
    """All fields optional — only what's provided gets updated."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    subscription_tier: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)  # IANA name, e.g. "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                ZoneInfo(v)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError("Unknown time zone; use an IANA name like 'Asia/Kolkata'")
        return v
