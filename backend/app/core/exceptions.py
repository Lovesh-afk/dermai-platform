"""Domain-level exceptions, translated to HTTP responses at the API layer
(not raised as HTTPException from inside services — keeps services
transport-agnostic and unit-testable without FastAPI in the loop)."""


class AppError(Exception):
    """Base class for all application (non-framework) errors."""


class NotFoundError(AppError):
    pass


class AlreadyExistsError(AppError):
    pass


class InvalidCredentialsError(AppError):
    pass


class MFARequiredError(AppError):
    """Raised by the service layer when password is correct but MFA
    verification is still needed — the API layer turns this into a
    200 with an mfa_pending_token rather than an error status, since
    it's an expected step in a successful login, not a failure."""
    def __init__(self, mfa_pending_token: str):
        self.mfa_pending_token = mfa_pending_token
        super().__init__("MFA verification required")


class InvalidMFACodeError(AppError):
    pass


class InvalidResetTokenError(AppError):
    pass


class PermissionDeniedError(AppError):
    pass


class TenantMismatchError(AppError):
    """Raised when a request tries to access a resource outside its hospital_id scope."""
