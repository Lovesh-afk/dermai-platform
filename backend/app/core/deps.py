"""Shared FastAPI dependencies: DB session passthrough + current-user
resolution from the JWT. Import these in endpoints, never duplicate
the decode logic per-endpoint."""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_error

    try:
        user_id = uuid.UUID(payload.get("sub"))
    except (TypeError, ValueError):
        raise credentials_error

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_error
    return user


def require_permission(permission: str):
    """Usage: Depends(require_permission('patients:write'))"""

    def _checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        role = db.get(Role, user.role_id)
        if permission not in (role.permissions or []) and role.name != "SUPER_ADMIN":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker


def require_role(*role_names: str):
    """Usage: Depends(require_role('SUPER_ADMIN')) or
    Depends(require_role('SUPER_ADMIN', 'HOSPITAL_ADMIN')) for either.
    Unlike require_permission (a specific action), this checks the
    user's role by name — the right tool for "only admins can see
    this screen at all" rather than "can this role do this specific
    thing"."""

    def _checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        role = db.get(Role, user.role_id)
        if role.name not in role_names:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker
