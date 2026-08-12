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


class PermissionDeniedError(AppError):
    pass


class TenantMismatchError(AppError):
    """Raised when a request tries to access a resource outside its hospital_id scope."""
