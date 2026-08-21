"""Shared schema building blocks.

UUIDStr: Pydantic v2, unlike v1, does NOT silently stringify a UUID
object for a plain `str` field even with from_attributes=True — it
raises a validation error instead. Every response schema that exposes
a database UUID primary/foreign key as a string uses this type
instead of bare `str` so ORM objects can be returned directly from
endpoints without manually converting every id field by hand.
"""
from typing import Annotated

from pydantic import BeforeValidator

UUIDStr = Annotated[str, BeforeValidator(lambda v: str(v) if v is not None else v)]
