from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    hospital_slug: str | None = None  # None => patient signing up directly


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    hospital_id: str | None = None

    model_config = {"from_attributes": True}


# --- MFA ---

class MFASetupOut(BaseModel):
    secret: str
    provisioning_uri: str  # feed this to a QR code generator on the frontend


class MFAVerifySetupRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MFADisableRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    """Either a full token pair (MFA disabled) or an mfa_pending_token
    the client must submit alongside a TOTP code (MFA enabled).
    Exactly one of the two token fields is populated."""
    mfa_required: bool
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    mfa_pending_token: str | None = None


class MFALoginVerifyRequest(BaseModel):
    mfa_pending_token: str
    code: str = Field(min_length=6, max_length=6)


# --- Password reset ---

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetRequestOut(BaseModel):
    message: str
    # DEV-ONLY: no email service is wired up yet (Phase 12), so the
    # raw reset token is returned directly for local testing. This
    # field MUST be removed once real email delivery exists — see
    # docs/ARCHITECTURE.md Phase 2 notes.
    dev_reset_token: str | None = None


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


# --- Logout ---

class LogoutRequest(BaseModel):
    refresh_token: str
