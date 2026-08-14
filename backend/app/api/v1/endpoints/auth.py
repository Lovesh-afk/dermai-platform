"""HTTP layer only — validates input via schemas, calls the service
layer, translates domain exceptions to HTTP status codes. No business
logic and no direct DB access here (see ARCHITECTURE.md)."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import (
    AlreadyExistsError,
    InvalidCredentialsError,
    InvalidMFACodeError,
    InvalidResetTokenError,
    NotFoundError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginResponse,
    LogoutRequest,
    MFADisableRequest,
    MFALoginVerifyRequest,
    MFASetupOut,
    MFAVerifySetupRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetRequestOut,
    RefreshRequest,
    TokenPair,
    UserLogin,
    UserOut,
    UserRegister,
)
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


@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        return auth_service.authenticate_user(db, payload, user_agent=request.headers.get("user-agent"))
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/mfa/login-verify", response_model=TokenPair)
def mfa_login_verify(payload: MFALoginVerifyRequest, request: Request, db: Session = Depends(get_db)):
    try:
        return auth_service.verify_mfa_and_login(
            db, payload.mfa_pending_token, payload.code, user_agent=request.headers.get("user-agent")
        )
    except (InvalidCredentialsError, InvalidMFACodeError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        return auth_service.refresh_access_token(db, payload.refresh_token)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    auth_service.logout(db, payload.refresh_token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_user_out(db, current_user)


# --- MFA setup (requires being logged in already) ---

@router.post("/mfa/setup", response_model=MFASetupOut)
def mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret, uri = auth_service.start_mfa_setup(db, current_user)
    return MFASetupOut(secret=secret, provisioning_uri=uri)


@router.post("/mfa/verify-setup", status_code=status.HTTP_204_NO_CONTENT)
def mfa_verify_setup(payload: MFAVerifySetupRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        auth_service.verify_mfa_setup(db, current_user, payload.code)
    except InvalidMFACodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def mfa_disable(payload: MFADisableRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        auth_service.disable_mfa(db, current_user, payload.password)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


# --- Password reset (no auth required — that's the point) ---

@router.post("/password-reset/request", response_model=PasswordResetRequestOut)
def password_reset_request(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    return auth_service.request_password_reset(db, payload.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def password_reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    try:
        auth_service.confirm_password_reset(db, payload.token, payload.new_password)
    except InvalidResetTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
