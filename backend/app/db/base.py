"""Import all models here so Alembic autogenerate can discover them
via Base.metadata — models themselves never import this file."""
from app.db.base_class import Base  # noqa
from app.models.hospital import Hospital  # noqa
from app.models.role import Role  # noqa
from app.models.user import User  # noqa
