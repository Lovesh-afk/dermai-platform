"""
Central place to write audit events — every other service that
touches sensitive data calls this rather than writing to AuditLog
directly, so the shape of an audit entry stays consistent everywhere
it's used.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit_event(
    db: Session,
    action: str,
    user_id: uuid.UUID | None = None,
    hospital_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        user_id=user_id,
        hospital_id=hospital_id,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
