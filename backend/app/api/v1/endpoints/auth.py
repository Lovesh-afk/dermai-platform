"""HTTP layer only — validates input via schemas, calls the service
layer, translates domain exceptions to HTTP status codes. No business
logic and no direct DB access here (see ARCHITECTURE.md)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import AlreadyExistsError, InvalidCredentialsError, NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RefreshRequest, TokenPair, UserLogin, UserOut, UserRegister
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_user(db, payload)
    except AlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _to_user_out(db, user)


@router.post("/login", response_model=TokenPair)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate_user(db, payload)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        return auth_service.refresh_access_token(db, payload.refresh_token)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_user_out(db, current_user)


def _to_user_out(db: Session, user: User) -> UserOut:
    from app.models.role import Role

    role = db.get(Role, user.role_id)
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=role.name,
        hospital_id=str(user.hospital_id) if user.hospital_id else None,
    )
